from flask import request

from Models.pago_model import METODOS_VALIDOS, PagoModel, SaldoInsuficiente
from utils import respuestas
from utils.decorators import empleado_actual_id, requiere_permiso, tiene_permiso
from utils.validacion import a_decimal, a_entero, descartados, filtrar

model = PagoModel()

# §4.2 — Lo único que el cliente puede decidir de un pago. `monto` es opcional
# (sólo para abonos parciales) y `empleado_id` no está: sale del JWT.
CAMPOS_CREAR = ('reserva_id', 'metodo', 'referencia', 'notas', 'monto',
                'fecha_pago')

# F17 — En una edición sólo se tocan los datos descriptivos.
CAMPOS_EDITAR = ('metodo', 'referencia', 'notas', 'fecha_pago')


@requiere_permiso('pagos.registrar')
def get_pagos():
    """
    §4.4 — Listado filtrable y paginado.

    Antes devolvía TODOS los pagos del hotel y el frontend los filtraba en
    memoria sólo para saber si una reserva estaba saldada. Ahora:

      * sin `reserva_id`, hace falta el permiso `pagos.ver_todos`;
      * `?reserva_id=42`, `?desde=&hasta=`, `?limite=&offset=`.
    """
    try:
        reserva_id = a_entero(request.args.get('reserva_id'),
                              campo='reserva_id', minimo=1, permite_none=True)
        limite = a_entero(request.args.get('limite', 100), campo='limite',
                          minimo=1, maximo=500)
        offset = a_entero(request.args.get('offset', 0), campo='offset', minimo=0)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    if reserva_id is None and not tiene_permiso('pagos.ver_todos'):
        return respuestas.error(
            'Para listar todos los pagos hace falta el permiso pagos.ver_todos. '
            'Filtra por reserva_id.',
            403, codigo='PERMISO_DENEGADO', permiso='pagos.ver_todos')

    try:
        filas, total = model.buscar(
            reserva_id=reserva_id,
            desde=request.args.get('desde'),
            hasta=request.args.get('hasta'),
            incluir_anulados=request.args.get('incluir_anulados') == 'true',
            limite=limite,
            offset=offset,
        )
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    return respuestas.lista(filas, total=total, limite=limite, offset=offset)


@requiere_permiso('pagos.registrar')
def get_pagos_reserva(reserva_id):
    return respuestas.lista(model.get_by_reserva(reserva_id))


@requiere_permiso('pagos.registrar')
def get_pago(id):
    pago = model.get_by_id(id)
    if not pago:
        return respuestas.error('Pago no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.recurso(pago)


@requiere_permiso('pagos.registrar')
def get_pagos_fecha(fecha):
    try:
        return respuestas.lista(model.get_by_fecha(fecha))
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')


@requiere_permiso('pagos.registrar')
def get_total_pagado(reserva_id):
    return respuestas.recurso(model.get_total_by_reserva(reserva_id))


@requiere_permiso('pagos.registrar')
def create_pago():
    """
    §4.2 — El servidor decide cuánto se cobra.

    Sin `monto`, cobra el saldo pendiente completo. Con `monto`, valida
    `0 < monto <= saldo_pendiente`. `empleado_id` sale del JWT: si viene en el
    body se ignora, y por eso ya no se puede falsificar quién cobró (F34).
    """
    data, faltantes = filtrar(request.json, CAMPOS_CREAR,
                              obligatorios=('reserva_id',))
    if faltantes:
        return respuestas.error('reserva_id es requerido', 400,
                                codigo='CAMPOS_REQUERIDOS')

    metodo = data.get('metodo') or 'efectivo'
    if metodo not in METODOS_VALIDOS:
        return respuestas.error(
            f'Método de pago inválido. Válidos: {list(METODOS_VALIDOS)}', 400,
            codigo='METODO_INVALIDO')

    try:
        monto = a_decimal(data.get('monto'), campo='monto', permite_none=True)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    try:
        pago, financiero = model.registrar(
            data['reserva_id'],
            empleado_actual_id(),
            metodo=metodo,
            monto=monto,
            referencia=data.get('referencia'),
            notas=data.get('notas'),
            fecha_pago=data.get('fecha_pago'),
        )
    except SaldoInsuficiente as exc:
        status = 409 if exc.codigo == 'RESERVA_SALDADA' else 422
        return respuestas.error(str(exc), status, codigo=exc.codigo,
                                saldo_pendiente=exc.saldo)
    except ValueError as exc:
        if str(exc) == 'reserva_no_encontrada':
            return respuestas.error('Reserva no encontrada', 404,
                                    codigo='NO_ENCONTRADO')
        return respuestas.error('Error de validación', 400, codigo='VALIDACION')

    return respuestas.creado(
        {
            'pago': pago,
            'reserva': {
                'id': financiero['id'],
                'total_cuenta': financiero['total_cuenta'],
                'total_pagado': financiero['total_pagado'],
                'saldo_pendiente': financiero['saldo_pendiente'],
                'estado_pago': financiero['estado_pago'],
            },
        },
        mensaje='Pago registrado',
        ignorados=descartados(request.json, CAMPOS_CREAR),
    )


@requiere_permiso('pagos.registrar')
def update_pago(id):
    """
    F17 — `monto`, `reserva_id` y `empleado_id` se ignoran aunque vengan.
    Para corregir un importe hay que anular y volver a cobrar.
    """
    data, _ = filtrar(request.json, CAMPOS_EDITAR)
    ignorados = descartados(request.json, CAMPOS_EDITAR)

    if not data:
        return respuestas.error(
            'No se envió ningún campo editable. Para corregir un importe, '
            'anula el pago y registra uno nuevo.',
            400, codigo='SIN_CAMBIOS', campos_editables=list(CAMPOS_EDITAR),
            ignorados=ignorados)

    try:
        afectadas = model.actualizar_datos(id, data)
    except ValueError:
        return respuestas.error(
            f'Método de pago inválido. Válidos: {list(METODOS_VALIDOS)}', 400,
            codigo='METODO_INVALIDO')

    if not afectadas:
        return respuestas.error('Pago no encontrado o anulado', 404,
                                codigo='NO_ENCONTRADO')

    return respuestas.recurso(model.get_by_id(id), mensaje='Pago actualizado',
                              ignorados=ignorados)


@requiere_permiso('pagos.anular')
def anular_pago(id):
    """
    POST /pagos/<id>/anular — la vía correcta para deshacer un cobro.

    El pago no se borra: queda marcado con quién lo anuló, cuándo y por qué.
    Los consumos que ese pago había saldado vuelven a 'pendiente'.
    """
    data = request.json or {}
    motivo = (data.get('motivo') or '').strip()
    if not motivo:
        return respuestas.error('motivo es requerido para anular un pago', 400,
                                codigo='CAMPOS_REQUERIDOS')

    pago, financiero = model.anular(id, empleado_actual_id(), motivo)
    if not pago:
        return respuestas.error('Pago no encontrado o ya anulado', 404,
                                codigo='NO_ENCONTRADO')

    return respuestas.recurso(
        {
            'pago': pago,
            'reserva': {
                'id': financiero['id'],
                'saldo_pendiente': financiero['saldo_pendiente'],
                'estado_pago': financiero['estado_pago'],
            },
        },
        mensaje='Pago anulado',
    )


@requiere_permiso('pagos.anular')
def delete_pago(id):
    afectadas = model.delete(id)
    if not afectadas:
        return respuestas.error('Pago no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Pago eliminado')
