from database import get_connection
import hashlib

class AuthModel:

    def login(self, usuario, contrasena):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        contrasena_hash = hashlib.sha256(contrasena.encode()).hexdigest()
        cursor.execute("""
            SELECT e.id, e.nombre, e.apellido, e.usuario, e.activo,
                   GROUP_CONCAT(r.nombre) AS roles
            FROM empleados e
            LEFT JOIN empleado_rol er ON e.id = er.empleado_id
            LEFT JOIN roles r ON er.rol_id = r.id
            WHERE e.usuario = %s AND e.contrasena = %s AND e.activo = 1
            GROUP BY e.id
        """, (usuario, contrasena_hash))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def get_permisos(self, empleado_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT DISTINCT p.nombre
            FROM permisos p
            JOIN rol_permiso rp ON p.id = rp.permiso_id
            JOIN empleado_rol er ON rp.rol_id = er.rol_id
            WHERE er.empleado_id = %s
        """, (empleado_id,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row['nombre'] for row in result]