from database import get_connection

class ClienteModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM clientes ORDER BY creado_en DESC")
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM clientes WHERE id = %s", (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def get_by_documento(self, numero_documento):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM clientes WHERE numero_documento = %s", (numero_documento,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clientes 
                (tipo_documento, numero_documento, nombre, apellido,
                 nacionalidad, telefono, email, direccion, empresa,
                 fecha_nacimiento, notas)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get('tipo_documento', 'CC'),
            data['numero_documento'],
            data['nombre'],
            data['apellido'],
            data.get('nacionalidad', 'Colombiana'),
            data.get('telefono'),
            data.get('email'),
            data.get('direccion'),
            data.get('empresa'),
            data.get('fecha_nacimiento'),
            data.get('notas')
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
            UPDATE clientes SET
                tipo_documento   = %s,
                numero_documento = %s,
                nombre           = %s,
                apellido         = %s,
                nacionalidad     = %s,
                telefono         = %s,
                email            = %s,
                direccion        = %s,
                empresa          = %s,
                fecha_nacimiento = %s,
                notas            = %s
            WHERE id = %s
        """, (
            data.get('tipo_documento', 'CC'),
            data['numero_documento'],
            data['nombre'],
            data['apellido'],
            data.get('nacionalidad', 'Colombiana'),
            data.get('telefono'),
            data.get('email'),
            data.get('direccion'),
            data.get('empresa'),
            data.get('fecha_nacimiento'),
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
        cursor.execute("DELETE FROM clientes WHERE id = %s", (id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected

    def search(self, query):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        like = f"%{query}%"
        cursor.execute("""
            SELECT * FROM clientes
            WHERE nombre           LIKE %s
               OR apellido         LIKE %s
               OR numero_documento LIKE %s
               OR email            LIKE %s
        """, (like, like, like, like))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result