from flask import request

from Models.rol_model import RolModel
from utils import respuestas
from utils.decorators import requiere_permiso

model = RolModel()

@requiere_permiso('roles.gestionar')
def get_all_roles():
    return respuestas.lista(model.get_all())

@requiere_permiso('roles.gestionar')
def get_rol(id):
    rol = model.get_by_id(id)
    if not rol:
        return respuestas.error('Rol no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.recurso(rol)

@requiere_permiso('roles.gestionar')
def create_rol():
    data = request.json
    if not data or not data.get('nombre'):
        return respuestas.error('nombre es requerido', 400,
                                codigo='CAMPOS_REQUERIDOS')
    new_id = model.create(data)
    return respuestas.creado(model.get_by_id(new_id), mensaje='Rol creado')

@requiere_permiso('roles.gestionar')
def update_rol(id):
    data = request.json
    affected = model.update(id, data)
    if not affected:
        return respuestas.error('Rol no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.recurso(model.get_by_id(id), mensaje='Rol actualizado')

@requiere_permiso('roles.gestionar')
def delete_rol(id):
    affected = model.delete(id)
    if not affected:
        return respuestas.error('Rol no encontrado', 404, codigo='NO_ENCONTRADO')
    return respuestas.sin_contenido('Rol eliminado')

@requiere_permiso('roles.gestionar')
def get_permisos_rol(rol_id):
    return respuestas.lista(model.get_permisos(rol_id))

@requiere_permiso('roles.gestionar')
def asignar_permiso_rol(rol_id):
    data = request.json
    if not data or not data.get('permiso_id'):
        return respuestas.error('permiso_id es requerido', 400,
                                codigo='CAMPOS_REQUERIDOS')
    model.asignar_permiso(rol_id, data['permiso_id'])
    return respuestas.lista(model.get_permisos(rol_id))

@requiere_permiso('roles.gestionar')
def quitar_permiso_rol(rol_id, permiso_id):
    model.quitar_permiso(rol_id, permiso_id)
    return respuestas.lista(model.get_permisos(rol_id))