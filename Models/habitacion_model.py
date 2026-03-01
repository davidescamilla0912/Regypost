from database import get_connection

class HabitacionModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
            FROM habitaciones h
            JOIN tipos_habitacion t ON h.tipo_id = t.id
            ORDER BY h.piso, h.numero
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
            FROM habitaciones h
            JOIN tipos_habitacion t ON h.tipo_id = t.id
            WHERE h.id = %s
        """, (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def get_disponibles(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
            FROM habitaciones h
            JOIN tipos_habitacion t ON h.tipo_id = t.id
            WHERE h.estado = 'disponible'
            ORDER BY h.piso, h.numero
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_estado(self, estado):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
            FROM habitaciones h
            JOIN tipos_habitacion t ON h.tipo_id = t.id
            WHERE h.estado = %s
            ORDER BY h.piso, h.numero
        """, (estado,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO habitaciones (numero, piso, tipo_id, tipo_cama, estado, notas_mantenimiento)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            data['numero'],
            data['piso'],
            data['tipo_id'],
            data.get('tipo_cama'),
            data.get('estado', 'disponible'),
            data.get('notas_mantenimiento')
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
            UPDATE habitaciones SET
                numero               = %s,
                piso                 = %s,
                tipo_id              = %s,
                tipo_cama            = %s,
                estado               = %s,
                notas_mantenimiento  = %s
            WHERE id = %s
        """, (
            data['numero'],
            data['piso'],
            data['tipo_id'],
            data.get('tipo_cama'),
            data.get('estado', 'disponible'),
            data.get('notas_mantenimiento'),
            id
        ))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected

    def update_estado(self, id, estado):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE habitaciones SET estado = %s WHERE id = %s", (estado, id)
        )
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected

    def delete(self, id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM habitaciones WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected