"""
§7.1 y §7.2 — Inventario.

Dos problemas que se arreglan aquí:

  * Descontar stock y cobrar el producto eran dos llamadas sueltas desde el
    navegador. Si la segunda fallaba, el stock ya había bajado y nadie cobraba
    el producto (F42). Ahora es un solo endpoint transaccional.

  * El frontend adivinaba a qué tipo de consumo correspondía un producto
    comparando cadenas de texto, y si no acertaba usaba el PRIMER tipo de la
    lista (F43). Eso categorizaba mal los consumos sin avisar y corrompía
    cualquier reporte por categoría. Ahora el producto declara su
    `tipo_consumo_id` y, si no lo tiene, el servidor devuelve un error
    explícito en vez de adivinar.
"""
from decimal import Decimal

import mysql.connector

from database import get_connection

TIPOS_MOVIMIENTO = ('entrada', 'salida', 'ajuste')

# Expresión del stock a partir de los movimientos. Se repite en varias
# consultas, así que vive en un solo sitio.
SQL_STOCK = """
    COALESCE(SUM(
        CASE
            WHEN m.tipo_movimiento = 'entrada' THEN  m.cantidad
            WHEN m.tipo_movimiento = 'salida'  THEN -m.cantidad
            WHEN m.tipo_movimiento = 'ajuste'  THEN  m.cantidad
        END
    ), 0)
"""


class StockInsuficiente(Exception):
    def __init__(self, disponible, pedido):
        self.disponible = disponible
        self.pedido = pedido
        super().__init__(f'stock {disponible} < {pedido}')


class InventarioModel:

    # ─── LECTURA ──────────────────────────────────────────────────────────────

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"""
                SELECT p.*, tc.nombre AS tipo_consumo_nombre,
                       {SQL_STOCK} AS stock_actual,
                       CASE WHEN {SQL_STOCK} <= p.stock_minimo
                            THEN 'REPONER' ELSE 'OK' END AS alerta
                FROM productos_inventario p
                LEFT JOIN movimientos_inventario m ON m.producto_id = p.id
                LEFT JOIN tipos_consumo tc ON tc.id = p.tipo_consumo_id
                WHERE p.activo = 1
                GROUP BY p.id
                ORDER BY p.categoria, p.nombre
                """
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
                f"""
                SELECT p.*, tc.nombre AS tipo_consumo_nombre,
                       {SQL_STOCK} AS stock_actual
                FROM productos_inventario p
                LEFT JOIN movimientos_inventario m ON m.producto_id = p.id
                LEFT JOIN tipos_consumo tc ON tc.id = p.tipo_consumo_id
                WHERE p.id = %s
                GROUP BY p.id
                """,
                (id,),
            )
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

    def get_por_reponer(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"""
                SELECT p.*, {SQL_STOCK} AS stock_actual
                FROM productos_inventario p
                LEFT JOIN movimientos_inventario m ON m.producto_id = p.id
                WHERE p.activo = 1
                GROUP BY p.id
                HAVING stock_actual <= p.stock_minimo
                ORDER BY stock_actual ASC
                """
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_movimientos(self, producto_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT m.*,
                       CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
                FROM movimientos_inventario m
                LEFT JOIN empleados e ON m.empleado_id = e.id
                WHERE m.producto_id = %s
                ORDER BY m.fecha DESC, m.id DESC
                """,
                (producto_id,),
            )
            from utils.fechas import marcar_local
            filas = cursor.fetchall()
            for fila in filas:
                fila['fecha'] = marcar_local(fila.get('fecha'))
            return filas
        finally:
            cursor.close()
            conn.close()

    def _stock_actual(self, cursor, producto_id):
        cursor.execute(
            f"""
            SELECT {SQL_STOCK} AS stock
            FROM movimientos_inventario m
            WHERE m.producto_id = %s
            """,
            (producto_id,),
        )
        fila = cursor.fetchone()
        if not fila:
            return 0
        valor = fila['stock'] if isinstance(fila, dict) else fila[0]
        return int(valor or 0)

    # ─── ESCRITURA ────────────────────────────────────────────────────────────

    def create(self, data, empleado_id=None):
        """
        F44 — Crea el producto y su stock inicial en una sola transacción.
        Antes eran dos llamadas: crear producto y registrar el movimiento.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            conn.start_transaction()

            cursor.execute(
                """
                INSERT INTO productos_inventario
                    (nombre, categoria, tipo_consumo_id, precio_unitario,
                     stock_minimo, activo)
                VALUES (%s, %s, %s, %s, %s, 1)
                """,
                (
                    data['nombre'],
                    data.get('categoria'),
                    data.get('tipo_consumo_id'),
                    data.get('precio_unitario', 0),
                    data.get('stock_minimo', 5),
                ),
            )
            nuevo_id = cursor.lastrowid

            stock_inicial = int(data.get('stock_inicial') or 0)
            if stock_inicial > 0:
                cursor.execute(
                    """
                    INSERT INTO movimientos_inventario
                        (producto_id, tipo_movimiento, cantidad, referencia,
                         empleado_id, observacion)
                    VALUES (%s, 'entrada', %s, 'stock_inicial', %s,
                            'Stock inicial al crear el producto')
                    """,
                    (nuevo_id, stock_inicial, empleado_id),
                )

            conn.commit()
            return nuevo_id
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def update(self, id, data):
        campos = []
        valores = []
        for campo in ('nombre', 'categoria', 'tipo_consumo_id',
                      'precio_unitario', 'stock_minimo', 'activo'):
            if campo in data:
                campos.append(f'{campo} = %s')
                valores.append(data[campo])

        if not campos:
            return 0

        valores.append(id)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"UPDATE productos_inventario SET {', '.join(campos)} WHERE id = %s",
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

    def delete(self, id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'UPDATE productos_inventario SET activo = 0 WHERE id = %s', (id,)
            )
            conn.commit()
            return cursor.rowcount
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def registrar_movimiento(self, data, empleado_id=None):
        """
        Movimiento suelto de inventario (entrada, ajuste, o salida que no se
        cobra a una habitación). Valida que una salida no deje el stock en
        negativo.
        """
        tipo = data.get('tipo_movimiento')
        if tipo not in TIPOS_MOVIMIENTO:
            raise ValueError('tipo_movimiento_invalido')

        cantidad = int(data.get('cantidad') or 0)
        if cantidad <= 0:
            raise ValueError('cantidad_invalida')

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                'SELECT id FROM productos_inventario WHERE id = %s FOR UPDATE',
                (data['producto_id'],),
            )
            if not cursor.fetchone():
                raise ValueError('producto_no_encontrado')

            if tipo == 'salida':
                disponible = self._stock_actual(cursor, data['producto_id'])
                if disponible < cantidad:
                    raise StockInsuficiente(disponible, cantidad)

            cursor.execute(
                """
                INSERT INTO movimientos_inventario
                    (producto_id, tipo_movimiento, cantidad, referencia,
                     empleado_id, observacion)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    data['producto_id'], tipo, cantidad,
                    data.get('referencia'), empleado_id, data.get('observacion'),
                ),
            )
            nuevo_id = cursor.lastrowid
            conn.commit()
            return nuevo_id
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # ─── §7.1 CONSUMO DE HABITACIÓN, ATÓMICO ──────────────────────────────────

    def consumo_habitacion(self, producto_id, reserva_habitacion_id, cantidad,
                           empleado_id=None):
        """
        Descuenta stock y crea el consumo en UNA transacción.

        El precio y el tipo de consumo salen del PRODUCTO, no del cliente:
        eso cierra a la vez el precio libre (F15) y la categorización a ojo
        (F43). Si el producto no tiene `tipo_consumo_id`, falla con un error
        explícito en vez de caer al primer tipo de la lista.

        Devuelve `(movimiento_id, consumo_id, producto)`.
        """
        cantidad = int(cantidad or 0)
        if cantidad <= 0:
            raise ValueError('cantidad_invalida')

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                """
                SELECT id, nombre, precio_unitario, tipo_consumo_id
                FROM productos_inventario
                WHERE id = %s AND activo = 1
                FOR UPDATE
                """,
                (producto_id,),
            )
            producto = cursor.fetchone()
            if not producto:
                raise ValueError('producto_no_encontrado')

            if not producto['tipo_consumo_id']:
                raise ValueError('producto_sin_tipo_consumo')

            cursor.execute(
                'SELECT id, reserva_id FROM reserva_habitaciones WHERE id = %s',
                (reserva_habitacion_id,),
            )
            rh = cursor.fetchone()
            if not rh:
                raise ValueError('reserva_habitacion_no_encontrada')

            disponible = self._stock_actual(cursor, producto_id)
            if disponible < cantidad:
                raise StockInsuficiente(disponible, cantidad)

            cursor.execute(
                """
                INSERT INTO movimientos_inventario
                    (producto_id, tipo_movimiento, cantidad, referencia,
                     empleado_id, observacion)
                VALUES (%s, 'salida', %s, %s, %s, %s)
                """,
                (
                    producto_id, cantidad,
                    f'consumo_rh_{reserva_habitacion_id}',
                    empleado_id,
                    f"Consumo de habitación: {producto['nombre']}",
                ),
            )
            movimiento_id = cursor.lastrowid

            precio = Decimal(str(producto['precio_unitario'] or 0))
            total = precio * cantidad

            cursor.execute(
                """
                INSERT INTO consumos (
                    reserva_habitacion_id, tipo_consumo_id, descripcion,
                    cantidad, precio_unitario, total, fecha, empleado_id,
                    estado
                ) VALUES (%s, %s, %s, %s, %s, %s, CURDATE(), %s, 'pendiente')
                """,
                (
                    reserva_habitacion_id,
                    producto['tipo_consumo_id'],
                    producto['nombre'],
                    cantidad,
                    precio,
                    total,
                    empleado_id,
                ),
            )
            consumo_id = cursor.lastrowid

            # El consumo entra al saldo del huésped en el acto.
            from Models.finanzas_model import calcular_saldo
            financiero = calcular_saldo(cursor, rh['reserva_id'])
            if financiero:
                cursor.execute(
                    'UPDATE reservas SET saldo_pendiente = %s WHERE id = %s',
                    (financiero['saldo_pendiente'], rh['reserva_id']),
                )

            conn.commit()
            return movimiento_id, consumo_id, producto

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
