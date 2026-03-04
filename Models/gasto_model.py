from database import get_connection

class GastoModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT g.*,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM gastos g
            LEFT JOIN empleados e ON g.empleado_id = e.id
            ORDER BY g.fecha DESC
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT g.*,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM gastos g
            LEFT JOIN empleados e ON g.empleado_id = e.id
            WHERE g.id = %s
        """, (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def get_by_fecha(self, fecha):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT g.*,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM gastos g
            LEFT JOIN empleados e ON g.empleado_id = e.id
            WHERE g.fecha = %s
            ORDER BY g.creado_en DESC
        """, (fecha,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_categoria(self, categoria):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT g.*,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM gastos g
            LEFT JOIN empleados e ON g.empleado_id = e.id
            WHERE g.categoria = %s
            ORDER BY g.fecha DESC
        """, (categoria,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO gastos (empleado_id, fecha, categoria, descripcion, monto)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            data.get('empleado_id'),
            data['fecha'],
            data.get('categoria', 'varios'),
            data.get('descripcion'),
            data['monto']
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
            UPDATE gastos SET
                empleado_id = %s,
                fecha       = %s,
                categoria   = %s,
                descripcion = %s,
                monto       = %s
            WHERE id = %s
        """, (
            data.get('empleado_id'),
            data['fecha'],
            data.get('categoria', 'varios'),
            data.get('descripcion'),
            data['monto'],
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
        cursor.execute("DELETE FROM gastos WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected