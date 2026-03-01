from database import get_connection

class RolModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM roles ORDER BY nombre")
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM roles WHERE id = %s", (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO roles (nombre, descripcion, activo)
            VALUES (%s, %s, %s)
        """, (
            data['nombre'],
            data.get('descripcion'),
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
            UPDATE roles SET
                nombre      = %s,
                descripcion = %s,
                activo      = %s
            WHERE id = %s
        """, (
            data['nombre'],
            data.get('descripcion'),
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
        cursor.execute("DELETE FROM roles WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected

    def asignar_permiso(self, rol_id, permiso_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT IGNORE INTO rol_permiso (rol_id, permiso_id)
            VALUES (%s, %s)
        """, (rol_id, permiso_id))
        conn.commit()
        cursor.close()
        conn.close()

    def quitar_permiso(self, rol_id, permiso_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM rol_permiso WHERE rol_id = %s AND permiso_id = %s
        """, (rol_id, permiso_id))
        conn.commit()
        cursor.close()
        conn.close()

    def get_permisos(self, rol_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.* FROM permisos p
            JOIN rol_permiso rp ON p.id = rp.permiso_id
            WHERE rp.rol_id = %s
        """, (rol_id,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result