from flask import request

from Models.cuadre_caja_model import CAMPOS, CuadreCajaModel, calcular_total
from utils import respuestas
from utils.decorators import empleado_actual_id, requiere_permiso
from utils.validacion import a_decimal, descartados, filtrar

model = CuadreCajaModel()

# §7.3 — `total_movimiento` NO está: lo calcula el servidor.
# `empleado_id` tampoco: sale del JWT (F38).
CAMPOS_CUADRE = ('fecha',) + CAMPOS + ('observaciones',)


def _validar_importes(data):
    for campo in CAMPOS:
        if campo in data:
            a_decimal(data[campo], campo=campo, minimo=0)


@requiere_permiso('caja.ver')
def get_all_cuadres():
    return respuestas.lista(model.get_all())


@requiere_permiso('caja.ver')
def get_cuadre(id):
    cuadre = model.get_by_id(id)
    if not cuadre:
        return respuestas.error('Cuadre no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.recurso(cuadre)


@requiere_permiso('caja.ver')
def get_cuadres_fecha(fecha):
    try:
        return respuestas.lista(model.get_by_fecha(fecha))
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')


@requiere_permiso('caja.ver')
def get_resumen_dia(fecha):
    """
    GET /caja/resumen/<fecha> — lo que realmente entró ese día según los pagos
    registrados, para contrastarlo con lo que declara el cuadre.

    El día es el día calendario de Bogotá, así que un pago de las 20:30 cuenta
    en el cuadre de hoy y no en el de mañana (F16).
    """
    try:
        return respuestas.recurso(model.resumen_del_dia(fecha))
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')


@requiere_permiso('caja.crear')
def create_cuadre():
    """
    §7.3 — El total lo calcula el servidor:

        saldo_anterior + efectivo + tarjetas + consignacion + factura_cxc
        + factura_credito - gastos_turno

    La fórmula anterior, que vivía en el navegador, ignoraba `efectivo` y
    `saldo_anterior`.
    """
    data, faltantes = filtrar(request.json, CAMPOS_CUADRE,
                              obligatorios=('fecha',))
    if faltantes:
        return respuestas.error('fecha es requerida', 400,
                                codigo='CAMPOS_REQUERIDOS')

    try:
        _validar_importes(data)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    nuevo_id = model.create(data, empleado_id=empleado_actual_id())
    return respuestas.creado(
        model.get_by_id(nuevo_id),
        mensaje='Cuadre de caja creado',
        ignorados=descartados(request.json, CAMPOS_CUADRE),
    )


@requiere_permiso('caja.crear')
def update_cuadre(id):
    data, _ = filtrar(request.json, CAMPOS_CUADRE)
    if not data:
        return respuestas.error('No se envió ningún campo editable', 400,
                                codigo='SIN_CAMBIOS')

    try:
        _validar_importes(data)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    afectadas = model.update(id, data, empleado_id=empleado_actual_id())
    if not afectadas:
        return respuestas.error('Cuadre no encontrado', 404, codigo='NO_ENCONTRADO')

    return respuestas.recurso(model.get_by_id(id), mensaje='Cuadre actualizado',
                              ignorados=descartados(request.json, CAMPOS_CUADRE))


@requiere_permiso('caja.crear')
def delete_cuadre(id):
    afectadas = model.delete(id)
    if not afectadas:
        return respuestas.error('Cuadre no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Cuadre eliminado')
