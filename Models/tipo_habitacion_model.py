from database import get_connection

class TipoHabitacionModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM tipos_habitacion ORDER BY nombre")
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM tipos_habitacion WHERE id = %s", (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tipos_habitacion (nombre, descripcion, capacidad, precio_base)
            VALUES (%s, %s, %s, %s)
        """, (
            data['nombre'],
            data.get('descripcion'),
            data.get('capacidad', 1),
            data.get('precio_base', 0)
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
            UPDATE tipos_habitacion SET
                nombre      = %s,
                descripcion = %s,
                capacidad   = %s,
                precio_base = %s
            WHERE id = %s
        """, (
            data['nombre'],
            data.get('descripcion'),
            data.get('capacidad', 1),
            data.get('precio_base', 0),
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
        cursor.execute("DELETE FROM tipos_habitacion WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected