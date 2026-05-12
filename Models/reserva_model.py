from database import get_connection
import mysql.connector
from Models.consumo_model import ConsumoModel
from datetime import timedelta

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

    def update_personas(self, id, num_adultos, num_ninos):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE reservas
                SET num_adultos = %s,
                    num_ninos   = %s
                WHERE id = %s
            """, (num_adultos, num_ninos, id))
            conn.commit()
            affected = cursor.rowcount
            return affected
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

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
    
    def extender_dias(self, id, dias_extra):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Obtener reserva y precio por noche agregado (suma de habitaciones)
            cursor.execute("""
                SELECT r.*, COALESCE(SUM(rh.precio_noche), 0) AS precio_noche_total
                FROM reservas r
                LEFT JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
                WHERE r.id = %s
                GROUP BY r.id
            """, (id,))
            reserva = cursor.fetchone()

            if not reserva:
                return None, "not_found"
            if reserva.get('estado') != 'checkin':
                return None, "invalid_state"

            fecha_salida_actual = reserva.get('fecha_salida')
            if fecha_salida_actual is None:
                return None, "invalid_date"

            nueva_fecha_salida = fecha_salida_actual + timedelta(days=int(dias_extra))

            precio_noche = float(reserva.get('precio_noche_total') or 0)
            total_actual = float(reserva.get('total') or 0)
            anticipo = float(reserva.get('anticipo') or 0)

            costo_dias_extra = precio_noche * int(dias_extra)
            nuevo_total = total_actual + costo_dias_extra
            nuevo_saldo = max(nuevo_total - anticipo, 0)

            cursor.execute("""
                UPDATE reservas SET
                    fecha_salida    = %s,
                    total           = %s,
                    saldo_pendiente = %s
                WHERE id = %s
            """, (nueva_fecha_salida, nuevo_total, nuevo_saldo, id))

            conn.commit()

            return {
                "nueva_fecha_salida": getattr(nueva_fecha_salida, 'isoformat', lambda: str(nueva_fecha_salida))(),
                "dias_extra": int(dias_extra),
                "costo_dias_extra": costo_dias_extra,
                "nuevo_total": nuevo_total,
                "nuevo_saldo": nuevo_saldo
            }, "ok"
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    
    def cambiar_habitacion(self, reserva_id, nueva_habitacion_id, motivo, empleado_id=None):
        """
        Cambia la habitación de una reserva en checkin.
 
        Pasos atómicos (una sola transacción):
        1. Validar que la reserva exista y esté en checkin.
        2. Obtener el registro reserva_habitaciones actual (habitación origen).
        3. Validar que la nueva habitación esté disponible o reservada
           (estado != ocupada / mantenimiento / bloqueada).
        4. Validar que la nueva habitación NO tenga una reserva activa en checkin
           (si está en estado 'reservada', solo reservas futuras son aceptables).
        5. Validar que el checkout de la reserva actual NO choque con la
           próxima reserva futura de la habitación destino.
        6. Actualizar reserva_habitaciones: cambia habitacion_id al nuevo,
           mantiene precio_noche (mismo rango de precio que ya definiste).
        7. Habitación origen  → estado = 'mantenimiento'  +  notas_mantenimiento = motivo
        8. Habitación destino → estado = 'ocupada'
        9. Registrar el cambio en observaciones de la reserva (append).
        10. Si el empleado_id viene, también se guarda en el campo empleado_id
            de la reserva (audit trail mínimo sin tabla extra).
 
        Retorna (dict_resultado, "ok") o (None, "codigo_error").
        """
        from datetime import date as date_type
        import mysql.connector as _mc
 
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
 
        try:
            # ── 1. Obtener reserva ──────────────────────────────────────────
            cursor.execute("""
                SELECT r.*,
                       COALESCE(SUM(rh.precio_noche), 0) AS precio_noche_total
                FROM reservas r
                LEFT JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
                WHERE r.id = %s
                GROUP BY r.id
            """, (reserva_id,))
            reserva = cursor.fetchone()
 
            if not reserva:
                return None, "not_found"
            if reserva.get('estado') != 'checkin':
                return None, "invalid_state"   # solo reservas en checkin
 
            # ── 2. Registro reserva_habitaciones actual ─────────────────────
            cursor.execute("""
                SELECT rh.id, rh.habitacion_id, rh.precio_noche,
                       h.numero AS numero_origen, h.estado AS estado_origen,
                       h.notas_mantenimiento
                FROM reserva_habitaciones rh
                JOIN habitaciones h ON h.id = rh.habitacion_id
                WHERE rh.reserva_id = %s
                LIMIT 1
            """, (reserva_id,))
            rh_actual = cursor.fetchone()
 
            if not rh_actual:
                return None, "no_room_linked"
 
            habitacion_origen_id = rh_actual['habitacion_id']
            rh_id                = rh_actual['id']
 
            if habitacion_origen_id == nueva_habitacion_id:
                return None, "same_room"
 
            # ── 3. Validar habitación destino ───────────────────────────────
            cursor.execute("""
                SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
                FROM habitaciones h
                JOIN tipos_habitacion t ON t.id = h.tipo_id
                WHERE h.id = %s
            """, (nueva_habitacion_id,))
            hab_destino = cursor.fetchone()
 
            if not hab_destino:
                return None, "dest_not_found"
 
            estados_bloqueados = ('ocupada', 'mantenimiento', 'bloqueada')
            if hab_destino['estado'] in estados_bloqueados:
                return None, "dest_not_available"
 
            # ── 4. Verificar que destino no tenga checkin activo ───────────
            cursor.execute("""
                SELECT COUNT(*) AS cnt
                FROM reservas r
                JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
                WHERE rh.habitacion_id = %s
                  AND r.estado = 'checkin'
                  AND r.id != %s
            """, (nueva_habitacion_id, reserva_id))
            if cursor.fetchone()['cnt'] > 0:
                return None, "dest_occupied"
 
            # ── 5. Validar que el checkout no choque con reserva futura ─────
            fecha_salida_reserva = reserva.get('fecha_salida')
            cursor.execute("""
                SELECT r.fecha_entrada
                FROM reservas r
                JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
                WHERE rh.habitacion_id = %s
                  AND r.estado IN ('confirmada', 'pendiente')
                  AND r.fecha_entrada < %s
                  AND r.id != %s
                ORDER BY r.fecha_entrada ASC
                LIMIT 1
            """, (nueva_habitacion_id, fecha_salida_reserva, reserva_id))
            conflicto = cursor.fetchone()
            if conflicto:
                return None, "date_conflict"
 
            # ── 6. Actualizar reserva_habitaciones ──────────────────────────
            cursor.execute("""
                UPDATE reserva_habitaciones
                SET habitacion_id = %s
                WHERE id = %s
            """, (nueva_habitacion_id, rh_id))
 
            # ── 7. Habitación origen → mantenimiento ────────────────────────
            nota_anterior = rh_actual.get('notas_mantenimiento') or ''
            nota_nueva    = f"[CAMBIO HAB {date_type.today().isoformat()}] {motivo}"
            notas_finales = (nota_anterior + '\n' + nota_nueva).strip()
 
            cursor.execute("""
                UPDATE habitaciones
                SET estado               = 'mantenimiento',
                    notas_mantenimiento  = %s
                WHERE id = %s
            """, (notas_finales, habitacion_origen_id))
 
            # ── 8. Habitación destino → ocupada ─────────────────────────────
            cursor.execute("""
                UPDATE habitaciones
                SET estado = 'ocupada'
                WHERE id = %s
            """, (nueva_habitacion_id,))
 
            # ── 9. Registrar en observaciones de la reserva (audit simple) ──
            obs_anterior = reserva.get('observaciones') or ''
            obs_nueva    = (
                f"[CAMBIO HAB {date_type.today().isoformat()}] "
                f"Hab {rh_actual['numero_origen']} → Hab {hab_destino['numero']}. "
                f"Motivo: {motivo}. "
                f"Operador ID: {empleado_id or 'N/A'}"
            )
            obs_final = (obs_anterior + '\n' + obs_nueva).strip()
 
            # ── 10. Guardar observaciones (y empleado como audit) ───────────
            if empleado_id:
                cursor.execute("""
                    UPDATE reservas
                    SET observaciones = %s, empleado_id = %s
                    WHERE id = %s
                """, (obs_final, empleado_id, reserva_id))
            else:
                cursor.execute("""
                    UPDATE reservas
                    SET observaciones = %s
                    WHERE id = %s
                """, (obs_final, reserva_id))
 
            conn.commit()
 
            return {
                "reserva_id":           reserva_id,
                "habitacion_origen_id": habitacion_origen_id,
                "habitacion_origen":    rh_actual['numero_origen'],
                "habitacion_destino_id": nueva_habitacion_id,
                "habitacion_destino":   hab_destino['numero'],
                "motivo":               motivo,
                "empleado_id":          empleado_id,
                "observaciones":        obs_final,
            }, "ok"
 
        except _mc.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
 
    def get_habitaciones_para_cambio(self, reserva_id):
        """
        Retorna habitaciones candidatas para un cambio:
        - Estado 'disponible'
        - Estado 'reservada' que NO tenga una reserva con checkin activo
          y cuya próxima reserva futura no choque con la fecha_salida actual.
 
        Excluye la habitación actualmente asignada a la reserva.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Fecha salida de la reserva actual y habitación actual
            cursor.execute("""
                SELECT r.fecha_salida, rh.habitacion_id AS hab_actual_id
                FROM reservas r
                JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
                WHERE r.id = %s
                LIMIT 1
            """, (reserva_id,))
            info = cursor.fetchone()
            if not info:
                return []
 
            fecha_salida = info['fecha_salida']
            hab_actual_id = info['hab_actual_id']
 
            # Habitaciones disponibles (excluir la actual)
            cursor.execute("""
                SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
                FROM habitaciones h
                JOIN tipos_habitacion t ON t.id = h.tipo_id
                WHERE h.estado = 'disponible'
                  AND h.id != %s
                ORDER BY h.piso, h.numero
            """, (hab_actual_id,))
            disponibles = cursor.fetchall()
            for d in disponibles:
                d['motivo_disponible'] = 'disponible'
 
            # Habitaciones reservadas sin checkin activo
            # y cuya próxima reserva futura empieza DESPUÉS de fecha_salida
            cursor.execute("""
                SELECT h.*, t.nombre AS tipo_nombre, t.precio_base,
                       MIN(r2.fecha_entrada) AS proxima_entrada
                FROM habitaciones h
                JOIN tipos_habitacion t ON t.id = h.tipo_id
                JOIN reserva_habitaciones rh2 ON rh2.habitacion_id = h.id
                JOIN reservas r2 ON r2.id = rh2.reserva_id
                WHERE h.estado = 'reservada'
                  AND h.id != %s
                  AND r2.estado IN ('confirmada', 'pendiente')
                  AND r2.fecha_entrada >= %s
                GROUP BY h.id
                HAVING proxima_entrada >= %s
                ORDER BY h.piso, h.numero
            """, (hab_actual_id, fecha_salida, fecha_salida))
            reservadas_ok = cursor.fetchall()
            for r in reservadas_ok:
                r['motivo_disponible'] = 'reservada_sin_conflicto'
                # Convertir fecha a string si es date object
                if hasattr(r.get('proxima_entrada'), 'isoformat'):
                    r['proxima_entrada'] = r['proxima_entrada'].isoformat()
 
            return disponibles + reservadas_ok
        finally:
            cursor.close()
            conn.close()
 
