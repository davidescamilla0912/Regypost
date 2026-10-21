"""
Pruebas #12 y #17 del §10: concurrencia y atomicidad.

Estas dos no se pueden comprobar con un test_client secuencial, porque lo que
verifican es precisamente qué pasa cuando dos peticiones compiten o cuando una
falla a mitad de camino.

    python tests/test_concurrencia.py
"""
import os
import sys
import threading
from datetime import timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Models.reserva_model import ReservaModel  # noqa: E402
from database import get_connection  # noqa: E402
from utils.fechas import hoy_local  # noqa: E402

MARCA = 'ZZCONC'
resultados = []


def check(nombre, condicion, detalle=''):
    resultados.append((nombre, bool(condicion)))
    print(f"  [{'PASA' if condicion else 'FALLA'}] {nombre}"
          + (f' — {detalle}' if detalle else ''))


def sql(query, params=(), fetch=None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        if fetch:
            return cursor.fetchone() if fetch == 'one' else cursor.fetchall()
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        conn.close()


def limpiar():
    sql("""DELETE rh FROM reserva_habitaciones rh
           JOIN reservas r ON r.id = rh.reserva_id
           JOIN clientes c ON c.id = r.cliente_id
           WHERE c.numero_documento LIKE %s""", (MARCA + '%',))
    sql("""DELETE r FROM reservas r JOIN clientes c ON c.id = r.cliente_id
           WHERE c.numero_documento LIKE %s""", (MARCA + '%',))
    sql('DELETE FROM clientes WHERE numero_documento LIKE %s', (MARCA + '%',))
    sql('DELETE FROM habitaciones WHERE numero LIKE %s', ('Y9%',))


def main():
    limpiar()

    cliente_id = sql(
        """INSERT INTO clientes (tipo_documento, numero_documento, nombre, apellido)
           VALUES ('CC', %s, 'Conc', 'Prueba')""", (MARCA + '001',))
    tipo = sql('SELECT id FROM tipos_habitacion LIMIT 1', fetch='one')
    hab_id = sql("""INSERT INTO habitaciones (numero, piso, tipo_id, estado)
                    VALUES ('Y901', 9, %s, 'disponible')""", (tipo['id'],))

    entrada = hoy_local() + timedelta(days=60)
    salida = entrada + timedelta(days=3)
    payload = {
        'cliente_id': cliente_id,
        'habitacion_id': hab_id,
        'fecha_entrada': entrada.isoformat(),
        'fecha_salida': salida.isoformat(),
        'precio_noche': 100000,
    }

    print('\n=== #12 (F18) Dos peticiones simultáneas por la misma habitación ===')

    model = ReservaModel()
    exitos, fallos = [], []
    barrera = threading.Barrier(2)

    def intentar():
        barrera.wait()   # arrancan a la vez
        try:
            exitos.append(model.create(dict(payload)))
        except Exception as exc:
            fallos.append(str(exc))

    hilos = [threading.Thread(target=intentar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    check('#12 Sólo una de las dos reservas simultáneas se crea',
          len(exitos) == 1 and len(fallos) == 1,
          f'creadas={len(exitos)} rechazadas={len(fallos)} motivo={fallos}')

    filas = sql("""SELECT COUNT(*) AS c FROM reserva_habitaciones rh
                   JOIN reservas r ON r.id = rh.reserva_id
                   WHERE rh.habitacion_id = %s AND r.estado != 'cancelada'""",
                (hab_id,), fetch='one')
    check('#12 La habitación queda con UNA sola reserva en la base de datos',
          filas['c'] == 1, f"filas={filas['c']}")

    print('\n=== #17 (F26) Fallo a mitad del check-out ===')

    # Reserva sana en estado checkin para provocar el fallo.
    rid = exitos[0]
    sql("UPDATE reservas SET estado = 'checkin' WHERE id = %s", (rid,))
    sql("UPDATE habitaciones SET estado = 'ocupada' WHERE id = %s", (hab_id,))

    estado_previo = sql('SELECT estado FROM reservas WHERE id = %s', (rid,),
                        fetch='one')['estado']
    hab_previa = sql('SELECT estado FROM habitaciones WHERE id = %s', (hab_id,),
                     fetch='one')['estado']

    # Inyectamos un fallo justo DESPUÉS de cambiar el estado de la reserva,
    # cuando el checkout va a mover las habitaciones.
    original = ReservaModel._habitaciones_de
    llamadas = {'n': 0}

    def explota(self, cursor, reserva_id):
        llamadas['n'] += 1
        raise RuntimeError('fallo inyectado a mitad del check-out')

    ReservaModel._habitaciones_de = explota
    try:
        model.checkout(rid, empleado_id=None, forzar=True, motivo='prueba')
        fallo_propagado = False
    except RuntimeError:
        fallo_propagado = True
    finally:
        ReservaModel._habitaciones_de = original

    estado_final = sql('SELECT estado FROM reservas WHERE id = %s', (rid,),
                       fetch='one')['estado']
    hab_final = sql('SELECT estado FROM habitaciones WHERE id = %s', (hab_id,),
                    fetch='one')['estado']

    check('#17 El fallo se propaga (no se traga en un console.warn)',
          fallo_propagado and llamadas['n'] == 1)
    check('#17 La reserva NO quedó cerrada a medias',
          estado_final == estado_previo,
          f'{estado_previo} → {estado_final}')
    check('#17 La habitación NO quedó a medias',
          hab_final == hab_previa, f'{hab_previa} → {hab_final}')

    limpiar()

    print('\n' + '=' * 70)
    pasan = sum(1 for _, ok in resultados if ok)
    print(f'{pasan}/{len(resultados)} pruebas pasan')
    return 0 if pasan == len(resultados) else 1


if __name__ == '__main__':
    sys.exit(main())
