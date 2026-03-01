from database import get_connection
import hashlib

class EmpleadoModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT e.id, e.nombre, e.apellido, e.telefono, e.email,
                   e.usuario, e.activo, e.creado_en,
                   GROUP_CONCAT(r.nombre) AS roles
            FROM empleados e
            LEFT JOIN empleado_rol er ON e.id = er.empleado_id
            LEFT JOIN roles r ON er.rol_id = r.id
            GROUP BY e.id
            ORDER BY e.nombre
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT e.id, e.nombre, e.apellido, e.telefono, e.email,
                   e.usuario, e.activo, e.creado_en,
                   GROUP_CONCAT(r.nombre) AS roles
            FROM empleados e
            LEFT JOIN empleado_rol er ON e.id = er.empleado_id
            LEFT JOIN roles r ON er.rol_id = r.id
            WHERE e.id = %s
            GROUP BY e.id
        """, (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def get_by_usuario(self, usuario):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM empleados WHERE usuario = %s", (usuario,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        # Hash simple con sha256 (luego se puede cambiar a bcrypt)
        contrasena_hash = hashlib.sha256(data['contrasena'].encode()).hexdigest()
        cursor.execute("""
            INSERT INTO empleados (nombre, apellido, telefono, email, usuario, contrasena, activo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data['nombre'],
            data['apellido'],
            data.get('telefono'),
            data.get('email'),
            data['usuario'],
            contrasena_hash,
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
            UPDATE empleados SET
                nombre   = %s,
                apellido = %s,
                telefono = %s,
                email    = %s,
                usuario  = %s,
                activo   = %s
            WHERE id = %s
        """, (
            data['nombre'],
            data['apellido'],
            data.get('telefono'),
            data.get('email'),
            data['usuario'],
            data.get('activo', 1),
            id
        ))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected

    def update_contrasena(self, id, nueva_contrasena):
        conn = get_connection()
        cursor = conn.cursor()
        contrasena_hash = hashlib.sha256(nueva_contrasena.encode()).hexdigest()
        cursor.execute(
            "UPDATE empleados SET contrasena = %s WHERE id = %s",
            (contrasena_hash, id)
        )
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected

    def delete(self, id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM empleados WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected

    def asignar_rol(self, empleado_id, rol_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT IGNORE INTO empleado_rol (empleado_id, rol_id)
            VALUES (%s, %s)
        """, (empleado_id, rol_id))
        conn.commit()
        cursor.close()
        conn.close()

    def quitar_rol(self, empleado_id, rol_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM empleado_rol WHERE empleado_id = %s AND rol_id = %s
        """, (empleado_id, rol_id))
        conn.commit()
        cursor.close()
        conn.close()