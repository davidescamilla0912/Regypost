from flask import request
from flask_jwt_extended import jwt_required

from Models.parqueadero_model import ParqueaderoModel
from utils import respuestas
from utils.validacion import a_decimal, descartados, filtrar

model = ParqueaderoModel()

CAMPOS_ENTRADA = ('reserva_id', 'habitacion_id', 'placa', 'hora_entrada',
                  'valor', 'notas')
CAMPOS_SALIDA = ('hora_salida', 'valor', 'notas')


@jwt_required()
def get_all_parqueadero():
    return respuestas.lista(model.get_all())


@jwt_required()
def get_parqueadero(id):
    registro = model.get_by_id(id)
    if not registro:
        return respuestas.error('Registro no encontrado', 404,
                                codigo='NO_ENCONTRADO')
    return respuestas.recurso(registro)


@jwt_required()
def get_parqueadero_activos():
    return respuestas.lista(model.get_activos())


@jwt_required()
def get_parqueadero_placa(placa):
    return respuestas.lista(model.get_by_placa(placa))


@jwt_required()
def create_parqueadero():
    data, faltantes = filtrar(request.json, CAMPOS_ENTRADA,
                              obligatorios=('placa', 'hora_entrada'))
    if faltantes:
        return respuestas.error(
            f"Faltan campos requeridos: {', '.join(faltantes)}", 400,
            codigo='CAMPOS_REQUERIDOS', campos=faltantes)

    # §7.4 / F14 — El cobro salía de un `prompt()` del navegador. El servidor
    # valida que sea numérico y no negativo.
    try:
        a_decimal(data.get('valor', 0), campo='valor', minimo=0)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    try:
        nuevo_id = model.create(data)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    return respuestas.creado(model.get_by_id(nuevo_id),
                             mensaje='Entrada registrada',
                             ignorados=descartados(request.json, CAMPOS_ENTRADA))


@jwt_required()
def registrar_salida(id):
    data, faltantes = filtrar(request.json, CAMPOS_SALIDA,
                              obligatorios=('hora_salida',))
    if faltantes:
        return respuestas.error('hora_salida es requerida', 400,
                                codigo='CAMPOS_REQUERIDOS')

    try:
        a_decimal(data.get('valor', 0), campo='valor', minimo=0)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    try:
        afectadas = model.registrar_salida(id, data)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    if not afectadas:
        return respuestas.error('Registro no encontrado', 404,
                                codigo='NO_ENCONTRADO')

    return respuestas.recurso(model.get_by_id(id), mensaje='Salida registrada')


@jwt_required()
def delete_parqueadero(id):
    afectadas = model.delete(id)
    if not afectadas:
        return respuestas.error('Registro no encontrado', 404,
                                codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Registro eliminado')
