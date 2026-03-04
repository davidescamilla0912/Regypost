from flask import request, jsonify
from Models.gasto_model import GastoModel

model = GastoModel()

categorias_validas = ['olimpica', 'ferreteria', 'turno', 'insumos', 'mantenimiento', 'varios']

def get_all_gastos():
    return jsonify(model.get_all()), 200

def get_gasto(id):
    gasto = model.get_by_id(id)
    if not gasto:
        return jsonify({"error": "Gasto no encontrado"}), 404
    return jsonify(gasto), 200

def get_gastos_fecha(fecha):
    return jsonify(model.get_by_fecha(fecha)), 200

def get_gastos_categoria(categoria):
    if categoria not in categorias_validas:
        return jsonify({"error": f"Categoria debe ser una de: {categorias_validas}"}), 400
    return jsonify(model.get_by_categoria(categoria)), 200

def create_gasto():
    data = request.json
    if not data or not data.get('fecha') or not data.get('monto'):
        return jsonify({"error": "fecha y monto son requeridos"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Gasto registrado", "id": new_id}), 201

def update_gasto(id):
    data = request.json
    affected = model.update(id, data)
    if not affected:
        return jsonify({"error": "Gasto no encontrado"}), 404
    return jsonify({"mensaje": "Gasto actualizado"}), 200

def delete_gasto(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Gasto no encontrado"}), 404
    return jsonify({"mensaje": "Gasto eliminado"}), 200