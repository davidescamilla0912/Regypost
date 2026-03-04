from database import get_connection

class CuadreCajaModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.*,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM cuadre_caja c
            LEFT JOIN empleados e ON c.empleado_id = e.id
            ORDER BY c.fecha DESC
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.*,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM cuadre_caja c
            LEFT JOIN empleados e ON c.empleado_id = e.id
            WHERE c.id = %s
        """, (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def get_by_fecha(self, fecha):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.*,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM cuadre_caja c
            LEFT JOIN empleados e ON c.empleado_id = e.id
            WHERE c.fecha = %s
            ORDER BY c.creado_en DESC
        """, (fecha,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cuadre_caja (
                empleado_id, fecha, saldo_anterior, efectivo,
                gastos_turno, tarjetas, consignacion, factura_cxc,
                factura_credito, total_movimiento, observaciones
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get('empleado_id'),
            data['fecha'],
            data.get('saldo_anterior', 0),
            data.get('efectivo', 0),
            data.get('gastos_turno', 0),
            data.get('tarjetas', 0),
            data.get('consignacion', 0),
            data.get('factura_cxc', 0),
            data.get('factura_credito', 0),
            data.get('total_movimiento', 0),
            data.get('observaciones')
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
            UPDATE cuadre_caja SET
                empleado_id      = %s,
                fecha            = %s,
                saldo_anterior   = %s,
                efectivo         = %s,
                gastos_turno     = %s,
                tarjetas         = %s,
                consignacion     = %s,
                factura_cxc      = %s,
                factura_credito  = %s,
                total_movimiento = %s,
                observaciones    = %s
            WHERE id = %s
        """, (
            data.get('empleado_id'),
            data['fecha'],
            data.get('saldo_anterior', 0),
            data.get('efectivo', 0),
            data.get('gastos_turno', 0),
            data.get('tarjetas', 0),
            data.get('consignacion', 0),
            data.get('factura_cxc', 0),
            data.get('factura_credito', 0),
            data.get('total_movimiento', 0),
            data.get('observaciones'),
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
        cursor.execute("DELETE FROM cuadre_caja WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected