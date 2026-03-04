from database import get_connection

class InventarioModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*, 
                   COALESCE(SUM(
                       CASE
                           WHEN m.tipo_movimiento = 'entrada' THEN  m.cantidad
                           WHEN m.tipo_movimiento = 'salida'  THEN -m.cantidad
                           WHEN m.tipo_movimiento = 'ajuste'  THEN  m.cantidad
                       END
                   ), 0) AS stock_actual,
                   CASE
                       WHEN COALESCE(SUM(
                           CASE
                               WHEN m.tipo_movimiento = 'entrada' THEN  m.cantidad
                               WHEN m.tipo_movimiento = 'salida'  THEN -m.cantidad
                               WHEN m.tipo_movimiento = 'ajuste'  THEN  m.cantidad
                           END
                       ), 0) <= p.stock_minimo THEN 'REPONER'
                       ELSE 'OK'
                   END AS alerta
            FROM productos_inventario p
            LEFT JOIN movimientos_inventario m ON m.producto_id = p.id
            WHERE p.activo = 1
            GROUP BY p.id
            ORDER BY p.categoria, p.nombre
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*,
                   COALESCE(SUM(
                       CASE
                           WHEN m.tipo_movimiento = 'entrada' THEN  m.cantidad
                           WHEN m.tipo_movimiento = 'salida'  THEN -m.cantidad
                           WHEN m.tipo_movimiento = 'ajuste'  THEN  m.cantidad
                       END
                   ), 0) AS stock_actual
            FROM productos_inventario p
            LEFT JOIN movimientos_inventario m ON m.producto_id = p.id
            WHERE p.id = %s
            GROUP BY p.id
        """, (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def get_por_reponer(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*,
                   COALESCE(SUM(
                       CASE
                           WHEN m.tipo_movimiento = 'entrada' THEN  m.cantidad
                           WHEN m.tipo_movimiento = 'salida'  THEN -m.cantidad
                           WHEN m.tipo_movimiento = 'ajuste'  THEN  m.cantidad
                       END
                   ), 0) AS stock_actual
            FROM productos_inventario p
            LEFT JOIN movimientos_inventario m ON m.producto_id = p.id
            WHERE p.activo = 1
            GROUP BY p.id
            HAVING stock_actual <= p.stock_minimo
            ORDER BY stock_actual ASC
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO productos_inventario
                (nombre, categoria, precio_unitario, stock_minimo, activo)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            data['nombre'],
            data.get('categoria'),
            data.get('precio_unitario', 0),
            data.get('stock_minimo', 5),
            data.get('activo', 1)
        ))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return new_id

    def update(self, id, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE productos_inventario SET
                nombre          = %s,
                categoria       = %s,
                precio_unitario = %s,
                stock_minimo    = %s,
                activo          = %s
            WHERE id = %s
        """, (
            data['nombre'],
            data.get('categoria'),
            data.get('precio_unitario', 0),
            data.get('stock_minimo', 5),
            data.get('activo', 1),
            id
        ))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected

    def delete(self, id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE productos_inventario SET activo = 0 WHERE id = %s", (id,)
        )
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected

    # --- Movimientos ---
    def get_movimientos(self, producto_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT m.*,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM movimientos_inventario m
            LEFT JOIN empleados e ON m.empleado_id = e.id
            WHERE m.producto_id = %s
            ORDER BY m.fecha DESC
        """, (producto_id,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def registrar_movimiento(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO movimientos_inventario
                (producto_id, tipo_movimiento, cantidad, referencia, empleado_id, observacion)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            data['producto_id'],
            data['tipo_movimiento'],
            data['cantidad'],
            data.get('referencia'),
            data.get('empleado_id'),
            data.get('observacion')
        ))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return new_id