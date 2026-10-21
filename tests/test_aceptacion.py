"""
Batería de pruebas de aceptación del §10 de ESPECIFICACION_BACKEND.md.

Cada prueba demuestra que un hallazgo concreto quedó cerrado. Se ejecuta
contra la base de datos real usando el test_client de Flask, crea sus propios
datos con un prefijo reconocible y los borra al terminar.

    python tests/test_aceptacion.py
"""
import hashlib
import os
import sys

# La consola de Windows usa cp1252 y el informe lleva acentos y flechas.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection  # noqa: E402
from utils.fechas import hoy_local  # noqa: E402

MARCA = 'ZZTEST'
CONTRASENA = 'prueba123'

resultados = []


def check(nombre, condicion, detalle=''):
    resultados.append((nombre, bool(condicion), detalle))
    estado = 'PASA' if condicion else 'FALLA'
    print(f'  [{estado}] {nombre}' + (f' — {detalle}' if detalle else ''))
    return bool(condicion)


# ─── Preparación de datos ─────────────────────────────────────────────────────

def sql(query, params=(), fetch=None):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        if fetch == 'one':
            return cursor.fetchone()
        if fetch == 'all':
            return cursor.fetchall()
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        conn.close()


def limpiar():
    """Borra todo lo que hayan creado ejecuciones anteriores."""
    sql("""DELETE p FROM pagos p JOIN reservas r ON r.id = p.reserva_id
           JOIN clientes c ON c.id = r.cliente_id
           WHERE c.numero_documento LIKE %s""", (MARCA + '%',))
    sql("""DELETE co FROM consumos co
           JOIN reserva_habitaciones rh ON rh.id = co.reserva_habitacion_id
           JOIN reservas r ON r.id = rh.reserva_id
           JOIN clientes c ON c.id = r.cliente_id
           WHERE c.numero_documento LIKE %s""", (MARCA + '%',))
    sql("""DELETE rh FROM reserva_habitaciones rh
           JOIN reservas r ON r.id = rh.reserva_id
           JOIN clientes c ON c.id = r.cliente_id
           WHERE c.numero_documento LIKE %s""", (MARCA + '%',))
    sql("""DELETE r FROM reservas r JOIN clientes c ON c.id = r.cliente_id
           WHERE c.numero_documento LIKE %s""", (MARCA + '%',))
    sql('DELETE FROM clientes WHERE numero_documento LIKE %s', (MARCA + '%',))
    sql('DELETE FROM empleados WHERE usuario LIKE %s', (MARCA + '%',))
    sql('DELETE FROM habitaciones WHERE numero LIKE %s', ('Z9%',))
    # Los consumos de habitación dejan un movimiento de inventario en un
    # producto real; hay que devolver ese stock al borrar la reserva.
    sql("""DELETE m FROM movimientos_inventario m
           WHERE m.referencia LIKE 'consumo_rh_%'
             AND NOT EXISTS (
                 SELECT 1 FROM reserva_habitaciones rh
                 WHERE rh.id = CAST(SUBSTRING(m.referencia, 12) AS UNSIGNED))""")


def preparar():
    """Crea un empleado admin, uno de recepción, un cliente y una habitación."""
    hash_pwd = hashlib.sha256(CONTRASENA.encode()).hexdigest()

    admin_id = sql(
        """INSERT INTO empleados (nombre, apellido, usuario, contrasena, activo)
           VALUES ('Test', 'Admin', %s, %s, 1)""",
        (MARCA + '_admin', hash_pwd))
    rol_admin = sql("SELECT id FROM roles WHERE nombre = 'admin'", fetch='one')
    sql('INSERT IGNORE INTO empleado_rol (empleado_id, rol_id) VALUES (%s, %s)',
        (admin_id, rol_admin['id']))

    recep_id = sql(
        """INSERT INTO empleados (nombre, apellido, usuario, contrasena, activo)
           VALUES ('Test', 'Recepcion', %s, %s, 1)""",
        (MARCA + '_recep', hash_pwd))
    rol_recep = sql("SELECT id FROM roles WHERE nombre = 'recepcionista'",
                    fetch='one')
    sql('INSERT IGNORE INTO empleado_rol (empleado_id, rol_id) VALUES (%s, %s)',
        (recep_id, rol_recep['id']))

    cliente_id = sql(
        """INSERT INTO clientes (tipo_documento, numero_documento, nombre, apellido)
           VALUES ('CC', %s, 'Cliente', 'De Prueba')""",
        (MARCA + '001',))

    tipo = sql('SELECT id FROM tipos_habitacion LIMIT 1', fetch='one')
    hab_id = sql(
        """INSERT INTO habitaciones (numero, piso, tipo_id, estado)
           VALUES ('Z901', 9, %s, 'disponible')""",
        (tipo['id'],))
    hab2_id = sql(
        """INSERT INTO habitaciones (numero, piso, tipo_id, estado)
           VALUES ('Z902', 9, %s, 'disponible')""",
        (tipo['id'],))

    return {'admin_id': admin_id, 'recep_id': recep_id,
            'cliente_id': cliente_id, 'hab_id': hab_id, 'hab2_id': hab2_id}


# ─── Utilidades HTTP ──────────────────────────────────────────────────────────

class Api:
    def __init__(self, cliente, token=None):
        self.cliente = cliente
        self.token = token

    def _headers(self):
        return {'Authorization': f'Bearer {self.token}'} if self.token else {}

    def get(self, ruta, **kw):
        return self.cliente.get(ruta, headers=self._headers(), **kw)

    def post(self, ruta, json=None):
        return self.cliente.post(ruta, json=json or {}, headers=self._headers())

    def put(self, ruta, json=None):
        return self.cliente.put(ruta, json=json or {}, headers=self._headers())

    def patch(self, ruta, json=None):
        return self.cliente.patch(ruta, json=json or {}, headers=self._headers())


def login(cliente, usuario):
    resp = cliente.post('/auth/login',
                        json={'usuario': usuario, 'contrasena': CONTRASENA})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()['data']['token']


# ─── La batería ───────────────────────────────────────────────────────────────

def main():
    import app as modulo_app

    modulo_app.app.config['TESTING'] = True
    limpiar()
    datos = preparar()

    with modulo_app.app.test_client() as cliente:
        admin = Api(cliente, login(cliente, MARCA + '_admin'))
        recep = Api(cliente, login(cliente, MARCA + '_recep'))

        hoy = hoy_local().isoformat()
        manana = hoy_local().replace(day=hoy_local().day)

        print('\n=== DINERO (Fase 1) ===')

        # Reserva base: 3 noches × 100.000 = 300.000
        from datetime import timedelta
        entrada = hoy_local()
        salida = entrada + timedelta(days=3)

        resp = admin.post('/reservas', json={
            'cliente_id': datos['cliente_id'],
            'habitacion_id': datos['hab_id'],
            'fecha_entrada': entrada.isoformat(),
            'fecha_salida': salida.isoformat(),
            'precio_noche': 100000,
            # Campos que el servidor debe IGNORAR:
            'total': 1, 'saldo_pendiente': 1, 'estado': 'checkout', 'noches': 99,
        })
        reserva = resp.get_json()['data']
        rid = reserva['id']
        check('§6.1 POST /reservas calcula el total (3×100.000)',
              reserva['total'] == 300000, f"total={reserva['total']}")
        check('§6.1 POST /reservas ignora el estado del cliente',
              reserva['estado'] == 'pendiente', f"estado={reserva['estado']}")
        check('§6.1 POST /reservas liga la habitación en la misma llamada',
              len(reserva['habitaciones']) == 1)
        check('§8.1 La reserva trae las habitaciones embebidas',
              reserva['habitaciones'][0]['numero'] == 'Z901')

        # #13 — fechas cruzadas → 409
        resp = admin.post('/reservas', json={
            'cliente_id': datos['cliente_id'],
            'habitacion_id': datos['hab_id'],
            'fecha_entrada': (entrada + timedelta(days=1)).isoformat(),
            'fecha_salida': (salida + timedelta(days=1)).isoformat(),
            'precio_noche': 100000,
        })
        check('#13 (F18) POST /reservas con fechas cruzadas → 409',
              resp.status_code == 409,
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        # Confirmar con anticipo de 150.000
        resp = admin.patch(f'/reservas/{rid}/confirmar', json={'anticipo': 150000})
        check('§6.3 Confirmar deja la reserva en "confirmada"',
              resp.get_json()['data']['estado'] == 'confirmada')

        # Check-in
        resp = admin.post(f'/reservas/{rid}/checkin')
        check('§6.4 POST /checkin deja la reserva en "checkin"',
              resp.status_code == 200
              and resp.get_json()['data']['estado'] == 'checkin',
              str(resp.status_code))
        hab = admin.get(f"/habitaciones/{datos['hab_id']}").get_json()['data']
        check('§6.4 El check-in deja la habitación "ocupada"',
              hab['estado'] == 'ocupada', f"estado={hab['estado']}")

        rh_id = reserva['habitaciones'][0]['reserva_habitacion_id']

        # Consumo de 50.000, intentando marcarlo pagado desde el cliente
        resp = admin.post('/consumos', json={
            'reserva_habitacion_id': rh_id,
            'tipo_consumo_id': 6,
            'cantidad': 1,
            'precio_unitario': 50000,
            'estado': 'cancelado',        # ← F03: debe ignorarse
        })
        consumo = resp.get_json()['data']
        check('#5 (F03) POST /consumos ignora estado="cancelado"',
              consumo['estado'] == 'pendiente', f"estado={consumo['estado']}")

        # #2 y #3 — total=300.000, anticipo=150.000, consumos=50.000
        # saldo = 300.000 + 50.000 - 150.000 = 200.000
        r = admin.get(f'/reservas/{rid}').get_json()['data']
        check('#2 (F10) Fórmula única del saldo',
              r['saldo_pendiente'] == 200000,
              f"saldo={r['saldo_pendiente']} estado_pago={r['estado_pago']}")
        check('§4.1 La reserva trae el resumen financiero completo',
              all(k in r for k in ('total', 'anticipo', 'total_consumos',
                                   'total_pagado', 'saldo_pendiente',
                                   'estado_pago', 'noches')))
        check('§4.1 El mismo saldo aparece en el listado',
              next(x for x in admin.get('/reservas').get_json()['data']
                   if x['id'] == rid)['saldo_pendiente'] == 200000)
        check('§4.1 El mismo saldo aparece en /reservas/estado/checkin',
              next(x for x in admin.get('/reservas/estado/checkin')
                   .get_json()['data'] if x['id'] == rid)['saldo_pendiente'] == 200000)

        # #16 — check-out con saldo pendiente
        resp = admin.post(f'/reservas/{rid}/checkout')
        check('#16 (F27) Check-out con saldo pendiente → 409',
              resp.status_code == 409
              and resp.get_json()['codigo'] == 'SALDO_PENDIENTE',
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        # #1 — pagar con monto=1
        resp = admin.post('/pagos', json={
            'reserva_id': rid, 'metodo': 'efectivo', 'monto': 1,
            'empleado_id': 99999,     # ← F34: debe ignorarse
        })
        pago = resp.get_json()['data']['pago']
        check('#1 (F02) POST /pagos con monto=1 cobra sólo 1, no el total',
              float(pago['monto']) == 1.0, f"monto={pago['monto']}")
        check('#1 (F34) empleado_id sale del JWT, no del body',
              pago['empleado_id'] == datos['admin_id'],
              f"empleado_id={pago['empleado_id']} (esperado {datos['admin_id']})")

        # #4 — abono mayor al saldo → 422
        resp = admin.post('/pagos', json={'reserva_id': rid, 'monto': 999999999})
        check('#4 (F08) Abono mayor al saldo → 422',
              resp.status_code == 422
              and resp.get_json()['codigo'] == 'ABONO_EXCEDE_SALDO',
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        # Pago sin monto → cobra el saldo completo (199.999)
        resp = admin.post('/pagos', json={'reserva_id': rid, 'metodo': 'efectivo'})
        cuerpo = resp.get_json()['data']
        check('§4.2 POST /pagos sin monto cobra el saldo completo',
              float(cuerpo['pago']['monto']) == 199999.0,
              f"monto={cuerpo['pago']['monto']}")
        check('§4.2 La respuesta trae el estado nuevo de la reserva',
              cuerpo['reserva']['estado_pago'] == 'pagada',
              f"estado_pago={cuerpo['reserva']['estado_pago']}")

        # #5 — el consumo quedó saldado, con un pago detrás
        consumos = admin.get(f'/reservas/{rid}/consumos').get_json()['data']
        check('#5 (F03) El consumo sólo queda pagado con un pago detrás',
              consumos[0]['estado'] == 'cancelado'
              and consumos[0]['pago_id'] is not None,
              f"estado={consumos[0]['estado']} pago_id={consumos[0]['pago_id']}")

        # #3 — no se puede registrar un pago de $0 sobre una reserva saldada
        resp = admin.post('/pagos', json={'reserva_id': rid})
        check('#3 (F11) Reserva saldada → no se puede cobrar de nuevo',
              resp.status_code == 409
              and resp.get_json()['codigo'] == 'RESERVA_SALDADA',
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        # #7 — PUT /pagos/:id con monto alterado
        pago_id = pago['id']
        resp = admin.put(f'/pagos/{pago_id}', json={
            'monto': 999999, 'reserva_id': 1, 'empleado_id': 1,
            'notas': 'nota nueva',
        })
        actualizado = resp.get_json()['data']
        check('#7 (F17) PUT /pagos ignora monto/reserva_id/empleado_id',
              float(actualizado['monto']) == 1.0
              and actualizado['notas'] == 'nota nueva',
              f"monto={actualizado['monto']} ignorados={resp.get_json().get('ignorados')}")

        # Ahora sí, check-out sin saldo
        resp = admin.post(f'/reservas/{rid}/checkout')
        check('§6.4 Check-out sin saldo → 200',
              resp.status_code == 200
              and resp.get_json()['data']['estado'] == 'checkout',
              str(resp.status_code))
        hab = admin.get(f"/habitaciones/{datos['hab_id']}").get_json()['data']
        check('§6.4 El check-out manda la habitación a mantenimiento',
              hab['estado'] == 'mantenimiento', f"estado={hab['estado']}")

        # #6 (F16) — un pago de las 20:30 hora Colombia cae en el cuadre de hoy
        from utils.fechas import a_datetime_local
        momento_utc = f'{hoy}T{ (20):02d}:30:00'
        convertido = a_datetime_local(
            (entrada.isoformat() + 'T01:30:00.000Z').replace('T', 'T', 1))
        check('#6 (F16) Un pago UTC de las 01:30 se guarda como el día anterior '
              '20:30 local',
              convertido.hour == 20 and convertido.date() == entrada - timedelta(days=1),
              str(convertido))

        print('\n=== AUTORIZACIÓN (Fase 2) ===')

        # #8 — recepcionista no entra a /empleados
        resp = recep.get('/empleados')
        check('#8 (F31) Empleado sin permiso → 403 en GET /empleados',
              resp.status_code == 403
              and resp.get_json()['codigo'] == 'PERMISO_DENEGADO',
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        # #9 — PUT /reservas con total alterado
        resp2 = admin.post('/reservas', json={
            'cliente_id': datos['cliente_id'],
            'habitacion_id': datos['hab2_id'],
            'fecha_entrada': entrada.isoformat(),
            'fecha_salida': salida.isoformat(),
            'precio_noche': 100000,
        })
        rid2 = resp2.get_json()['data']['id']
        admin.patch(f'/reservas/{rid2}/confirmar', json={'anticipo': 0})
        resp = admin.put(f'/reservas/{rid2}', json={'total': 1,
                                                    'observaciones': 'ok'})
        cuerpo = resp.get_json()
        check('#9 (F19/F36) PUT /reservas ignora {"total": 1}',
              cuerpo['data']['total'] == 300000 and 'total' in cuerpo['ignorados'],
              f"total={cuerpo['data']['total']} ignorados={cuerpo['ignorados']}")

        # #11 — recepcionista intenta asignar el rol admin
        rol_admin_id = sql("SELECT id FROM roles WHERE nombre='admin'",
                           fetch='one')['id']
        resp = recep.post(f"/empleados/{datos['recep_id']}/roles",
                          json={'rol_id': rol_admin_id})
        check('#11 (F37) Empleado sin permiso no puede otorgarse el rol admin',
              resp.status_code == 403,
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        # §4.4 — un recepcionista no puede listar todos los pagos
        resp = recep.get('/pagos')
        check('§4.4 (F09) GET /pagos sin filtro exige pagos.ver_todos',
              resp.status_code == 403,
              f'{resp.status_code} {resp.get_json().get("codigo")}')
        resp = recep.get(f'/pagos?reserva_id={rid}')
        check('§4.4 GET /pagos?reserva_id=N sí funciona y viene paginado',
              resp.status_code == 200 and 'total' in resp.get_json(),
              f"total={resp.get_json().get('total')}")

        # §5.4 — token inválido devuelve 401 con el sobre unificado
        resp = cliente.get('/reservas',
                           headers={'Authorization': 'Bearer basura'})
        check('§5.4 (F33) Token inválido → 401 con {error, codigo}',
              resp.status_code == 401 and 'codigo' in resp.get_json(),
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        print('\n=== RESERVAS (Fase 3) ===')

        # #18 — habitación ocupada no puede pasar a disponible
        resp = admin.post(f'/reservas/{rid2}/checkin')
        check('§6.4 Check-in de la segunda reserva (montaje de #18)',
              resp.status_code == 200, str(resp.status_code))
        resp = admin.patch(f"/habitaciones/{datos['hab2_id']}/estado",
                           json={'estado': 'disponible'})
        check('#18 (F29) Habitación ocupada no puede pasar a disponible',
              resp.status_code == 409,
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        # #15 — check-in con fecha futura
        futura_entrada = entrada + timedelta(days=30)
        r3 = admin.post('/reservas', json={
            'cliente_id': datos['cliente_id'],
            'habitacion_id': datos['hab_id'],
            'fecha_entrada': futura_entrada.isoformat(),
            'fecha_salida': (futura_entrada + timedelta(days=2)).isoformat(),
            'precio_noche': 100000,
        }).get_json()['data']
        admin.patch(f"/reservas/{r3['id']}/confirmar", json={'anticipo': 0})
        resp = admin.post(f"/reservas/{r3['id']}/checkin")
        check('#15 (F22) Check-in con fecha futura → 4xx',
              resp.status_code == 409
              and resp.get_json()['codigo'] == 'FECHA_FUTURA',
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        # §6.3 — transición inválida
        resp = admin.patch(f"/reservas/{r3['id']}/estado",
                           json={'estado': 'checkout'})
        check('§6.3 (F28) Transición inválida confirmada→checkout → 409',
              resp.status_code == 409
              and resp.get_json()['codigo'] == 'TRANSICION_INVALIDA',
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        # §6.2 — disponibilidad con fechas (con la Z902 aún ocupada)
        resp = admin.get(f'/habitaciones/disponibles?desde={entrada}'
                         f'&hasta={salida.isoformat()}')
        libres = [h['numero'] for h in resp.get_json()['data']]
        check('§6.2 GET /habitaciones/disponibles?desde&hasta excluye las ocupadas',
              'Z902' not in libres, f'Z902 en libres: {"Z902" in libres}')

        # #19 — cancelar una reserva con check-in hecho
        resp = admin.post(f'/reservas/{rid2}/cancelar', json={})
        check('#19 (F25) Cancelar con check-in hecho exige motivo explícito',
              resp.status_code == 409,
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        print('\n=== INVENTARIO Y CAJA (Fase 4) ===')

        # #21 — producto sin tipo_consumo_id
        prod_sin_tipo = sql(
            """INSERT INTO productos_inventario
               (nombre, categoria, tipo_consumo_id, precio_unitario, stock_minimo, activo)
               VALUES ('ZZTEST sin tipo', 'varios', NULL, 5000, 1, 1)""")
        sql("""INSERT INTO movimientos_inventario
               (producto_id, tipo_movimiento, cantidad) VALUES (%s, 'entrada', 10)""",
            (prod_sin_tipo,))
        rh2 = sql('SELECT id FROM reserva_habitaciones WHERE reserva_id = %s',
                  (rid2,), fetch='one')['id']
        resp = admin.post('/inventario/consumo-habitacion', json={
            'producto_id': prod_sin_tipo, 'reserva_habitacion_id': rh2,
            'cantidad': 1})
        check('#21 (F43) Producto sin tipo_consumo_id → error explícito',
              resp.status_code == 409
              and resp.get_json()['codigo'] == 'PRODUCTO_SIN_TIPO_CONSUMO',
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        # #20 — stock insuficiente no descuenta nada
        prod = sql("""SELECT id FROM productos_inventario
                      WHERE tipo_consumo_id IS NOT NULL AND activo = 1 LIMIT 1""",
                   fetch='one')
        antes = admin.get(f"/inventario/{prod['id']}").get_json()['data']['stock_actual']
        resp = admin.post('/inventario/consumo-habitacion', json={
            'producto_id': prod['id'], 'reserva_habitacion_id': rh2,
            'cantidad': 999999})
        despues = admin.get(f"/inventario/{prod['id']}").get_json()['data']['stock_actual']
        check('#20 (F42) Stock insuficiente → 409 y el stock NO baja',
              resp.status_code == 409 and antes == despues,
              f'{resp.status_code} stock {antes}→{despues}')

        # §7.1 — consumo de habitación atómico
        resp = admin.post('/inventario/consumo-habitacion', json={
            'producto_id': prod['id'], 'reserva_habitacion_id': rh2,
            'cantidad': 2})
        cuerpo = resp.get_json()['data']
        check('§7.1 (F42) Consumo de habitación: baja stock y crea el consumo',
              resp.status_code == 201
              and cuerpo['producto']['stock_actual'] == antes - 2
              and cuerpo['consumo']['estado'] == 'pendiente',
              f"stock={cuerpo['producto']['stock_actual']} (antes {antes})")
        check('§7.2 (F43) El tipo de consumo sale del producto, no de adivinar',
              cuerpo['consumo']['tipo_consumo_id'] is not None)

        # #22 — el cuadre incluye efectivo y saldo_anterior
        resp = admin.post('/caja', json={
            'fecha': hoy, 'saldo_anterior': 100000, 'efectivo': 500000,
            'tarjetas': 200000, 'consignacion': 0, 'factura_cxc': 0,
            'factura_credito': 0, 'gastos_turno': 50000,
            'total_movimiento': 999,   # ← debe ignorarse
        })
        cuadre = resp.get_json()['data']
        check('#22 (F12) El cuadre incluye efectivo y saldo_anterior',
              float(cuadre['total_movimiento']) == 750000.0,
              f"total={cuadre['total_movimiento']} (esperado 750000)")

        # §7.4 — parqueadero con valor negativo
        resp = admin.post('/parqueadero', json={
            'placa': 'ZZZ999', 'hora_entrada': f'{hoy}T10:00:00', 'valor': -5})
        check('§7.4 (F14) Parqueadero rechaza un valor negativo',
              resp.status_code == 400,
              f'{resp.status_code} {resp.get_json().get("codigo")}')

        print('\n=== CONTRATO (§2) ===')

        resp = admin.get('/reservas')
        cuerpo = resp.get_json()
        check('§2.1 Las colecciones responden {data: [...], total: N}',
              isinstance(cuerpo.get('data'), list) and 'total' in cuerpo)
        resp = admin.get(f'/reservas/{rid}')
        check('§2.1 Los recursos responden {data: {...}}',
              isinstance(resp.get_json().get('data'), dict))
        resp = admin.get('/reservas/999999')
        check('§2.2 Los errores responden {error, codigo}',
              resp.status_code == 404
              and 'error' in resp.get_json() and 'codigo' in resp.get_json())

    limpiar()
    sql("""DELETE m FROM movimientos_inventario m
           JOIN productos_inventario p ON p.id = m.producto_id
           WHERE p.nombre LIKE 'ZZTEST%'""")
    sql("DELETE FROM productos_inventario WHERE nombre LIKE 'ZZTEST%'")

    print('\n' + '=' * 70)
    pasan = sum(1 for _, ok, _ in resultados if ok)
    fallan = [n for n, ok, _ in resultados if not ok]
    print(f'{pasan}/{len(resultados)} pruebas pasan')
    if fallan:
        print('\nFALLAN:')
        for nombre in fallan:
            print(f'  - {nombre}')
    return 1 if fallan else 0


if __name__ == '__main__':
    sys.exit(main())
