from datetime import timedelta

import mysql.connector

from Models.consumo_model import ConsumoModel
from Models.finanzas_model import agregados, calcular_saldo, resumen, resumen_lista
from database import get_connection
from utils.fechas import a_fecha, hoy_local, noches_entre


class TransicionInvalida(Exception):
    """La transición de estado pedida no está permitida (§6.3)."""

    def __init__(self, desde, hacia, permitidas):
        self.desde = desde
        self.hacia = hacia
        self.permitidas = sorted(permitidas)
        super().__init__(f'{desde} -> {hacia}')


# ─── §6.3 Máquina de estados ──────────────────────────────────────────────────
# El vocabulario es el del ENUM de la tabla `reservas`. El documento hablaba de
# 'check-in' y de 'llegada prevista'; en este esquema los estados reales son
# 'checkin'/'checkout' y 'llegada prevista' no existe (ver ESTADOS_BLOQUEAN).
TRANSICIONES_RESERVA = {
    'pendiente':  {'confirmada', 'cancelada'},
    'confirmada': {'checkin', 'cancelada', 'pendiente'},
    'checkin':    {'checkout'},
    'checkout':   set(),
    'cancelada':  set(),
}

# Estados que ocupan la habitación en un rango de fechas y por tanto impiden
# sobre-reservar. 'cancelada' y 'checkout' liberan la habitación.
ESTADOS_BLOQUEAN = ('pendiente', 'confirmada', 'checkin')

TRANSICIONES_HABITACION = {
    'disponible':    {'reservada', 'ocupada', 'mantenimiento', 'bloqueada'},
    'reservada':     {'ocupada', 'disponible', 'mantenimiento', 'bloqueada'},
    'ocupada':       {'mantenimiento'},   # sólo por la vía del check-out
    'mantenimiento': {'disponible', 'bloqueada'},
    'bloqueada':     {'disponible', 'mantenimiento'},
}

# Alias tolerados en la entrada, para no romper las llamadas ya existentes.
ALIAS_ESTADO = {
    'check-in': 'checkin', 'check_in': 'checkin', 'check in': 'checkin',
    'check-out': 'checkout', 'check_out': 'checkout', 'check out': 'checkout',
}


def normalizar_estado(estado):
    """Traduce las variantes que usa el frontend al vocabulario del ENUM."""
    if not estado:
        return estado
    limpio = str(estado).strip().lower()
    return ALIAS_ESTADO.get(limpio, limpio)


class ReservaModel:

    # ─── HELPERS PRIVADOS ─────────────────────────────────────────────────────

    def _tiene_solapamiento(self, cursor, habitacion_id, fecha_entrada,
                            fecha_salida, excluir_reserva_id=None):
        """
        True si la habitación ya tiene una reserva activa que se solapa con
        el rango [fecha_entrada, fecha_salida).

        El solapamiento es `inicioA < finB && inicioB < finA`: dos reservas
        donde A.fecha_salida == B.fecha_entrada NO solapan (un huésped sale el
        mismo día que entra el otro).

        **La consulta es una lectura con bloqueo (`FOR UPDATE`), y eso no es
        decorativo.** MySQL corre en REPEATABLE READ, así que un `SELECT`
        normal lee del snapshot que la transacción tomó en su primera lectura
        y NO vería la reserva que otra transacción acabara de confirmar. Con
        dos cajeros reservando la misma habitación a la vez, los dos leían
        "libre" y las dos reservas entraban.

        Una lectura con bloqueo siempre ve la última versión confirmada y,
        cuando no hay coincidencias, toma gap locks sobre el rango, que es lo
        que impide que la otra transacción inserte ahí mientras tanto.
        """
        marcadores = ', '.join(['%s'] * len(ESTADOS_BLOQUEAN))
        query = f"""
            SELECT rh.id
            FROM reservas r
            JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
            WHERE rh.habitacion_id = %s
              AND r.estado IN ({marcadores})
              AND r.fecha_entrada < %s
              AND r.fecha_salida  > %s
        """
        params = [habitacion_id, *ESTADOS_BLOQUEAN, fecha_salida, fecha_entrada]

        if excluir_reserva_id is not None:
            query += ' AND r.id != %s'
            params.append(excluir_reserva_id)

        query += ' LIMIT 1 FOR UPDATE'

        cursor.execute(query, params)
        return cursor.fetchone() is not None

    def _bloquear_habitacion(self, cursor, habitacion_id):
        """
        `SELECT ... FOR UPDATE` sobre la habitación. Serializa las peticiones
        que compiten por la misma habitación, que es lo que impide la doble
        reserva entre dos requests simultáneos (§6.2). Validar en Python sin
        bloquear no evita la condición de carrera.
        """
        cursor.execute(
            'SELECT id, estado FROM habitaciones WHERE id = %s FOR UPDATE',
            (habitacion_id,),
        )
        return cursor.fetchone()

    def _habitaciones_de(self, cursor, reserva_id):
        """Ids de las habitaciones ligadas a una reserva."""
        cursor.execute(
            'SELECT habitacion_id FROM reserva_habitaciones WHERE reserva_id = %s',
            (reserva_id,),
        )
        filas = cursor.fetchall()
        if not filas:
            return []
        if isinstance(filas[0], dict):
            return [f['habitacion_id'] for f in filas]
        return [f[0] for f in filas]

    def _adjuntar_habitaciones(self, cursor, filas):
        """
        §8.1 — Mete las habitaciones dentro de cada reserva con UNA consulta.

        Elimina de golpe los cuatro bucles N+1 del frontend, que pedían
        `/reservas/:id/habitaciones` de una en una (con 200 reservas eran 200+
        peticiones por cada apertura del modal de habitación).
        """
        filas = list(filas or [])
        if not filas:
            return filas

        ids = [f['id'] for f in filas]
        marcadores = ', '.join(['%s'] * len(ids))
        cursor.execute(
            f"""
            SELECT rh.id AS reserva_habitacion_id,
                   rh.reserva_id, rh.habitacion_id, rh.precio_noche,
                   h.numero, h.piso, h.tipo_cama,
                   h.estado AS habitacion_estado,
                   t.nombre AS tipo_nombre
            FROM reserva_habitaciones rh
            JOIN habitaciones h ON h.id = rh.habitacion_id
            JOIN tipos_habitacion t ON t.id = h.tipo_id
            WHERE rh.reserva_id IN ({marcadores})
            ORDER BY h.piso, h.numero
            """,
            ids,
        )

        por_reserva = {}
        for hab in cursor.fetchall():
            por_reserva.setdefault(hab['reserva_id'], []).append(hab)

        for fila in filas:
            fila['habitaciones'] = por_reserva.get(fila['id'], [])
        return filas

    # ─── LECTURA ──────────────────────────────────────────────────────────────
    # Todos los listados devuelven ya el resumen financiero de §4.1 y las
    # habitaciones embebidas de §8.1.

    def _listar(self, where='', params=(), orden='r.creado_en DESC'):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"""
                SELECT r.*,
                       CONCAT(c.nombre, ' ', c.apellido) AS cliente_nombre,
                       c.numero_documento,
                       c.telefono,
                       CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre,
                       {agregados('r')}
                FROM reservas r
                JOIN clientes c ON r.cliente_id = c.id
                LEFT JOIN empleados e ON r.empleado_id = e.id
                {where}
                ORDER BY {orden}
                """,
                params,
            )
            filas = cursor.fetchall()
            self._adjuntar_habitaciones(cursor, filas)
            return resumen_lista(filas)
        finally:
            cursor.close()
            conn.close()

    def get_all(self):
        return self._listar()

    def get_by_id(self, id):
        filas = self._listar('WHERE r.id = %s', (id,))
        return filas[0] if filas else None

    def get_by_estado(self, estado):
        return self._listar('WHERE r.estado = %s', (estado,),
                            orden='r.fecha_entrada')

    def get_activas(self):
        return self._listar("WHERE r.estado IN ('confirmada', 'checkin')",
                            orden='r.fecha_entrada')

    # ─── §6.1 ALTA TRANSACCIONAL ──────────────────────────────────────────────

    def create(self, data, empleado_id=None):
        """
        Crea la reserva, la liga a su habitación y registra los acompañantes
        en UNA sola transacción.

        Antes el frontend hacía dos llamadas: creaba la reserva y luego
        asociaba la habitación; si la segunda fallaba sólo escribía un
        `console.warn` y quedaba una reserva huérfana sin habitación.

        El servidor calcula `noches`, `total` y `saldo_pendiente` e ignora los
        que vengan del cliente. El estado siempre nace 'pendiente'.

        Lanza ValueError con un código: 'fechas_invalidas', 'solapamiento_fechas',
        'habitacion_no_encontrada', 'cliente_no_encontrado', 'precio_invalido'.
        """
        fecha_entrada = a_fecha(data.get('fecha_entrada'))
        fecha_salida  = a_fecha(data.get('fecha_salida'))

        if not fecha_entrada or not fecha_salida or fecha_entrada >= fecha_salida:
            raise ValueError('fechas_invalidas')

        noches = noches_entre(fecha_entrada, fecha_salida)
        habitacion_id = data.get('habitacion_id')
        precio_noche = data.get('precio_noche')

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute('SELECT id FROM clientes WHERE id = %s',
                           (data['cliente_id'],))
            if not cursor.fetchone():
                raise ValueError('cliente_no_encontrado')

            # El precio por noche sale del tipo de habitación si el cliente no
            # manda uno; nunca se acepta 0 o negativo.
            if habitacion_id:
                habitacion = self._bloquear_habitacion(cursor, habitacion_id)
                if not habitacion:
                    raise ValueError('habitacion_no_encontrada')

                if self._tiene_solapamiento(cursor, habitacion_id,
                                            fecha_entrada, fecha_salida):
                    raise ValueError('solapamiento_fechas')

                if precio_noche in (None, '', 0):
                    cursor.execute(
                        """
                        SELECT t.precio_base
                        FROM habitaciones h
                        JOIN tipos_habitacion t ON t.id = h.tipo_id
                        WHERE h.id = %s
                        """,
                        (habitacion_id,),
                    )
                    fila = cursor.fetchone()
                    precio_noche = fila['precio_base'] if fila else 0

                precio_noche = float(precio_noche or 0)
                if precio_noche <= 0:
                    raise ValueError('precio_invalido')
            else:
                precio_noche = float(precio_noche or 0)

            total = precio_noche * noches

            # `num_adultos`/`num_ninos` se derivan de los acompañantes cuando
            # vienen (§6.6); si no, se respeta lo que teclee el recepcionista.
            acompanantes = data.get('acompanantes') or []
            num_adultos, num_ninos = self._contar_personas(data, acompanantes)

            cursor.execute(
                """
                INSERT INTO reservas (
                    cliente_id, empleado_id, fecha_reserva, fecha_entrada,
                    fecha_salida, hora_llegada, hora_salida, num_adultos,
                    num_ninos, estado, fuente, anticipo, saldo_pendiente,
                    total, late_checkout, observaciones
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                          'pendiente', %s, 0, %s, %s, 0, %s)
                """,
                (
                    data['cliente_id'],
                    empleado_id,
                    a_fecha(data.get('fecha_reserva')) or hoy_local(),
                    fecha_entrada,
                    fecha_salida,
                    data.get('hora_llegada'),
                    data.get('hora_salida'),
                    num_adultos,
                    num_ninos,
                    data.get('fuente', 'directa'),
                    total,          # saldo_pendiente inicial = total, sin anticipo
                    total,
                    data.get('observaciones'),
                ),
            )
            reserva_id = cursor.lastrowid

            if habitacion_id:
                cursor.execute(
                    """
                    INSERT INTO reserva_habitaciones
                        (reserva_id, habitacion_id, precio_noche)
                    VALUES (%s, %s, %s)
                    """,
                    (reserva_id, habitacion_id, precio_noche),
                )
                self.recalcular_estado_habitacion(habitacion_id, cursor)

            if acompanantes:
                self._insertar_acompanantes(cursor, reserva_id, acompanantes)

            conn.commit()
            return reserva_id

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def _contar_personas(self, data, acompanantes):
        """
        §6.6 — El número de huéspedes se deriva de los acompañantes cuando se
        registran nominalmente; si no hay lista, vale lo que teclee el usuario.
        Así deja de haber dos fuentes de verdad para el mismo campo.
        """
        if acompanantes:
            menores = sum(1 for a in acompanantes if a.get('es_menor'))
            adultos = len(acompanantes) - menores + 1   # +1 por el titular
            return adultos, menores

        try:
            adultos = max(int(data.get('num_adultos', 1) or 1), 1)
        except (TypeError, ValueError):
            adultos = 1
        try:
            ninos = max(int(data.get('num_ninos', 0) or 0), 0)
        except (TypeError, ValueError):
            ninos = 0
        return adultos, ninos

    def _insertar_acompanantes(self, cursor, reserva_id, lista):
        filas = [
            (
                reserva_id,
                a.get('tipo_documento', 'CC'),
                a['numero_documento'],
                a['nombre'],
                a['apellido'],
                a.get('telefono'),
                1 if a.get('es_menor') else 0,
            )
            for a in lista
        ]
        cursor.executemany(
            """
            INSERT IGNORE INTO acompanantes_reserva
                (reserva_id, tipo_documento, numero_documento,
                 nombre, apellido, telefono, es_menor)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            filas,
        )

    def sincronizar_personas(self, reserva_id):
        """
        Recalcula `num_adultos` / `num_ninos` desde la tabla de acompañantes.
        Reemplaza al `PATCH /reservas/:id/personas` que el frontend calculaba
        en el navegador (§6.6).
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT COUNT(*) AS total,
                       COALESCE(SUM(es_menor), 0) AS menores
                FROM acompanantes_reserva
                WHERE reserva_id = %s
                """,
                (reserva_id,),
            )
            fila = cursor.fetchone() or {'total': 0, 'menores': 0}
            menores = int(fila['menores'] or 0)
            adultos = int(fila['total'] or 0) - menores + 1   # +1 por el titular

            cursor.execute(
                'UPDATE reservas SET num_adultos = %s, num_ninos = %s WHERE id = %s',
                (max(adultos, 1), menores, reserva_id),
            )
            conn.commit()
            return {'num_adultos': max(adultos, 1), 'num_ninos': menores}
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # ─── ESCRITURA ────────────────────────────────────────────────────────────

    def update(self, id, data):
        """
        Actualiza sólo los campos que el controlador ya filtró con la allowlist
        (§5.2). Nunca escribe `total`, `estado`, `anticipo` ni `saldo_pendiente`:
        esos los deriva el servidor.

        Si cambian las fechas, revalida el solapamiento (§6.2).
        """
        if not data:
            return 0

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                'SELECT * FROM reservas WHERE id = %s FOR UPDATE', (id,)
            )
            actual = cursor.fetchone()
            if not actual:
                return 0

            fecha_entrada = a_fecha(data.get('fecha_entrada')) or actual['fecha_entrada']
            fecha_salida  = a_fecha(data.get('fecha_salida'))  or actual['fecha_salida']
            if fecha_entrada >= fecha_salida:
                raise ValueError('fechas_invalidas')

            cambian_fechas = (fecha_entrada != actual['fecha_entrada']
                              or fecha_salida != actual['fecha_salida'])

            if cambian_fechas:
                for habitacion_id in self._habitaciones_de(cursor, id):
                    self._bloquear_habitacion(cursor, habitacion_id)
                    if self._tiene_solapamiento(cursor, habitacion_id,
                                                fecha_entrada, fecha_salida,
                                                excluir_reserva_id=id):
                        raise ValueError('solapamiento_fechas')

            asignaciones = []
            valores = []
            for campo in ('cliente_id', 'hora_llegada', 'hora_salida',
                          'num_adultos', 'num_ninos', 'fuente',
                          'late_checkout', 'observaciones'):
                if campo in data:
                    asignaciones.append(f'{campo} = %s')
                    valores.append(data[campo])

            if cambian_fechas:
                asignaciones += ['fecha_entrada = %s', 'fecha_salida = %s']
                valores += [fecha_entrada, fecha_salida]

            if not asignaciones:
                conn.rollback()
                return 0

            valores.append(id)
            cursor.execute(
                f"UPDATE reservas SET {', '.join(asignaciones)} WHERE id = %s",
                valores,
            )
            afectadas = cursor.rowcount

            # Si cambió la estadía, el total del alojamiento cambia con ella.
            if cambian_fechas:
                self._recalcular_total(cursor, id)

            conn.commit()
            return afectadas or 1

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def _recalcular_total(self, cursor, reserva_id):
        """
        Recalcula `total` = noches × suma de precios por noche, y con él el
        `saldo_pendiente` almacenado. El saldo que consume el frontend se
        deriva siempre en `finanzas_model`; esta columna se mantiene al día
        para no dejar datos incoherentes en la tabla.
        """
        cursor.execute(
            """
            SELECT DATEDIFF(r.fecha_salida, r.fecha_entrada) AS noches,
                   COALESCE(SUM(rh.precio_noche), 0) AS precio_total,
                   r.anticipo
            FROM reservas r
            LEFT JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
            WHERE r.id = %s
            GROUP BY r.id
            """,
            (reserva_id,),
        )
        fila = cursor.fetchone()
        if not fila:
            return

        noches = max(int(fila['noches'] or 0), 0)
        total = float(fila['precio_total'] or 0) * noches
        saldo = max(total - float(fila['anticipo'] or 0), 0)

        cursor.execute(
            'UPDATE reservas SET total = %s, saldo_pendiente = %s WHERE id = %s',
            (total, saldo, reserva_id),
        )

    def update_estado(self, id, estado, forzar=False):
        """
        §6.3 — Cambia el estado respetando la máquina de estados.

        Antes se aceptaba cualquier transición: se podía pasar de 'checkout' a
        'pendiente' o saltarse el check-in. Con `forzar=True` (permiso
        `reservas.forzar_estado`) se salta la validación, para casos de
        corrección administrativa.

        Lanza TransicionInvalida si la transición no está permitida.
        """
        estado = normalizar_estado(estado)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                'SELECT estado FROM reservas WHERE id = %s FOR UPDATE', (id,)
            )
            actual = cursor.fetchone()
            if not actual:
                return 0

            anterior = actual['estado']
            if anterior == estado:
                conn.rollback()
                return 1

            permitidas = TRANSICIONES_RESERVA.get(anterior, set())
            if not forzar and estado not in permitidas:
                raise TransicionInvalida(anterior, estado, permitidas)

            habitaciones = self._habitaciones_de(cursor, id)

            cursor.execute('UPDATE reservas SET estado = %s WHERE id = %s',
                           (estado, id))
            afectadas = cursor.rowcount

            for habitacion_id in habitaciones:
                self.recalcular_estado_habitacion(habitacion_id, cursor)

            conn.commit()
            return afectadas
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def confirmar_reserva(self, id, anticipo):
        """
        Confirma la reserva registrando el anticipo. Ya era atómico en el
        original — es el patrón que el resto de operaciones ahora replica.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                'SELECT id, total, estado FROM reservas WHERE id = %s FOR UPDATE',
                (id,),
            )
            reserva = cursor.fetchone()

            if not reserva:
                return None, 'not_found'
            if reserva['estado'] != 'pendiente':
                return reserva, 'invalid_state'

            total = reserva['total'] or 0
            saldo_pendiente = max(float(total) - float(anticipo), 0)

            habitaciones = self._habitaciones_de(cursor, id)

            cursor.execute(
                """
                UPDATE reservas
                SET estado = 'confirmada', anticipo = %s, saldo_pendiente = %s
                WHERE id = %s
                """,
                (anticipo, saldo_pendiente, id),
            )

            for habitacion_id in habitaciones:
                self.recalcular_estado_habitacion(habitacion_id, cursor)

            conn.commit()
            return self.get_by_id(id), 'ok'

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # ─── §6.4 CHECK-IN Y CHECK-OUT ATÓMICOS ───────────────────────────────────

    def checkin(self, id, empleado_id=None):
        """
        Check-in en una sola transacción: valida el estado, valida que la fecha
        de entrada ya llegó (antes sólo lo validaba el navegador, F22), valida
        que la habitación no arrastre otro check-in sin cerrar (F23), y deja
        reserva='checkin' y habitación='ocupada'.

        Devuelve `(reserva, estado)` donde estado es uno de: 'ok', 'not_found',
        'invalid_state', 'fecha_futura', 'habitacion_ocupada', 'sin_habitacion'.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                """
                SELECT id, estado, fecha_entrada, fecha_salida
                FROM reservas WHERE id = %s FOR UPDATE
                """,
                (id,),
            )
            reserva = cursor.fetchone()
            if not reserva:
                return None, 'not_found'

            if reserva['estado'] != 'confirmada':
                return None, 'invalid_state'

            if a_fecha(reserva['fecha_entrada']) > hoy_local():
                return None, 'fecha_futura'

            habitaciones = self._habitaciones_de(cursor, id)
            if not habitaciones:
                return None, 'sin_habitacion'

            for habitacion_id in habitaciones:
                self._bloquear_habitacion(cursor, habitacion_id)

                # F23: otra reserva sigue con el huésped dentro de esa habitación.
                cursor.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM reservas r
                    JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
                    WHERE rh.habitacion_id = %s
                      AND r.estado = 'checkin'
                      AND r.id != %s
                    """,
                    (habitacion_id, id),
                )
                if cursor.fetchone()['cnt'] > 0:
                    return None, 'habitacion_ocupada'

            cursor.execute(
                "UPDATE reservas SET estado = 'checkin' WHERE id = %s", (id,)
            )
            for habitacion_id in habitaciones:
                cursor.execute(
                    "UPDATE habitaciones SET estado = 'ocupada' WHERE id = %s",
                    (habitacion_id,),
                )
                if empleado_id:
                    cursor.execute(
                        """
                        UPDATE reserva_habitaciones
                        SET recepcionista_llegada_id = %s
                        WHERE reserva_id = %s AND habitacion_id = %s
                        """,
                        (empleado_id, id, habitacion_id),
                    )

            conn.commit()
            return self.get_by_id(id), 'ok'

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def checkout(self, id, empleado_id=None, forzar=False, motivo=None):
        """
        Check-out en una sola transacción.

        Antes eran dos llamadas sueltas desde el navegador con los fallos
        silenciados en un `console.warn`: si la segunda fallaba, la habitación
        quedaba 'ocupada' con la reserva ya cerrada. Y no se miraba el saldo,
        así que se podía cerrar una reserva con deuda (F27).

        Con `forzar=True` (permiso `checkout.forzar`) se cierra con saldo
        pendiente, pero queda registrado quién lo hizo, cuándo y por cuánto.

        Devuelve `(reserva, estado, saldo)`; estado puede ser 'ok',
        'not_found', 'invalid_state' o 'saldo_pendiente'.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                'SELECT id, estado FROM reservas WHERE id = %s FOR UPDATE', (id,)
            )
            reserva = cursor.fetchone()
            if not reserva:
                return None, 'not_found', None

            if reserva['estado'] != 'checkin':
                return None, 'invalid_state', None

            financiero = calcular_saldo(cursor, id)
            saldo = financiero['saldo_pendiente']

            if saldo > 0 and not forzar:
                return None, 'saldo_pendiente', saldo

            habitaciones = self._habitaciones_de(cursor, id)

            if saldo > 0:
                cursor.execute(
                    """
                    UPDATE reservas
                    SET estado = 'checkout',
                        checkout_forzado_por    = %s,
                        checkout_forzado_en     = NOW(),
                        checkout_forzado_motivo = %s,
                        checkout_saldo_forzado  = %s
                    WHERE id = %s
                    """,
                    (empleado_id, (motivo or 'Sin motivo registrado')[:255],
                     saldo, id),
                )
            else:
                cursor.execute(
                    "UPDATE reservas SET estado = 'checkout' WHERE id = %s", (id,)
                )

            # Todas las habitaciones pasan a mantenimiento en la MISMA
            # transacción: o se mueven todas, o no se mueve ninguna.
            for habitacion_id in habitaciones:
                cursor.execute(
                    "UPDATE habitaciones SET estado = 'mantenimiento' WHERE id = %s",
                    (habitacion_id,),
                )
                if empleado_id:
                    cursor.execute(
                        """
                        UPDATE reserva_habitaciones
                        SET recepcionista_salida_id = %s
                        WHERE reserva_id = %s AND habitacion_id = %s
                        """,
                        (empleado_id, id, habitacion_id),
                    )

            conn.commit()
            return self.get_by_id(id), 'ok', saldo

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def cancelar(self, id, motivo=None, empleado_id=None, forzar=False):
        """
        §6.3 — Cancela una reserva.

        F25: cancelar una reserva con pagos registrados o con el check-in ya
        hecho exige `forzar=True` (permiso `reservas.forzar_estado`) y un
        motivo, que queda escrito en las observaciones.

        Devuelve `(reserva, estado)`; estado puede ser 'ok', 'not_found',
        'invalid_state', 'tiene_pagos'.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                'SELECT id, estado, observaciones FROM reservas WHERE id = %s FOR UPDATE',
                (id,),
            )
            reserva = cursor.fetchone()
            if not reserva:
                return None, 'not_found'

            if reserva['estado'] in ('cancelada', 'checkout'):
                return None, 'invalid_state'

            cursor.execute(
                """
                SELECT COALESCE(SUM(monto), 0) AS pagado
                FROM pagos WHERE reserva_id = %s AND anulado = 0
                """,
                (id,),
            )
            pagado = float(cursor.fetchone()['pagado'] or 0)
            hizo_checkin = reserva['estado'] == 'checkin'

            if (pagado > 0 or hizo_checkin) and not forzar:
                return None, 'tiene_pagos'

            nota = f'[CANCELACIÓN {hoy_local().isoformat()}] {motivo or "Sin motivo"}'
            if pagado > 0:
                nota += f' | Pagos registrados: {pagado:.2f}'
            if empleado_id:
                nota += f' | Operador ID: {empleado_id}'
            observaciones = ((reserva['observaciones'] or '') + '\n' + nota).strip()

            habitaciones = self._habitaciones_de(cursor, id)

            cursor.execute(
                "UPDATE reservas SET estado = 'cancelada', observaciones = %s WHERE id = %s",
                (observaciones, id),
            )
            for habitacion_id in habitaciones:
                self.recalcular_estado_habitacion(habitacion_id, cursor)

            conn.commit()
            return self.get_by_id(id), 'ok'

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def delete(self, id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            conn.start_transaction()
            cursor.execute(
                'SELECT habitacion_id FROM reserva_habitaciones WHERE reserva_id = %s FOR UPDATE',
                (id,),
            )
            habitaciones = [row[0] for row in cursor.fetchall()]

            ConsumoModel().delete_by_reserva(id, cursor)
            cursor.execute('DELETE FROM reserva_habitaciones WHERE reserva_id = %s', (id,))
            cursor.execute('DELETE FROM reservas WHERE id = %s', (id,))
            afectadas = cursor.rowcount

            for habitacion_id in habitaciones:
                self.recalcular_estado_habitacion(habitacion_id, cursor)

            conn.commit()
            return afectadas
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # ─── HABITACIONES DE LA RESERVA ───────────────────────────────────────────

    def get_habitaciones(self, reserva_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT rh.*, rh.id AS reserva_habitacion_id,
                       h.numero, h.piso, h.tipo_cama,
                       h.estado AS habitacion_estado,
                       t.nombre AS tipo_nombre
                FROM reserva_habitaciones rh
                JOIN habitaciones h ON rh.habitacion_id = h.id
                JOIN tipos_habitacion t ON h.tipo_id = t.id
                WHERE rh.reserva_id = %s
                ORDER BY h.piso, h.numero
                """,
                (reserva_id,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def agregar_habitacion(self, reserva_id, data):
        """
        Agrega una habitación a una reserva existente, validando solapamiento
        con las fechas de la reserva padre y recalculando el total.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                'SELECT fecha_entrada, fecha_salida, estado FROM reservas WHERE id = %s FOR UPDATE',
                (reserva_id,),
            )
            reserva = cursor.fetchone()
            if not reserva:
                raise ValueError('reserva_no_encontrada')

            fecha_entrada = reserva['fecha_entrada']
            fecha_salida  = reserva['fecha_salida']
            habitacion_id = data['habitacion_id']

            if not fecha_entrada or not fecha_salida or fecha_entrada >= fecha_salida:
                raise ValueError('fechas_invalidas')

            habitacion = self._bloquear_habitacion(cursor, habitacion_id)
            if not habitacion:
                raise ValueError('habitacion_no_encontrada')

            if self._tiene_solapamiento(cursor, habitacion_id,
                                        fecha_entrada, fecha_salida,
                                        excluir_reserva_id=reserva_id):
                raise ValueError('solapamiento_fechas')

            precio_noche = data.get('precio_noche')
            if precio_noche in (None, '', 0):
                cursor.execute(
                    """
                    SELECT t.precio_base
                    FROM habitaciones h
                    JOIN tipos_habitacion t ON t.id = h.tipo_id
                    WHERE h.id = %s
                    """,
                    (habitacion_id,),
                )
                fila = cursor.fetchone()
                precio_noche = fila['precio_base'] if fila else 0

            cursor.execute(
                """
                INSERT INTO reserva_habitaciones
                    (reserva_id, habitacion_id, precio_noche)
                VALUES (%s, %s, %s)
                """,
                (reserva_id, habitacion_id, precio_noche),
            )
            nuevo_id = cursor.lastrowid

            self._recalcular_total(cursor, reserva_id)
            self.recalcular_estado_habitacion(habitacion_id, cursor)

            conn.commit()
            return nuevo_id

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def quitar_habitacion(self, reserva_id, habitacion_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            conn.start_transaction()
            cursor.execute(
                'DELETE FROM reserva_habitaciones WHERE reserva_id = %s AND habitacion_id = %s',
                (reserva_id, habitacion_id),
            )
            afectadas = cursor.rowcount
            self._recalcular_total(cursor, reserva_id)
            self.recalcular_estado_habitacion(habitacion_id, cursor)
            conn.commit()
            return afectadas
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def recalcular_estado_habitacion(self, habitacion_id, cursor=None):
        """
        Deriva el estado de una habitación de las reservas que la usan.

        §6.3 / F28: la regla "si la habitación tiene reservas futuras,
        'disponible' se convierte en 'reservada'" la decidía el cliente en dos
        pasos. Ahora la resuelve el servidor.

        No pisa 'mantenimiento' ni 'bloqueada': esos son estados operativos que
        fija una persona y sólo una persona los quita.
        """
        propio = cursor is None
        conn = None
        try:
            if propio:
                conn = get_connection()
                cursor = conn.cursor()

            cursor.execute('SELECT estado FROM habitaciones WHERE id = %s',
                           (habitacion_id,))
            fila = cursor.fetchone()
            if not fila:
                return None
            estado_actual = fila['estado'] if isinstance(fila, dict) else fila[0]

            if estado_actual in ('mantenimiento', 'bloqueada'):
                return estado_actual

            cursor.execute(
                """
                SELECT r.estado, r.fecha_entrada
                FROM reservas r
                JOIN reserva_habitaciones rh ON r.id = rh.reserva_id
                WHERE rh.habitacion_id = %s
                  AND r.estado IN ('pendiente', 'confirmada', 'checkin')
                """,
                (habitacion_id,),
            )
            filas = cursor.fetchall()
            estados = [
                (f['estado'] if isinstance(f, dict) else f[0]) for f in filas
            ]

            if 'checkin' in estados:
                estado_final = 'ocupada'
            elif estados:
                estado_final = 'reservada'
            else:
                estado_final = 'disponible'

            cursor.execute('UPDATE habitaciones SET estado = %s WHERE id = %s',
                           (estado_final, habitacion_id))
            if propio:
                conn.commit()
            return estado_final
        finally:
            if propio and cursor:
                cursor.close()
            if conn:
                conn.close()

    def tiene_reservas_futuras(self, habitacion_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM reservas r
                JOIN reserva_habitaciones rh ON r.id = rh.reserva_id
                WHERE rh.habitacion_id = %s
                  AND r.estado IN ('confirmada', 'pendiente')
                  AND r.fecha_entrada > CURDATE()
                """,
                (habitacion_id,),
            )
            return cursor.fetchone()[0] > 0
        finally:
            cursor.close()
            conn.close()

    # ─── §6.5 EXTENSIÓN DE ESTADÍA ────────────────────────────────────────────

    def extender_dias(self, id, dias_extra, precio_noche_override=None,
                      permite_precio_especial=False):
        """
        Extiende la estadía recalculando total y saldo en el servidor.

        F13: antes el precio por noche lo tecleaba el usuario sin techo ni piso.
        Ahora el precio por defecto sale de lo ya pactado en la reserva, y un
        precio distinto sólo se acepta dentro de ±30 % de ese valor, salvo que
        quien llama tenga el permiso `reservas.precio_especial`.

        Devuelve `(resultado, estado)`.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                """
                SELECT r.*, COALESCE(SUM(rh.precio_noche), 0) AS precio_noche_total
                FROM reservas r
                LEFT JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
                WHERE r.id = %s
                GROUP BY r.id
                FOR UPDATE
                """,
                (id,),
            )
            reserva = cursor.fetchone()

            if not reserva:
                return None, 'not_found'
            if reserva.get('estado') != 'checkin':
                return None, 'invalid_state'

            fecha_salida_actual = reserva.get('fecha_salida')
            if fecha_salida_actual is None:
                return None, 'invalid_date'

            nueva_fecha_salida = fecha_salida_actual + timedelta(days=int(dias_extra))

            precio_pactado = float(reserva.get('precio_noche_total') or 0)
            if precio_noche_override is None:
                precio_noche = precio_pactado
            else:
                precio_noche = float(precio_noche_override)
                if not permite_precio_especial and precio_pactado > 0:
                    minimo = precio_pactado * 0.70
                    maximo = precio_pactado * 1.30
                    if not (minimo <= precio_noche <= maximo):
                        return {
                            'precio_pactado': precio_pactado,
                            'minimo': round(minimo, 2),
                            'maximo': round(maximo, 2),
                        }, 'precio_fuera_de_rango'

            if precio_noche <= 0:
                return None, 'missing_price'

            for habitacion_id in self._habitaciones_de(cursor, id):
                self._bloquear_habitacion(cursor, habitacion_id)
                if self._tiene_solapamiento(cursor, habitacion_id,
                                            fecha_salida_actual,
                                            nueva_fecha_salida,
                                            excluir_reserva_id=id):
                    return None, 'date_conflict'

            costo_extra = precio_noche * int(dias_extra)
            nuevo_total = float(reserva.get('total') or 0) + costo_extra

            cursor.execute(
                'UPDATE reservas SET fecha_salida = %s, total = %s WHERE id = %s',
                (nueva_fecha_salida, nuevo_total, id),
            )

            financiero = calcular_saldo(cursor, id)
            cursor.execute(
                'UPDATE reservas SET saldo_pendiente = %s WHERE id = %s',
                (financiero['saldo_pendiente'], id),
            )

            conn.commit()
            return {
                'nueva_fecha_salida': nueva_fecha_salida.isoformat(),
                'precio_noche_aplicado': precio_noche,
                'costo_extra': costo_extra,
                'total': nuevo_total,
                'saldo_pendiente': financiero['saldo_pendiente'],
                'estado_pago': financiero['estado_pago'],
                'reserva': self.get_by_id(id),
            }, 'ok'

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # ─── CAMBIO DE HABITACIÓN ─────────────────────────────────────────────────

    def cambiar_habitacion(self, reserva_id, nueva_habitacion_id,
                           motivo, empleado_id=None):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                """
                SELECT r.*, COALESCE(SUM(rh.precio_noche), 0) AS precio_noche_total
                FROM reservas r
                LEFT JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
                WHERE r.id = %s
                GROUP BY r.id
                FOR UPDATE
                """,
                (reserva_id,),
            )
            reserva = cursor.fetchone()

            if not reserva:
                return None, 'not_found'
            if reserva.get('estado') != 'checkin':
                return None, 'invalid_state'

            cursor.execute(
                """
                SELECT rh.id, rh.habitacion_id, rh.precio_noche,
                       h.numero AS numero_origen, h.notas_mantenimiento
                FROM reserva_habitaciones rh
                JOIN habitaciones h ON h.id = rh.habitacion_id
                WHERE rh.reserva_id = %s
                LIMIT 1
                """,
                (reserva_id,),
            )
            rh_actual = cursor.fetchone()
            if not rh_actual:
                return None, 'no_room_linked'

            habitacion_origen_id = rh_actual['habitacion_id']
            if habitacion_origen_id == nueva_habitacion_id:
                return None, 'same_room'

            self._bloquear_habitacion(cursor, nueva_habitacion_id)
            cursor.execute(
                """
                SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
                FROM habitaciones h
                JOIN tipos_habitacion t ON t.id = h.tipo_id
                WHERE h.id = %s
                """,
                (nueva_habitacion_id,),
            )
            destino = cursor.fetchone()

            if not destino:
                return None, 'dest_not_found'
            if destino['estado'] in ('ocupada', 'mantenimiento', 'bloqueada'):
                return None, 'dest_not_available'

            if self._tiene_solapamiento(cursor, nueva_habitacion_id,
                                        reserva['fecha_entrada'],
                                        reserva['fecha_salida'],
                                        excluir_reserva_id=reserva_id):
                return None, 'date_conflict'

            cursor.execute(
                'UPDATE reserva_habitaciones SET habitacion_id = %s WHERE id = %s',
                (nueva_habitacion_id, rh_actual['id']),
            )

            nota = f'[CAMBIO HAB {hoy_local().isoformat()}] {motivo}'
            notas_finales = ((rh_actual.get('notas_mantenimiento') or '')
                             + '\n' + nota).strip()

            cursor.execute(
                """
                UPDATE habitaciones
                SET estado = 'mantenimiento', notas_mantenimiento = %s
                WHERE id = %s
                """,
                (notas_finales, habitacion_origen_id),
            )
            cursor.execute(
                "UPDATE habitaciones SET estado = 'ocupada' WHERE id = %s",
                (nueva_habitacion_id,),
            )

            obs_nueva = (
                f'[CAMBIO HAB {hoy_local().isoformat()}] '
                f"Hab {rh_actual['numero_origen']} → Hab {destino['numero']}. "
                f'Motivo: {motivo}. Operador ID: {empleado_id or "N/A"}'
            )
            obs_final = ((reserva.get('observaciones') or '')
                         + '\n' + obs_nueva).strip()

            cursor.execute(
                'UPDATE reservas SET observaciones = %s WHERE id = %s',
                (obs_final, reserva_id),
            )

            conn.commit()
            return {
                'reserva_id':            reserva_id,
                'habitacion_origen_id':  habitacion_origen_id,
                'habitacion_origen':     rh_actual['numero_origen'],
                'habitacion_destino_id': nueva_habitacion_id,
                'habitacion_destino':    destino['numero'],
                'motivo':                motivo,
                'empleado_id':           empleado_id,
                'observaciones':         obs_final,
            }, 'ok'

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def get_habitaciones_para_cambio(self, reserva_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT r.fecha_entrada, r.fecha_salida,
                       rh.habitacion_id AS hab_actual_id
                FROM reservas r
                JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
                WHERE r.id = %s
                LIMIT 1
                """,
                (reserva_id,),
            )
            info = cursor.fetchone()
            if not info:
                return []

            marcadores = ', '.join(['%s'] * len(ESTADOS_BLOQUEAN))
            cursor.execute(
                f"""
                SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
                FROM habitaciones h
                JOIN tipos_habitacion t ON t.id = h.tipo_id
                WHERE h.id != %s
                  AND h.estado NOT IN ('mantenimiento', 'bloqueada', 'ocupada')
                  AND NOT EXISTS (
                      SELECT 1
                      FROM reserva_habitaciones rh2
                      JOIN reservas r2 ON r2.id = rh2.reserva_id
                      WHERE rh2.habitacion_id = h.id
                        AND r2.id != %s
                        AND r2.estado IN ({marcadores})
                        AND r2.fecha_entrada < %s
                        AND r2.fecha_salida  > %s
                  )
                ORDER BY h.piso, h.numero
                """,
                (info['hab_actual_id'], reserva_id, *ESTADOS_BLOQUEAN,
                 info['fecha_salida'], info['fecha_entrada']),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
