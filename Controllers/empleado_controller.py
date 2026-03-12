from flask import request, jsonify
from Models.empleado_model import EmpleadoModel
from utils.decorators import requiere_permiso

model = EmpleadoModel()

@requiere_permiso('empleados.gestionar')
def get_all_empleados():
    return jsonify(model.get_all()), 200

@requiere_permiso('empleados.gestionar')
def get_empleado(id):
    emp = model.get_by_id(id)
    if not emp:
        return jsonify({"error": "Empleado no encontrado"}), 404
    return jsonify(emp), 200

@requiere_permiso('empleados.gestionar')
def create_empleado():
    data = request.json
    if not data or not data.get('nombre') or not data.get('usuario') or not data.get('contrasena'):
        return jsonify({"error": "nombre, usuario y contrasena son requeridos"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Empleado creado", "id": new_id}), 201

@requiere_permiso('empleados.gestionar')
def update_empleado(id):
    data = request.json
    affected = model.update(id, data)
    if not affected:
        return jsonify({"error": "Empleado no encontrado"}), 404
    return jsonify({"mensaje": "Empleado actualizado"}), 200

@requiere_permiso('empleados.gestionar')
def update_contrasena_empleado(id):
    data = request.json
    if not data or not data.get('contrasena'):
        return jsonify({"error": "contrasena es requerida"}), 400
    affected = model.update_contrasena(id, data['contrasena'])
    if not affected:
        return jsonify({"error": "Empleado no encontrado"}), 404
    return jsonify({"mensaje": "Contraseña actualizada"}), 200

@requiere_permiso('empleados.gestionar')
def delete_empleado(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Empleado no encontrado"}), 404
    return jsonify({"mensaje": "Empleado eliminado"}), 200

@requiere_permiso('roles.gestionar')
def asignar_rol_empleado(empleado_id):
    data = request.json
    if not data or not data.get('rol_id'):
        return jsonify({"error": "rol_id es requerido"}), 400
    model.asignar_rol(empleado_id, data['rol_id'])
    return jsonify({"mensaje": "Rol asignado"}), 200


@requiere_permiso('roles.gestionar')
def quitar_rol_empleado(empleado_id, rol_id):
    model.quitar_rol(empleado_id, rol_id)
    return jsonify({"mensaje": "Rol removido"}), 200