"""
§4.2 y §4.4 — Pagos.

El cambio de fondo: el navegador ya no dice cuánto se cobra. Envía la
intención ("cobrar esta reserva en efectivo") y el servidor calcula el importe
a partir de la fórmula única de `finanzas_model`.

    ANTES  POST /pagos  {"reserva_id": 42, "monto": 1850000, "empleado_id": 7}
                                   calculado en el navegador ↑   ↑ de localStorage

    AHORA  POST /pagos  {"reserva_id": 42, "metodo": "efectivo"}
                          el servidor calcula el monto y toma el empleado del JWT
"""
from decimal import Decimal

import mysql.connector

from Models.finanzas_model import CERO, calcular_saldo
from database import get_connection
from utils.fechas import a_datetime_local, marcar_local, rango_del_dia

# Métodos aceptados: el ENUM de la columna `pagos.metodo`.
METODOS_VALIDOS = (
    'efectivo', 'tarjeta_debito', 'tarjeta_credito', 'transferencia',
    'nequi', 'daviplata', 'consignacion', 'cxc', 'credito', 'otro', 'canje',
)


class SaldoInsuficiente(Exception):
    """Se intentó cobrar más de lo que se debe, o cobrar una reserva saldada."""

    def __init__(self, codigo, saldo, mensaje):
        self.codigo = codigo
        self.saldo = saldo
        super().__init__(mensaje)


class PagoModel:

    # ─── LECTURA ──────────────────────────────────────────────────────────────

    def _marcar_fechas(self, filas):
        """
        Etiqueta `fecha_pago` como hora de Bogotá para que salga con el desfase
        explícito (`-05:00`) y el frontend no tenga que adivinar (§2.4).
        """
        for fila in filas or []:
            if fila.get('fecha_pago') is not None:
                fila['fecha_pago'] = marcar_local(fila['fecha_pago'])
        return filas

    def buscar(self, *, reserva_id=None, desde=None, hasta=None,
               incluir_anulados=False, limite=100, offset=0):
        """
        §4.4 — `GET /pagos` con filtros y paginación.

        Antes devolvía el historial COMPLETO de pagos del hotel, y el hook
        `useReservaPagada` lo descargaba entero sólo para saber si UNA reserva
        estaba saldada: cada empleado veía todos los pagos del negocio y el
        coste crecía sin límite.

        `desde` y `hasta` son días calendario de Bogotá, inclusive ambos.
        Devuelve `(filas, total)`.
        """
        condiciones = []
        params = []

        if reserva_id is not None:
            condiciones.append('p.reserva_id = %s')
            params.append(reserva_id)

        if not incluir_anulados:
            condiciones.append('p.anulado = 0')

        if desde:
            inicio, _ = rango_del_dia(desde)
            condiciones.append('p.fecha_pago >= %s')
            params.append(inicio)

        if hasta:
            _, fin = rango_del_dia(hasta)
            condiciones.append('p.fecha_pago < %s')
            params.append(fin)

        where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ''

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(f'SELECT COUNT(*) AS cnt FROM pagos p {where}', params)
            total = cursor.fetchone()['cnt']

            cursor.execute(
                f"""
                SELECT p.*,
                       CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
                FROM pagos p
                LEFT JOIN empleados e ON p.empleado_id = e.id
                {where}
                ORDER BY p.fecha_pago DESC, p.id DESC
                LIMIT %s OFFSET %s
                """,
                [*params, int(limite), int(offset)],
            )
            return self._marcar_fechas(cursor.fetchall()), total
        finally:
            cursor.close()
            conn.close()

    def get_by_reserva(self, reserva_id, incluir_anulados=False):
        filas, _ = self.buscar(reserva_id=reserva_id,
                               incluir_anulados=incluir_anulados,
                               limite=1000)
        return filas

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT p.*,
                       CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
                FROM pagos p
                LEFT JOIN empleados e ON p.empleado_id = e.id
                WHERE p.id = %s
                """,
                (id,),
            )
            fila = cursor.fetchone()
            self._marcar_fechas([fila] if fila else [])
            return fila
        finally:
            cursor.close()
            conn.close()

    def get_by_fecha(self, fecha, incluir_anulados=False):
        """
        Pagos de un día calendario de Bogotá. Usa un rango [inicio, fin) en vez
        de `DATE(fecha_pago) = ...` para que el índice sirva y para que el
        corte del día sea el local (F16).
        """
        filas, _ = self.buscar(desde=fecha, hasta=fecha,
                               incluir_anulados=incluir_anulados, limite=1000)
        return filas

    def get_total_by_reserva(self, reserva_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT %s AS reserva_id,
                       COALESCE(SUM(monto), 0) AS total_pagado,
                       COUNT(id) AS num_pagos
                FROM pagos
                WHERE reserva_id = %s AND anulado = 0
                """,
                (reserva_id, reserva_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

    # ─── §4.2 REGISTRO DE PAGO ────────────────────────────────────────────────

    def registrar(self, reserva_id, empleado_id, *, metodo='efectivo',
                  monto=None, referencia=None, notas=None, fecha_pago=None):
        """
        Registra un pago dentro de una transacción, con la reserva bloqueada.

        Reglas (§4.2):
          1. Si `monto` no viene, se cobra el `saldo_pendiente` completo que
             calcula el servidor.
          2. Si `monto` viene, debe cumplir `0 < monto <= saldo_pendiente`.
          3. `empleado_id` sale del JWT; nunca del body.
          4. Si el saldo ya es 0, no se crea un pago de $0.
          5. `SELECT ... FOR UPDATE` sobre la reserva: dos cajeros simultáneos
             no pueden cobrar dos veces el mismo saldo.
          6. Los consumos que el pago alcanza a cubrir quedan marcados como
             'cancelado' apuntando a ESTE pago (§4.3).

        Devuelve `(pago, financiero)` con el estado nuevo de la reserva.
        """
        if metodo not in METODOS_VALIDOS:
            raise ValueError('metodo_invalido')

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            financiero = calcular_saldo(cursor, reserva_id, bloquear=True)
            if financiero is None:
                raise ValueError('reserva_no_encontrada')

            saldo = financiero['saldo_pendiente']

            if saldo <= CERO:
                raise SaldoInsuficiente(
                    'RESERVA_SALDADA', saldo,
                    'La reserva ya está saldada; no hay nada que cobrar',
                )

            if monto is None:
                monto_final = saldo
            else:
                monto_final = Decimal(str(monto))
                if monto_final <= CERO:
                    raise SaldoInsuficiente(
                        'MONTO_INVALIDO', saldo,
                        'El monto del pago debe ser mayor que 0',
                    )
                if monto_final > saldo:
                    raise SaldoInsuficiente(
                        'ABONO_EXCEDE_SALDO', saldo,
                        f'El abono no puede superar el saldo pendiente de ${saldo:,.2f}',
                    )

            momento = a_datetime_local(fecha_pago)

            if momento is None:
                cursor.execute(
                    """
                    INSERT INTO pagos
                        (reserva_id, empleado_id, monto, metodo, referencia, notas)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (reserva_id, empleado_id, monto_final, metodo,
                     referencia, notas),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO pagos
                        (reserva_id, empleado_id, monto, metodo, referencia,
                         notas, fecha_pago)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (reserva_id, empleado_id, monto_final, metodo,
                     referencia, notas, momento),
                )

            pago_id = cursor.lastrowid

            # §4.3: los consumos que este pago cubre quedan saldados y con
            # traza hacia el pago. Sin esto, marcarlos "pagados" hacía
            # desaparecer el dinero de la contabilidad.
            self._saldar_consumos(cursor, reserva_id, monto_final, pago_id)

            nuevo = calcular_saldo(cursor, reserva_id)
            cursor.execute(
                'UPDATE reservas SET saldo_pendiente = %s WHERE id = %s',
                (nuevo['saldo_pendiente'], reserva_id),
            )

            conn.commit()

            return self.get_by_id(pago_id), nuevo

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def _saldar_consumos(self, cursor, reserva_id, monto, pago_id):
        """
        Marca como 'cancelado' los consumos pendientes que el importe alcanza a
        cubrir, del más antiguo al más nuevo, y los liga al pago.

        Un consumo sólo puede salir del saldo por esta vía: siempre queda un
        registro en `pagos` detrás.
        """
        cursor.execute(
            """
            SELECT c.id, c.total
            FROM consumos c
            JOIN reserva_habitaciones rh ON rh.id = c.reserva_habitacion_id
            WHERE rh.reserva_id = %s AND c.estado <> 'cancelado'
            ORDER BY c.fecha ASC, c.id ASC
            """,
            (reserva_id,),
        )
        restante = Decimal(str(monto))
        for consumo in cursor.fetchall():
            valor = Decimal(str(consumo['total'] or 0))
            if valor > restante:
                break
            cursor.execute(
                "UPDATE consumos SET estado = 'cancelado', pago_id = %s WHERE id = %s",
                (pago_id, consumo['id']),
            )
            restante -= valor

    # ─── §4.2 EDICIÓN Y ANULACIÓN ─────────────────────────────────────────────

    def actualizar_datos(self, id, data):
        """
        F17 — Sólo se pueden editar los datos descriptivos del pago.

        `monto`, `reserva_id` y `empleado_id` se ignoran aunque vengan en el
        body: corregir un importe es una anulación más un pago nuevo, con
        traza, no una edición silenciosa.
        """
        campos = []
        valores = []

        if 'metodo' in data:
            if data['metodo'] not in METODOS_VALIDOS:
                raise ValueError('metodo_invalido')
            campos.append('metodo = %s')
            valores.append(data['metodo'])

        for campo in ('referencia', 'notas'):
            if campo in data:
                campos.append(f'{campo} = %s')
                valores.append(data[campo])

        if 'fecha_pago' in data:
            campos.append('fecha_pago = %s')
            valores.append(a_datetime_local(data['fecha_pago']))

        if not campos:
            return 0

        valores.append(id)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"UPDATE pagos SET {', '.join(campos)} WHERE id = %s AND anulado = 0",
                valores,
            )
            conn.commit()
            return cursor.rowcount
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def anular(self, id, empleado_id, motivo):
        """
        Anula un pago sin borrarlo: la fila queda con `anulado = 1`, quién lo
        anuló, cuándo y por qué. Los consumos que ese pago había saldado
        vuelven a 'pendiente' y el saldo de la reserva se recalcula.

        Devuelve `(pago, financiero)` o `(None, None)` si no existe o ya estaba
        anulado.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                'SELECT id, reserva_id, anulado FROM pagos WHERE id = %s FOR UPDATE',
                (id,),
            )
            pago = cursor.fetchone()
            if not pago or pago['anulado']:
                conn.rollback()
                return None, None

            reserva_id = pago['reserva_id']

            cursor.execute(
                """
                UPDATE pagos
                SET anulado = 1, anulado_por = %s, anulado_en = NOW(),
                    motivo_anulacion = %s
                WHERE id = %s
                """,
                (empleado_id, (motivo or 'Sin motivo registrado')[:255], id),
            )

            cursor.execute(
                "UPDATE consumos SET estado = 'pendiente', pago_id = NULL WHERE pago_id = %s",
                (id,),
            )

            financiero = calcular_saldo(cursor, reserva_id)
            cursor.execute(
                'UPDATE reservas SET saldo_pendiente = %s WHERE id = %s',
                (financiero['saldo_pendiente'], reserva_id),
            )

            conn.commit()
            return self.get_by_id(id), financiero

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def delete(self, id):
        """
        Borrado físico. Se conserva para administración, pero la vía normal
        para deshacer un cobro es `anular()`, que deja traza.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()
            cursor.execute('SELECT reserva_id FROM pagos WHERE id = %s', (id,))
            pago = cursor.fetchone()
            if not pago:
                conn.rollback()
                return 0

            cursor.execute(
                "UPDATE consumos SET estado = 'pendiente', pago_id = NULL WHERE pago_id = %s",
                (id,),
            )
            cursor.execute('DELETE FROM pagos WHERE id = %s', (id,))
            afectadas = cursor.rowcount

            financiero = calcular_saldo(cursor, pago['reserva_id'])
            if financiero:
                cursor.execute(
                    'UPDATE reservas SET saldo_pendiente = %s WHERE id = %s',
                    (financiero['saldo_pendiente'], pago['reserva_id']),
                )

            conn.commit()
            return afectadas
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
