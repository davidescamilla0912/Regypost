from flask import request

from Models.tipo_habitacion_model import TipoHabitacionModel
from utils import respuestas
from utils.decorators import requiere_permiso
from utils.validacion import a_decimal, a_entero, filtrar, fusionar

model = TipoHabitacionModel()

CAMPOS_TIPO = ('nombre', 'descripcion', 'capacidad', 'precio_base')


@requiere_permiso('habitaciones.ver')
def get_all_tipos():
    return respuestas.lista(model.get_all())


@requiere_permiso('habitaciones.ver')
def get_tipo(id):
    tipo = model.get_by_id(id)
    if not tipo:
        return respuestas.error('Tipo no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.recurso(tipo)


def _validar(data):
    if 'precio_base' in data:
        a_decimal(data['precio_base'], campo='precio_base', minimo=0)
    if 'capacidad' in data:
        a_entero(data['capacidad'], campo='capacidad', minimo=1, maximo=20)


@requiere_permiso('habitaciones.editar')
def create_tipo():
    data, faltantes = filtrar(request.json, CAMPOS_TIPO,
                              obligatorios=('nombre',))
    if faltantes:
        return respuestas.error('nombre es requerido', 400,
                                codigo='CAMPOS_REQUERIDOS')
    try:
        _validar(data)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    nuevo_id = model.create(data)
    return respuestas.creado(model.get_by_id(nuevo_id), mensaje='Tipo creado')


@requiere_permiso('habitaciones.editar')
def update_tipo(id):
    data, _ = filtrar(request.json, CAMPOS_TIPO)
    if not data:
        return respuestas.error('No se envió ningún campo editable', 400,
                                codigo='SIN_CAMBIOS')
    try:
        _validar(data)
    except ValueError as exc:
        return respuestas.error(str(exc), 400, codigo='VALIDACION')

    actual = model.get_by_id(id)
    if not actual:
        return respuestas.error('Tipo no encontrado', 404, codigo='NO_ENCONTRADO')

    afectadas = model.update(id, fusionar(actual, data, CAMPOS_TIPO))
    if not afectadas:
        return respuestas.error('Tipo no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.recurso(model.get_by_id(id), mensaje='Tipo actualizado')


@requiere_permiso('habitaciones.editar')
def delete_tipo(id):
    afectadas = model.delete(id)
    if not afectadas:
        return respuestas.error('Tipo no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Tipo eliminado')
