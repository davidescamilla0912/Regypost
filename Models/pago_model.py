from database import get_connection

class PagoModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, reserva_id, empleado_id, monto, metodo, referencia, fecha_pago, notas
            FROM pagos
            ORDER BY fecha_pago DESC, id DESC
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_reserva(self, reserva_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM pagos p
            LEFT JOIN empleados e ON p.empleado_id = e.id
            WHERE p.reserva_id = %s
            ORDER BY p.fecha_pago DESC
        """, (reserva_id,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM pagos p
            LEFT JOIN empleados e ON p.empleado_id = e.id
            WHERE p.id = %s
        """, (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def get_by_fecha(self, fecha):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM pagos p
            LEFT JOIN empleados e ON p.empleado_id = e.id
            WHERE DATE(p.fecha_pago) = %s
            ORDER BY p.fecha_pago DESC
        """, (fecha,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pagos (
                reserva_id, empleado_id, monto, metodo, referencia, notas
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            data['reserva_id'],
            data.get('empleado_id'),
            data['monto'],
            data.get('metodo', 'efectivo'),
            data.get('referencia'),
            data.get('notas')
        ))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return new_id

    def delete(self, id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pagos WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected

    def get_total_by_reserva(self, reserva_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT reserva_id,
                   SUM(monto) AS total_pagado,
                   COUNT(id)  AS num_pagos
            FROM pagos
            WHERE reserva_id = %s
            GROUP BY reserva_id
        """, (reserva_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def update(self, id, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pagos
            SET reserva_id = %s,
                empleado_id = %s,
                monto = %s,
                metodo = %s,
                referencia = %s,
                fecha_pago = %s,
                notas = %s
            WHERE id = %s
        """, (
            data['reserva_id'],
            data.get('empleado_id'),
            data['monto'],
            data.get('metodo', 'efectivo'),
            data.get('referencia'),
            data.get('fecha_pago'),
            data.get('notas'),
            id
        ))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected