from database import get_connection

class ParqueaderoModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*, h.numero AS habitacion_numero
            FROM parqueadero p
            LEFT JOIN habitaciones h ON p.habitacion_id = h.id
            ORDER BY p.hora_entrada DESC
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*, h.numero AS habitacion_numero
            FROM parqueadero p
            LEFT JOIN habitaciones h ON p.habitacion_id = h.id
            WHERE p.id = %s
        """, (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def get_activos(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*, h.numero AS habitacion_numero
            FROM parqueadero p
            LEFT JOIN habitaciones h ON p.habitacion_id = h.id
            WHERE p.hora_salida IS NULL
            ORDER BY p.hora_entrada DESC
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_placa(self, placa):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*, h.numero AS habitacion_numero
            FROM parqueadero p
            LEFT JOIN habitaciones h ON p.habitacion_id = h.id
            WHERE p.placa = %s
            ORDER BY p.hora_entrada DESC
        """, (placa,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO parqueadero
                (reserva_id, habitacion_id, placa, hora_entrada, valor, notas)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            data.get('reserva_id'),
            data.get('habitacion_id'),
            data['placa'],
            data['hora_entrada'],
            data.get('valor', 0),
            data.get('notas')
        ))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return new_id

    def registrar_salida(self, id, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE parqueadero SET
                hora_salida = %s,
                valor       = %s,
                notas       = %s
            WHERE id = %s
        """, (
            data['hora_salida'],
            data.get('valor', 0),
            data.get('notas'),
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
        cursor.execute("DELETE FROM parqueadero WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected