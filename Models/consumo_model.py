"""
§4.3 — El estado de un consumo es derivado, nunca lo fija el cliente.

Antes había una casilla en la interfaz ("Marcar como pagado") que escribía
directamente `estado: 'cancelado'` en el consumo, sin ningún pago detrás. Un
consumo 'cancelado' sale del saldo a cobrar pero no entra a caja: era dinero
que desaparecía sin dejar rastro contable.

Ahora:
  * Todo consumo nace 'pendiente'. `create()` ignora el `estado` del cliente.
  * Un consumo sólo pasa a 'cancelado' desde `PagoModel.registrar()`, que lo
    liga al pago que lo cubrió (`consumos.pago_id`).
  * Para el caso "el huésped paga la cerveza en el momento" existe
    `cobrar()`, que crea el pago y marca el consumo en la MISMA transacción.
"""
from decimal import Decimal

import mysql.connector

from database import get_connection
from utils.fechas import a_fecha, hoy_local

ESTADOS = ('pendiente', 'cancelado')


class ConsumoModel:

    # ─── LECTURA ──────────────────────────────────────────────────────────────

    def get_by_reserva(self, reserva_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT c.*, tc.nombre AS tipo_nombre, tc.categoria,
                       h.numero AS habitacion_numero,
                       rh.reserva_id
                FROM consumos c
                JOIN tipos_consumo tc ON c.tipo_consumo_id = tc.id
                JOIN reserva_habitaciones rh ON c.reserva_habitacion_id = rh.id
                JOIN habitaciones h ON rh.habitacion_id = h.id
                WHERE rh.reserva_id = %s
                ORDER BY c.fecha DESC, c.id DESC
                """,
                (reserva_id,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT c.*, tc.nombre AS tipo_nombre, tc.categoria,
                       h.numero AS habitacion_numero,
                       rh.reserva_id
                FROM consumos c
                JOIN tipos_consumo tc ON c.tipo_consumo_id = tc.id
                JOIN reserva_habitaciones rh ON c.reserva_habitacion_id = rh.id
                JOIN habitaciones h ON rh.habitacion_id = h.id
                WHERE c.id = %s
                """,
                (id,),
            )
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

    def get_by_fecha(self, fecha):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT c.*, tc.nombre AS tipo_nombre, tc.categoria,
                       h.numero AS habitacion_numero,
                       rh.reserva_id
                FROM consumos c
                JOIN tipos_consumo tc ON c.tipo_consumo_id = tc.id
                JOIN reserva_habitaciones rh ON c.reserva_habitacion_id = rh.id
                JOIN habitaciones h ON rh.habitacion_id = h.id
                WHERE c.fecha = %s
                ORDER BY c.id DESC
                """,
                (a_fecha(fecha),),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_tipos_consumo(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                'SELECT * FROM tipos_consumo WHERE activo = 1 ORDER BY categoria, nombre'
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    # ─── ESCRITURA ────────────────────────────────────────────────────────────

    def _precio_de_catalogo(self, cursor, tipo_consumo_id):
        """
        F15 — Precio de referencia para el tipo de consumo: el precio unitario
        más frecuente de los productos de inventario ligados a ese tipo. Sirve
        para detectar precios inventados, no para imponerlos.
        Devuelve None si no hay referencia.
        """
        cursor.execute(
            """
            SELECT precio_unitario
            FROM productos_inventario
            WHERE tipo_consumo_id = %s AND activo = 1 AND precio_unitario > 0
            ORDER BY precio_unitario
            LIMIT 1
            """,
            (tipo_consumo_id,),
        )
        fila = cursor.fetchone()
        if not fila:
            return None
        return Decimal(str(fila['precio_unitario'] if isinstance(fila, dict) else fila[0]))

    def create(self, data, empleado_id=None, cursor=None, pago_id=None,
               estado='pendiente'):
        """
        Crea un consumo. SIEMPRE nace 'pendiente' salvo que lo llame el propio
        flujo de cobro pasando el `pago_id` que lo respalda.

        `total` lo calcula el servidor: cantidad × precio_unitario.
        `empleado_id` viene del JWT, no del body.

        Puede recibir un `cursor` externo para participar en la transacción de
        quien lo llama (así lo usa `InventarioModel.consumo_habitacion`).
        """
        if estado == 'cancelado' and pago_id is None:
            # Blindaje: nadie marca un consumo pagado sin un pago detrás.
            raise ValueError('consumo_cancelado_sin_pago')

        propio = cursor is None
        conn = None
        try:
            if propio:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                conn.start_transaction()

            cantidad = Decimal(str(data.get('cantidad', 1) or 1))
            precio = Decimal(str(data.get('precio_unitario', 0) or 0))
            total = cantidad * precio

            cursor.execute(
                """
                INSERT INTO consumos (
                    reserva_habitacion_id, tipo_consumo_id, descripcion,
                    cantidad, precio_unitario, total, fecha, empleado_id,
                    estado, pago_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    data['reserva_habitacion_id'],
                    data['tipo_consumo_id'],
                    data.get('descripcion'),
                    cantidad,
                    precio,
                    total,
                    a_fecha(data.get('fecha')) or hoy_local(),
                    empleado_id,
                    estado,
                    pago_id,
                ),
            )
            nuevo_id = cursor.lastrowid

            # El consumo entra al saldo de la reserva en el momento en que se
            # crea, así que la columna cacheada se actualiza con él.
            if estado != 'cancelado':
                self._refrescar_saldo(cursor, data['reserva_habitacion_id'])

            if propio:
                conn.commit()
            return nuevo_id

        except Exception:
            if propio and conn:
                conn.rollback()
            raise
        finally:
            if propio and cursor:
                cursor.close()
            if conn:
                conn.close()

    def _refrescar_saldo(self, cursor, reserva_habitacion_id):
        """Mantiene al día la columna `reservas.saldo_pendiente`."""
        from Models.finanzas_model import calcular_saldo

        cursor.execute(
            'SELECT reserva_id FROM reserva_habitaciones WHERE id = %s',
            (reserva_habitacion_id,),
        )
        fila = cursor.fetchone()
        if not fila:
            return
        reserva_id = fila['reserva_id'] if isinstance(fila, dict) else fila[0]

        financiero = calcular_saldo(cursor, reserva_id)
        if financiero:
            cursor.execute(
                'UPDATE reservas SET saldo_pendiente = %s WHERE id = %s',
                (financiero['saldo_pendiente'], reserva_id),
            )

    def cobrar(self, consumo_id, empleado_id, metodo='efectivo'):
        """
        §4.3 punto 3 — "El huésped paga la cerveza en el momento".

        Crea el pago y marca el consumo en la MISMA transacción. Es la única
        forma de que un consumo quede pagado, y siempre deja un registro en
        `/pagos`.

        Devuelve `(consumo, pago, financiero)`.
        Lanza ValueError('no_encontrado') o ValueError('ya_cobrado').
        """
        from Models.finanzas_model import calcular_saldo

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                """
                SELECT c.id, c.total, c.estado, rh.reserva_id
                FROM consumos c
                JOIN reserva_habitaciones rh ON rh.id = c.reserva_habitacion_id
                WHERE c.id = %s
                FOR UPDATE
                """,
                (consumo_id,),
            )
            consumo = cursor.fetchone()
            if not consumo:
                raise ValueError('no_encontrado')
            if consumo['estado'] == 'cancelado':
                raise ValueError('ya_cobrado')

            reserva_id = consumo['reserva_id']
            monto = Decimal(str(consumo['total'] or 0))
            if monto <= 0:
                raise ValueError('monto_invalido')

            cursor.execute(
                """
                INSERT INTO pagos
                    (reserva_id, empleado_id, monto, metodo, notas)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (reserva_id, empleado_id, monto, metodo,
                 f'Cobro directo del consumo #{consumo_id}'),
            )
            pago_id = cursor.lastrowid

            cursor.execute(
                "UPDATE consumos SET estado = 'cancelado', pago_id = %s WHERE id = %s",
                (pago_id, consumo_id),
            )

            financiero = calcular_saldo(cursor, reserva_id)
            cursor.execute(
                'UPDATE reservas SET saldo_pendiente = %s WHERE id = %s',
                (financiero['saldo_pendiente'], reserva_id),
            )

            conn.commit()

            from Models.pago_model import PagoModel
            return self.get_by_id(consumo_id), PagoModel().get_by_id(pago_id), financiero

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def update(self, id, data, empleado_id=None):
        """
        Edita un consumo pendiente. Un consumo ya cobrado no se toca: hay un
        pago apuntando a él.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                'SELECT estado, reserva_habitacion_id FROM consumos WHERE id = %s FOR UPDATE',
                (id,),
            )
            actual = cursor.fetchone()
            if not actual:
                return 0
            if actual['estado'] == 'cancelado':
                raise ValueError('consumo_ya_cobrado')

            cantidad = Decimal(str(data.get('cantidad', 1) or 1))
            precio = Decimal(str(data.get('precio_unitario', 0) or 0))

            cursor.execute(
                """
                UPDATE consumos SET
                    tipo_consumo_id = %s,
                    descripcion     = %s,
                    cantidad        = %s,
                    precio_unitario = %s,
                    total           = %s,
                    fecha           = %s,
                    empleado_id     = %s
                WHERE id = %s
                """,
                (
                    data['tipo_consumo_id'],
                    data.get('descripcion'),
                    cantidad,
                    precio,
                    cantidad * precio,
                    a_fecha(data.get('fecha')) or hoy_local(),
                    empleado_id,
                    id,
                ),
            )
            afectadas = cursor.rowcount
            self._refrescar_saldo(cursor, actual['reserva_habitacion_id'])

            conn.commit()
            return afectadas
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def delete(self, id):
        """
        Borra un consumo pendiente. Uno ya cobrado no se puede borrar sin
        anular antes el pago que lo respalda.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                'SELECT estado, reserva_habitacion_id FROM consumos WHERE id = %s FOR UPDATE',
                (id,),
            )
            actual = cursor.fetchone()
            if not actual:
                return 0
            if actual['estado'] == 'cancelado':
                raise ValueError('consumo_ya_cobrado')

            cursor.execute('DELETE FROM consumos WHERE id = %s', (id,))
            afectadas = cursor.rowcount
            self._refrescar_saldo(cursor, actual['reserva_habitacion_id'])

            conn.commit()
            return afectadas
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def delete_by_reserva(self, reserva_id, cursor=None):
        propio = cursor is None
        conn = None
        try:
            if propio:
                conn = get_connection()
                cursor = conn.cursor()
            cursor.execute(
                """
                DELETE c
                FROM consumos c
                JOIN reserva_habitaciones rh ON c.reserva_habitacion_id = rh.id
                WHERE rh.reserva_id = %s
                """,
                (reserva_id,),
            )
            afectadas = cursor.rowcount
            if propio:
                conn.commit()
            return afectadas
        except Exception:
            if propio and conn:
                conn.rollback()
            raise
        finally:
            if propio and cursor:
                cursor.close()
            if conn:
                conn.close()

    def create_dano(self, data, empleado_id=None):
        """
        Registra un daño como consumo. Igual que cualquier consumo: nace
        'pendiente' y entra al saldo del huésped.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                "SELECT id FROM tipos_consumo WHERE nombre = 'Daño' AND activo = 1"
            )
            tipo = cursor.fetchone()
            if not tipo:
                raise ValueError('tipo_dano_no_configurado')

            precio = Decimal(str(data.get('precio_unitario', 0) or 0))
            cursor.execute(
                """
                INSERT INTO consumos (
                    reserva_habitacion_id, tipo_consumo_id, descripcion,
                    cantidad, precio_unitario, total, fecha, empleado_id, estado
                ) VALUES (%s, %s, %s, 1, %s, %s, %s, %s, 'pendiente')
                """,
                (
                    data['reserva_habitacion_id'],
                    tipo['id'],
                    data.get('descripcion'),
                    precio,
                    precio,
                    a_fecha(data.get('fecha')) or hoy_local(),
                    empleado_id,
                ),
            )
            nuevo_id = cursor.lastrowid
            self._refrescar_saldo(cursor, data['reserva_habitacion_id'])

            conn.commit()
            return nuevo_id
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # Alias con el nombre original (tenía una 'ñ' en el identificador).
    create_daño = create_dano
