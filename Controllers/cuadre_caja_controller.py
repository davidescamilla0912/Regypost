from flask import request, jsonify
from Models.cuadre_caja_model import CuadreCajaModel
from utils.decorators import requiere_permiso

model = CuadreCajaModel()

@requiere_permiso('caja.ver')
def get_all_cuadres():
    return jsonify(model.get_all()), 200

@requiere_permiso('caja.ver')
def get_cuadre(id):
    cuadre = model.get_by_id(id)
    if not cuadre:
        return jsonify({"error": "Cuadre no encontrado"}), 404
    return jsonify(cuadre), 200

@requiere_permiso('caja.ver')
def get_cuadres_fecha(fecha):
    return jsonify(model.get_by_fecha(fecha)), 200

@requiere_permiso('caja.crear')
def create_cuadre():
    data = request.json
    if not data or not data.get('fecha'):
        return jsonify({"error": "fecha es requerida"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Cuadre de caja creado", "id": new_id}), 201

@requiere_permiso('caja.crear')
def update_cuadre(id):
    data = request.json
    affected = model.update(id, data)
    if not affected:
        return jsonify({"error": "Cuadre no encontrado"}), 404
    return jsonify({"mensaje": "Cuadre actualizado"}), 200

@requiere_permiso('caja.crear')
def delete_cuadre(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Cuadre no encontrado"}), 404
    return jsonify({"mensaje": "Cuadre eliminado"}), 200