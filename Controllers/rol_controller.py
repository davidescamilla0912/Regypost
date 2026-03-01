from flask import request, jsonify
from Models.rol_model import RolModel

model = RolModel()

def get_all_roles():
    return jsonify(model.get_all()), 200

def get_rol(id):
    rol = model.get_by_id(id)
    if not rol:
        return jsonify({"error": "Rol no encontrado"}), 404
    return jsonify(rol), 200

def create_rol():
    data = request.json
    if not data or not data.get('nombre'):
        return jsonify({"error": "nombre es requerido"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Rol creado", "id": new_id}), 201

def update_rol(id):
    data = request.json
    affected = model.update(id, data)
    if not affected:
        return jsonify({"error": "Rol no encontrado"}), 404
    return jsonify({"mensaje": "Rol actualizado"}), 200

def delete_rol(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Rol no encontrado"}), 404
    return jsonify({"mensaje": "Rol eliminado"}), 200

def get_permisos_rol(rol_id):
    permisos = model.get_permisos(rol_id)
    return jsonify(permisos), 200

def asignar_permiso_rol(rol_id):
    data = request.json
    if not data or not data.get('permiso_id'):
        return jsonify({"error": "permiso_id es requerido"}), 400
    model.asignar_permiso(rol_id, data['permiso_id'])
    return jsonify({"mensaje": "Permiso asignado"}), 200

def quitar_permiso_rol(rol_id, permiso_id):
    model.quitar_permiso(rol_id, permiso_id)
    return jsonify({"mensaje": "Permiso removido"}), 200