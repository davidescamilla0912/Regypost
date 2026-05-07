from database import get_connection

class ConsumoModel:

    def get_by_reserva(self, reserva_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.*, tc.nombre AS tipo_nombre, tc.categoria,
                   h.numero AS habitacion_numero
            FROM consumos c
            JOIN tipos_consumo tc ON c.tipo_consumo_id = tc.id
            JOIN reserva_habitaciones rh ON c.reserva_habitacion_id = rh.id
            JOIN habitaciones h ON rh.habitacion_id = h.id
            WHERE rh.reserva_id = %s
            ORDER BY c.fecha DESC
        """, (reserva_id,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.*, tc.nombre AS tipo_nombre,
                   h.numero AS habitacion_numero
            FROM consumos c
            JOIN tipos_consumo tc ON c.tipo_consumo_id = tc.id
            JOIN reserva_habitaciones rh ON c.reserva_habitacion_id = rh.id
            JOIN habitaciones h ON rh.habitacion_id = h.id
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
            SELECT c.*, tc.nombre AS tipo_nombre,
                   h.numero AS habitacion_numero
            FROM consumos c
            JOIN tipos_consumo tc ON c.tipo_consumo_id = tc.id
            JOIN reserva_habitaciones rh ON c.reserva_habitacion_id = rh.id
            JOIN habitaciones h ON rh.habitacion_id = h.id
            WHERE c.fecha = %s
            ORDER BY c.id DESC
        """, (fecha,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        total = data.get('cantidad', 1) * data.get('precio_unitario', 0)
        cursor.execute("""
        INSERT INTO consumos (
            reserva_habitacion_id, tipo_consumo_id, descripcion,
            cantidad, precio_unitario, total, fecha, empleado_id, estado
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data['reserva_habitacion_id'],
        data['tipo_consumo_id'],
        data.get('descripcion'),
        data.get('cantidad', 1),
        data.get('precio_unitario', 0),
        total,
        data['fecha'],
        data.get('empleado_id'),
        data.get('estado', 'pendiente')   # ← nuevo
    ))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return new_id

    def update(self, id, data):
        conn = get_connection()
        cursor = conn.cursor()
        total = data.get('cantidad', 1) * data.get('precio_unitario', 0)
        cursor.execute("""
            UPDATE consumos SET
                tipo_consumo_id       = %s,
                descripcion           = %s,
                cantidad              = %s,
                precio_unitario       = %s,
                total                 = %s,
                fecha                 = %s,
                empleado_id           = %s
            WHERE id = %s
        """, (
            data['tipo_consumo_id'],
            data.get('descripcion'),
            data.get('cantidad', 1),
            data.get('precio_unitario', 0),
            total,
            data['fecha'],
            data.get('empleado_id'),
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
        try:
            cursor.execute("DELETE FROM consumos WHERE id = %s", (id,))
            affected = cursor.rowcount
            conn.commit()
            return affected
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def delete_by_reserva(self, reserva_id, cursor=None):
        owns_connection = cursor is None
        if owns_connection:
            conn = get_connection()
            cursor = conn.cursor()
        try:
            cursor.execute(
                """
                DELETE c
                FROM consumos c
                JOIN reserva_habitaciones rh ON c.reserva_habitacion_id = rh.id
                WHERE rh.reserva_id = %s
                """,
                (reserva_id,)
            )
            affected = cursor.rowcount
            if owns_connection:
                conn.commit()
            return affected
        except Exception:
            if owns_connection:
                conn.rollback()
            raise
        finally:
            if owns_connection:
                cursor.close()
                conn.close()

    def get_tipos_consumo(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM tipos_consumo WHERE activo = 1 ORDER BY categoria, nombre")
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def create_daño(self, data):
        conn = get_connection()
        cursor = conn.cursor()

        # Buscar el id del tipo_consumo 'Daño' dinámicamente
        cursor.execute("SELECT id FROM tipos_consumo WHERE nombre = 'Daño' AND activo = 1")
        tipo = cursor.fetchone()
        if not tipo:
            cursor.close()
            conn.close()
            raise ValueError("Tipo de consumo 'Daño' no está configurado en la BD")

        tipo_consumo_id = tipo[0]
        total = data.get('precio_unitario', 0)  # cantidad siempre 1 para daños

        cursor.execute("""
            INSERT INTO consumos (
                reserva_habitacion_id, tipo_consumo_id, descripcion,
                cantidad, precio_unitario, total, fecha, empleado_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['reserva_habitacion_id'],
            tipo_consumo_id,
            data.get('descripcion'),  # descripción del daño es importante
            1,                        # siempre 1 unidad por daño
            data.get('precio_unitario', 0),
            total,
            data['fecha'],
            data.get('empleado_id')
        ))
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return new_id

   