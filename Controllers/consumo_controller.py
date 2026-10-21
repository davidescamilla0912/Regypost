from flask import request
from flask_jwt_extended import jwt_required

from Models.consumo_model import ConsumoModel
from Models.pago_model import METODOS_VALIDOS
from utils import respuestas
from utils.decorators import empleado_actual_id, requiere_permiso
from utils.validacion import a_decimal, descartados, filtrar

model = ConsumoModel()

# §4.3 / §5.2 — `estado` NO está en la allowlist: un consumo nunca nace pagado.
# `empleado_id` tampoco: sale del JWT.
CAMPOS_CREAR = ('reserva_habitacion_id', 'tipo_consumo_id', 'descripcion',
                'cantidad', 'precio_unitario', 'fecha')

CAMPOS_DANO = ('reserva_habitacion_id', 'descripcion', 'precio_unitario', 'fecha')


@requiere_permiso('consumos.registrar')
def get_consumos_reserva(reserva_id):
    return respuestas.lista(model.get_by_reserva(reserva_id))


@requiere_permiso('consumos.registrar')
def get_consumo(id):
    consumo = model.get_by_id(id)
    if not consumo:
        return respuestas.error('Consumo no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.recurso(consumo)


@requiere_permiso('consumos.consultar')
def get_consumos_fecha(fecha):
    try:
        return respuestas.lista(model.get_by_fecha(fecha))
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')


@jwt_required()
def get_tipos_consumo():
    return respuestas.lista(model.get_tipos_consumo())


@requiere_permiso('consumos.registrar')
def create_consumo():
    """
    §4.3 — Todo consumo nace 'pendiente'.

    El campo `estado` que enviaba la casilla "Marcar como pagado" se descarta:
    marcar un consumo pagado sin un pago real hacía desaparecer el dinero de
    la contabilidad. Para cobrarlo en el momento está `POST /consumos/:id/cobrar`.
    """
    data, faltantes = filtrar(
        request.json, CAMPOS_CREAR,
        obligatorios=('reserva_habitacion_id', 'tipo_consumo_id'),
    )
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    try:
        a_decimal(data.get('cantidad', 1), campo='cantidad', minimo=0)
        a_decimal(data.get('precio_unitario', 0), campo='precio_unitario', minimo=0)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    try:
        nuevo_id = model.create(data, empleado_id=empleado_actual_id())
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    ignorados = descartados(request.json, CAMPOS_CREAR)
    return respuestas.creado(
        model.get_by_id(nuevo_id),
        mensaje='Consumo registrado',
        ignorados=ignorados,
        aviso=('El campo "estado" se ignora: un consumo sólo queda pagado '
               'mediante POST /consumos/<id>/cobrar o un pago que lo cubra.')
        if 'estado' in ignorados else None,
    )


@requiere_permiso('pagos.registrar')
def cobrar_consumo(id):
    """
    §4.3 punto 3 — POST /consumos/<id>/cobrar

    Crea el pago y marca el consumo como pagado en la MISMA transacción, así
    que siempre queda un registro en `/pagos` detrás del consumo saldado.
    """
    data = request.json or {}
    metodo = data.get('metodo') or 'efectivo'
    if metodo not in METODOS_VALIDOS:
        return respuestas.error(
            f'Método de pago inválido. Válidos: {list(METODOS_VALIDOS)}', 400,
            codigo='METODO_INVALIDO')

    try:
        consumo, pago, financiero = model.cobrar(id, empleado_actual_id(), metodo)
    except ValueError as exc:
        errores = {
            'no_encontrado': ('Consumo no encontrado', 404, 'NO_ENCONTRADO'),
            'ya_cobrado': ('El consumo ya está cobrado', 409, 'CONSUMO_YA_COBRADO'),
            'monto_invalido': ('El consumo no tiene un importe que cobrar', 400,
                               'VALIDACION'),
        }
        mensaje, status, codigo = errores.get(
            str(exc), ('Error de validación', 400, 'VALIDACION'))
        return respuestas.error(mensaje, status, codigo=codigo)

    return respuestas.creado(
        {
            'consumo': consumo,
            'pago': pago,
            'reserva': {
                'id': financiero['id'],
                'saldo_pendiente': financiero['saldo_pendiente'],
                'estado_pago': financiero['estado_pago'],
            },
        },
        mensaje='Consumo cobrado',
    )


@requiere_permiso('consumos.registrar')
def create_dano():
    data, faltantes = filtrar(
        request.json, CAMPOS_DANO,
        obligatorios=('reserva_habitacion_id', 'descripcion'),
    )
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    try:
        precio = a_decimal(data.get('precio_unitario'), campo='precio_unitario',
                           minimo=0)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    if precio <= 0:
        return respuestas.error('precio_unitario debe ser mayor que 0', 400,
                                codigo='VALIDACION')

    try:
        nuevo_id = model.create_dano(data, empleado_id=empleado_actual_id())
    except ValueError as exc:
        if str(exc) == 'tipo_dano_no_configurado':
            return respuestas.error(
                'El tipo de consumo "Daño" no está configurado en la base de datos',
                500, codigo='CONFIGURACION')
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    return respuestas.creado(model.get_by_id(nuevo_id),
                             mensaje='Daño registrado')


@requiere_permiso('consumos.registrar')
def update_consumo(id):
    data, faltantes = filtrar(request.json, CAMPOS_CREAR,
                              obligatorios=('tipo_consumo_id',))
    if faltantes:
        return respuestas.error('tipo_consumo_id es requerido', 400,
                                codigo='CAMPOS_REQUERIDOS')

    try:
        afectadas = model.update(id, data, empleado_id=empleado_actual_id())
    except ValueError as exc:
        if str(exc) == 'consumo_ya_cobrado':
            return respuestas.error(
                'No se puede editar un consumo ya cobrado. Anula primero el pago.',
                409, codigo='CONSUMO_YA_COBRADO')
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    if not afectadas:
        return respuestas.error('Consumo no encontrado', 404, codigo='NO_ENCONTRADO')

    return respuestas.recurso(model.get_by_id(id), mensaje='Consumo actualizado',
                              ignorados=descartados(request.json, CAMPOS_CREAR))


@requiere_permiso('consumos.registrar')
def delete_consumo(id):
    try:
        afectadas = model.delete(id)
    except ValueError as exc:
        if str(exc) == 'consumo_ya_cobrado':
            return respuestas.error(
                'No se puede eliminar un consumo ya cobrado. Anula primero el pago.',
                409, codigo='CONSUMO_YA_COBRADO')
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    if not afectadas:
        return respuestas.error('Consumo no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Consumo eliminado')


# Alias con el nombre original del identificador.
create_daño = create_dano
