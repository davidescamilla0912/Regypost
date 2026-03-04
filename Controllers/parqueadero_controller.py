from flask import request, jsonify
from Models.parqueadero_model import ParqueaderoModel

model = ParqueaderoModel()

def get_all_parqueadero():
    return jsonify(model.get_all()), 200

def get_parqueadero(id):
    registro = model.get_by_id(id)
    if not registro:
        return jsonify({"error": "Registro no encontrado"}), 404
    return jsonify(registro), 200

def get_parqueadero_activos():
    return jsonify(model.get_activos()), 200

def get_parqueadero_placa(placa):
    return jsonify(model.get_by_placa(placa)), 200

def create_parqueadero():
    data = request.json
    if not data or not data.get('placa') or not data.get('hora_entrada'):
        return jsonify({"error": "placa y hora_entrada son requeridos"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Entrada registrada", "id": new_id}), 201

def registrar_salida(id):
    data = request.json
    if not data or not data.get('hora_salida'):
        return jsonify({"error": "hora_salida es requerida"}), 400
    affected = model.registrar_salida(id, data)
    if not affected:
        return jsonify({"error": "Registro no encontrado"}), 404
    return jsonify({"mensaje": "Salida registrada"}), 200

def delete_parqueadero(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Registro no encontrado"}), 404
    return jsonify({"mensaje": "Registro eliminado"}), 200