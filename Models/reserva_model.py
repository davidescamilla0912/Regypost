from database import get_connection
import mysql.connector
from Models.consumo_model import ConsumoModel

class ReservaModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.*,
                   CONCAT(c.nombre, ' ', c.apellido) AS cliente_nombre,
                   c.numero_documento,
                   c.telefono,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM reservas r
            JOIN clientes c ON r.cliente_id = c.id
            LEFT JOIN empleados e ON r.empleado_id = e.id
            ORDER BY r.creado_en DESC
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.*,
                   CONCAT(c.nombre, ' ', c.apellido) AS cliente_nombre,
                   c.numero_documento,
                   c.telefono,
                   CONCAT(e.nombre, ' ', e.apellido) AS empleado_nombre
            FROM reservas r
            JOIN clientes c ON r.cliente_id = c.id
            LEFT JOIN empleados e ON r.empleado_id = e.id
            WHERE r.id = %s
        """, (id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result

    def get_by_estado(self, estado):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.*,
                   CONCAT(c.nombre, ' ', c.apellido) AS cliente_nombre,
                   c.telefono
            FROM reservas r
            JOIN clientes c ON r.cliente_id = c.id
            WHERE r.estado = %s
            ORDER BY r.fecha_entrada
        """, (estado,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def get_activas(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.*,
                   CONCAT(c.nombre, ' ', c.apellido) AS cliente_nombre,
                   c.telefono,
                   GROUP_CONCAT(h.numero ORDER BY h.numero) AS habitaciones
            FROM reservas r
            JOIN clientes c ON r.cliente_id = c.id
            JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
            JOIN habitaciones h ON rh.habitacion_id = h.id
            WHERE r.estado IN ('confirmada', 'checkin')
            GROUP BY r.id
            ORDER BY r.fecha_entrada
        """)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reservas (
                cliente_id, empleado_id, fecha_reserva, fecha_entrada,
                fecha_salida, hora_llegada, hora_salida, num_adultos,
                num_ninos, estado, fuente, anticipo, saldo_pendiente,
                total, late_checkout, observaciones
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['cliente_id'],
            data.get('empleado_id'),
            data['fecha_reserva'],
            data['fecha_entrada'],
            data['fecha_salida'],
            data.get('hora_llegada'),
            data.get('hora_salida'),
            data.get('num_adultos', 1),
            data.get('num_ninos', 0),
            data.get('estado', 'pendiente'),
            data.get('fuente', 'directa'),
            data.get('anticipo', 0),
            data.get('saldo_pendiente', 0),
            data.get('total', 0),
            data.get('late_checkout', 0),
            data.get('observaciones')
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
            UPDATE reservas SET
                cliente_id      = %s,
                empleado_id     = %s,
                fecha_reserva   = %s,
                fecha_entrada   = %s,
                fecha_salida    = %s,
                hora_llegada    = %s,
                hora_salida     = %s,
                num_adultos     = %s,
                num_ninos       = %s,
                estado          = %s,
                fuente          = %s,
                anticipo        = %s,
                saldo_pendiente = %s,
                total           = %s,
                late_checkout   = %s,
                observaciones   = %s
            WHERE id = %s
        """, (
            data['cliente_id'],
            data.get('empleado_id'),
            data['fecha_reserva'],
            data['fecha_entrada'],
            data['fecha_salida'],
            data.get('hora_llegada'),
            data.get('hora_salida'),
            data.get('num_adultos', 1),
            data.get('num_ninos', 0),
            data.get('estado', 'pendiente'),
            data.get('fuente', 'directa'),
            data.get('anticipo', 0),
            data.get('saldo_pendiente', 0),
            data.get('total', 0),
            data.get('late_checkout', 0),
            data.get('observaciones'),
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
        try:
            cursor.execute("""
                SELECT rh.habitacion_id FROM reserva_habitaciones rh
                WHERE rh.reserva_id = %s
            """, (id,))
            habitaciones = [row[0] for row in cursor.fetchall()]

            cursor.execute("UPDATE reservas SET estado = %s WHERE id = %s", (estado, id))
            affected = cursor.rowcount
            # Después de cambiar el estado de la reserva, recalcular el estado
            # de cada habitación asociada teniendo en cuenta otras reservas.
            if habitaciones:
                for hid in habitaciones:
                    # recalcular estado de la habitación según todas sus reservas
                    try:
                        self.recalcular_estado_habitacion(hid, cursor)
                    except Exception:
                        # si falla la recalculación con el cursor, intentar en siguiente iteración
                        pass

            conn.commit()
            return affected
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def confirmar_reserva(self, id, anticipo):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT id, total, estado
                FROM reservas
                WHERE id = %s
            """, (id,))
            reserva = cursor.fetchone()

            if not reserva:
                return None, "not_found"

            if reserva['estado'] != 'pendiente':
                return reserva, "invalid_state"

            total = reserva['total'] or 0
            saldo_pendiente = total - anticipo

            cursor.execute("""
                SELECT habitacion_id
                FROM reserva_habitaciones
                WHERE reserva_id = %s
            """, (id,))
            habitaciones = [row['habitacion_id'] for row in cursor.fetchall()]

            cursor.execute("""
                UPDATE reservas
                SET estado = 'confirmada',
                    anticipo = %s,
                    saldo_pendiente = %s
                WHERE id = %s
            """, (anticipo, saldo_pendiente, id))

            conn.commit()

            # Recalcular estado para cada habitación vinculada
            if habitaciones:
                for hid in habitaciones:
                    try:
                        self.recalcular_estado_habitacion(hid)
                    except Exception:
                        pass

            return self.get_by_id(id), "ok"
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def delete(self, id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Bloquear filas hijas para mantener un orden consistente de lock.
            cursor.execute(
                "SELECT habitacion_id FROM reserva_habitaciones WHERE reserva_id = %s FOR UPDATE",
                (id,)
            )
            habitaciones = [row[0] for row in cursor.fetchall()]

            ConsumoModel().delete_by_reserva(id, cursor)

            cursor.execute("DELETE FROM reserva_habitaciones WHERE reserva_id = %s", (id,))

            cursor.execute("DELETE FROM reservas WHERE id = %s", (id,))
            affected = cursor.rowcount
            conn.commit()
            # Recalcular estado para cada habitación afectada
            if habitaciones:
                for hid in habitaciones:
                    try:
                        self.recalcular_estado_habitacion(hid)
                    except Exception:
                        pass

            return affected
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # --- Habitaciones de la reserva ---
    def get_habitaciones(self, reserva_id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT rh.*, h.numero, h.piso, h.tipo_cama,
                   t.nombre AS tipo_nombre
            FROM reserva_habitaciones rh
            JOIN habitaciones h ON rh.habitacion_id = h.id
            JOIN tipos_habitacion t ON h.tipo_id = t.id
            WHERE rh.reserva_id = %s
        """, (reserva_id,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def agregar_habitacion(self, reserva_id, data):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Obtener fechas y estado de la reserva
            cursor.execute(
                "SELECT fecha_entrada, estado FROM reservas WHERE id = %s",
                (reserva_id,)
            )
            reserva = cursor.fetchone()
            fecha_entrada = reserva[0] if reserva else None
            estado_reserva = reserva[1] if reserva else None

            cursor.execute("""
                INSERT INTO reserva_habitaciones
                    (reserva_id, habitacion_id, precio_noche)
                VALUES (%s, %s, %s)
            """, (
                reserva_id,
                data['habitacion_id'],
                data.get('precio_noche', 0)
            ))
            new_id = cursor.lastrowid

            conn.commit()

            # Recalcular estado real de la habitación teniendo en cuenta
            # todas las reservas asociadas (no solo la actual)
            try:
                self.recalcular_estado_habitacion(data['habitacion_id'])
            except Exception:
                pass

            return new_id
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def quitar_habitacion(self, reserva_id, habitacion_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                DELETE FROM reserva_habitaciones
                WHERE reserva_id = %s AND habitacion_id = %s
            """, (reserva_id, habitacion_id))
            affected = cursor.rowcount

            conn.commit()

            # Recalcular el estado de la habitación ahora que fue removida
            try:
                self.recalcular_estado_habitacion(habitacion_id)
            except Exception:
                pass

            return affected
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def recalcular_estado_habitacion(self, habitacion_id, cursor=None):
        """
        Recalcula y actualiza el estado de una habitación según las reservas
        asociadas. Prioridad:
        - Si existe una reserva en 'checkin' -> 'ocupada'
        - Else si existe 'confirmada' o 'llegada prevista' -> 'reservada'
        - Else -> 'disponible'

        El parámetro `cursor` es opcional; si se entrega se reutiliza la
        transacción actual, si no se abre una conexión temporal.
        """
        uso_cursor_externo = cursor is not None
        conn = None
        try:
            if not uso_cursor_externo:
                conn = get_connection()
                cursor = conn.cursor()

            cursor.execute("""
                SELECT DISTINCT r.estado
                FROM reservas r
                JOIN reserva_habitaciones rh ON r.id = rh.reserva_id
                WHERE rh.habitacion_id = %s
            """, (habitacion_id,))
            estados = [row[0] for row in cursor.fetchall()]

            estado_final = 'disponible'
            # Normalizar y evaluar prioridad
            for est in estados:
                if not est:
                    continue
                s = est.lower().strip()
                s_clean = s.replace('-', '').replace('_', ' ').replace('  ', ' ')
                # check-in / checkin / check_in
                if 'checkin' in s or ('check' in s and 'in' in s):
                    estado_final = 'ocupada'
                    break
                # llegada prevista (varias formas)
                if 'llegada' in s and 'prevista' in s:
                    estado_final = 'reservada'
                    # no rompemos, porque puede haber un checkin
                    continue
                # confirmada
                if 'confirm' in s or s == 'confirmada' or s == 'confirmado':
                    # si aún no hay 'ocupada', marcar como reservada
                    if estado_final != 'ocupada':
                        estado_final = 'reservada'

            cursor.execute("UPDATE habitaciones SET estado = %s WHERE id = %s", (estado_final, habitacion_id))
            if not uso_cursor_externo:
                conn.commit()
            return estado_final
        finally:
            if not uso_cursor_externo and cursor:
                cursor.close()
            if conn:
                conn.close()

    def tiene_reservas_futuras(self, habitacion_id):
        """Retorna True si la habitación tiene reservas futuras confirmadas o pendientes."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM reservas r
            JOIN reserva_habitaciones rh ON r.id = rh.reserva_id
            WHERE rh.habitacion_id = %s
              AND r.estado IN ('confirmada', 'pendiente')
              AND r.fecha_entrada > CURDATE()
        """, (habitacion_id,))
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count > 0