from database import get_connection


class AcompananteModel:


    def get_by_reserva(self, reserva_id):
        """Retorna todos los acompañantes de una reserva."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, reserva_id, tipo_documento, numero_documento,
                   nombre, apellido, telefono, es_menor, creado_en
            FROM acompanantes_reserva
            WHERE reserva_id = %s
            ORDER BY id ASC
        """, (reserva_id,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        """Retorna un acompañante por su id."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, reserva_id, tipo_documento, numero_documento,
                   nombre, apellido, telefono, es_menor, creado_en
            FROM acompanantes_reserva
            WHERE id = %s
        """, (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def create(self, reserva_id, data):
        """
        Crea un acompañante vinculado a una reserva.
        Retorna el id generado.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO acompanantes_reserva
                    (reserva_id, tipo_documento, numero_documento,
                     nombre, apellido, telefono, es_menor)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                reserva_id,
                data.get('tipo_documento', 'CC'),
                data['numero_documento'],
                data['nombre'],
                data['apellido'],
                data.get('telefono'),
                1 if data.get('es_menor') else 0
            ))
            conn.commit()
            new_id = cursor.lastrowid
            return new_id
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def create_bulk(self, reserva_id, lista):
        """
        Inserta varios acompañantes de una vez.
        lista: [ { tipo_documento, numero_documento, nombre, apellido, telefono, es_menor }, ... ]
        Retorna la cantidad de filas insertadas.
        """
        if not lista:
            return 0

        conn = get_connection()
        cursor = conn.cursor()
        try:
            rows = [
                (
                    reserva_id,
                    a.get('tipo_documento', 'CC'),
                    a['numero_documento'],
                    a['nombre'],
                    a['apellido'],
                    a.get('telefono'),
                    1 if a.get('es_menor') else 0
                )
                for a in lista
            ]
            cursor.executemany("""
                INSERT IGNORE INTO acompanantes_reserva
                    (reserva_id, tipo_documento, numero_documento,
                     nombre, apellido, telefono, es_menor)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, rows)
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def update(self, id, data):
        """Actualiza los datos de un acompañante."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE acompanantes_reserva SET
                    tipo_documento   = %s,
                    numero_documento = %s,
                    nombre           = %s,
                    apellido         = %s,
                    telefono         = %s,
                    es_menor         = %s
                WHERE id = %s
            """, (
                data.get('tipo_documento', 'CC'),
                data['numero_documento'],
                data['nombre'],
                data['apellido'],
                data.get('telefono'),
                1 if data.get('es_menor') else 0,
                id
            ))
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def delete(self, id):
        """Elimina un acompañante por su id."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM acompanantes_reserva WHERE id = %s", (id,)
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def delete_by_reserva(self, reserva_id):
        """Elimina TODOS los acompañantes de una reserva (útil al cancelar)."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM acompanantes_reserva WHERE reserva_id = %s",
                (reserva_id,)
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
