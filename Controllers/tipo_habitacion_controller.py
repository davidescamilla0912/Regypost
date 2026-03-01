from flask import request, jsonify
from Models.tipo_habitacion_model import TipoHabitacionModel

model = TipoHabitacionModel()

def get_all_tipos():
    return jsonify(model.get_all()), 200

def get_tipo(id):
    tipo = model.get_by_id(id)
    if not tipo:
        return jsonify({"error": "Tipo no encontrado"}), 404
    return jsonify(tipo), 200

def create_tipo():
    data = request.json
    if not data or not data.get('nombre'):
        return jsonify({"error": "nombre es requerido"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Tipo creado", "id": new_id}), 201

def update_tipo(id):
    data = request.json
    affected = model.update(id, data)
    if not affected:
        return jsonify({"error": "Tipo no encontrado"}), 404
    return jsonify({"mensaje": "Tipo actualizado"}), 200

def delete_tipo(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Tipo no encontrado"}), 404
    return jsonify({"mensaje": "Tipo eliminado"}), 200