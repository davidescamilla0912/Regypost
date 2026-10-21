"""
§6.2 y §6.3 — Habitaciones.

Dos cambios:

  * `PATCH /habitaciones/:id/estado` aceptaba cualquier transición: el
    `<select>` de la tarjeta permitía pasar de 'ocupada' a 'disponible' con el
    huésped dentro (F29). Ahora se valida contra TRANSICIONES_HABITACION.

  * `GET /habitaciones/disponibles` devolvía las que tenían el estado
    'disponible' en ese instante, sin mirar fechas. Ahora acepta
    `?desde=&hasta=` y responde con las que están libres en ese rango, que es
    lo que el frontend necesitaba para dejar de calcularlo en un `useMemo`.
"""
import mysql.connector

from Models.reserva_model import ESTADOS_BLOQUEAN, TRANSICIONES_HABITACION, TransicionInvalida
from database import get_connection
from utils.fechas import a_fecha


class HabitacionModel:

    def get_all(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
                FROM habitaciones h
                JOIN tipos_habitacion t ON h.tipo_id = t.id
                ORDER BY h.piso, h.numero
                """
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_by_id(self, id):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
                FROM habitaciones h
                JOIN tipos_habitacion t ON h.tipo_id = t.id
                WHERE h.id = %s
                """,
                (id,),
            )
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

    def get_disponibles(self, desde=None, hasta=None):
        """
        Habitaciones libres. Con `desde` y `hasta` la respuesta es la
        disponibilidad real en ese rango: excluye las que ya tienen una
        reserva que se solapa, con la misma regla que aplica el alta
        (`inicioA < finB && inicioB < finA`).

        Sin fechas, se comporta como antes: las que están 'disponible' ahora.
        """
        desde = a_fecha(desde)
        hasta = a_fecha(hasta)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if not desde or not hasta:
                cursor.execute(
                    """
                    SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
                    FROM habitaciones h
                    JOIN tipos_habitacion t ON h.tipo_id = t.id
                    WHERE h.estado = 'disponible'
                    ORDER BY h.piso, h.numero
                    """
                )
                return cursor.fetchall()

            if desde >= hasta:
                raise ValueError('fechas_invalidas')

            marcadores = ', '.join(['%s'] * len(ESTADOS_BLOQUEAN))
            cursor.execute(
                f"""
                SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
                FROM habitaciones h
                JOIN tipos_habitacion t ON h.tipo_id = t.id
                WHERE h.estado NOT IN ('mantenimiento', 'bloqueada')
                  AND NOT EXISTS (
                      SELECT 1
                      FROM reserva_habitaciones rh
                      JOIN reservas r ON r.id = rh.reserva_id
                      WHERE rh.habitacion_id = h.id
                        AND r.estado IN ({marcadores})
                        AND r.fecha_entrada < %s
                        AND r.fecha_salida  > %s
                  )
                ORDER BY h.piso, h.numero
                """,
                (*ESTADOS_BLOQUEAN, hasta, desde),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_by_estado(self, estado):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT h.*, t.nombre AS tipo_nombre, t.precio_base
                FROM habitaciones h
                JOIN tipos_habitacion t ON h.tipo_id = t.id
                WHERE h.estado = %s
                ORDER BY h.piso, h.numero
                """,
                (estado,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def create(self, data):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO habitaciones
                    (numero, piso, tipo_id, tipo_cama, estado, notas_mantenimiento)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    data['numero'],
                    data['piso'],
                    data['tipo_id'],
                    data.get('tipo_cama'),
                    data.get('estado', 'disponible'),
                    data.get('notas_mantenimiento'),
                ),
            )
            conn.commit()
            return cursor.lastrowid
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def update(self, id, data):
        """
        Edita los datos de la habitación. El `estado` NO se toca por aquí:
        tiene su propio endpoint con la máquina de estados.
        """
        campos = []
        valores = []
        for campo in ('numero', 'piso', 'tipo_id', 'tipo_cama',
                      'notas_mantenimiento'):
            if campo in data:
                campos.append(f'{campo} = %s')
                valores.append(data[campo])

        if not campos:
            return 0

        valores.append(id)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"UPDATE habitaciones SET {', '.join(campos)} WHERE id = %s",
                valores,
            )
            conn.commit()
            return cursor.rowcount or 1
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def update_estado(self, id, estado, forzar=False):
        """
        §6.3 — Cambia el estado validando la transición.

        Además resuelve en el servidor la regla que el cliente hacía en dos
        pasos (F28): si se pide 'disponible' pero la habitación tiene reservas
        activas, el estado real que queda es 'reservada' (u 'ocupada' si hay
        un check-in en curso).

        Devuelve `(afectadas, estado_final)`.
        Lanza TransicionInvalida si la transición no está permitida.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute(
                'SELECT estado FROM habitaciones WHERE id = %s FOR UPDATE', (id,)
            )
            fila = cursor.fetchone()
            if not fila:
                return 0, None

            anterior = fila['estado']
            if anterior == estado:
                conn.rollback()
                return 1, anterior

            permitidas = TRANSICIONES_HABITACION.get(anterior, set())
            if not forzar and estado not in permitidas:
                raise TransicionInvalida(anterior, estado, permitidas)

            estado_final = estado

            # F29: no se puede liberar una habitación con el huésped dentro.
            if estado == 'disponible':
                marcadores = ', '.join(['%s'] * len(ESTADOS_BLOQUEAN))
                cursor.execute(
                    f"""
                    SELECT r.estado
                    FROM reservas r
                    JOIN reserva_habitaciones rh ON rh.reserva_id = r.id
                    WHERE rh.habitacion_id = %s
                      AND r.estado IN ({marcadores})
                    """,
                    (id, *ESTADOS_BLOQUEAN),
                )
                estados = [f['estado'] for f in cursor.fetchall()]
                if 'checkin' in estados:
                    raise TransicionInvalida(anterior, 'disponible',
                                             {'mantenimiento'})
                if estados:
                    estado_final = 'reservada'

            cursor.execute('UPDATE habitaciones SET estado = %s WHERE id = %s',
                           (estado_final, id))
            afectadas = cursor.rowcount
            conn.commit()
            return (afectadas or 1), estado_final

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def delete(self, id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM habitaciones WHERE id = %s', (id,))
            conn.commit()
            return cursor.rowcount
        except mysql.connector.Error:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
