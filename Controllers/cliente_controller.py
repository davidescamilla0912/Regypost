from flask import request, jsonify
from flask_jwt_extended import jwt_required
from utils.decorators import requiere_permiso
from Models.cliente_model import ClienteModel

model = ClienteModel()

@jwt_required()
def get_all_clientes():
    clientes = model.get_all()
    return jsonify(clientes), 200

@jwt_required()
def get_cliente(id):
    cliente = model.get_by_id(id)
    if not cliente:
        return jsonify({"error": "Cliente no encontrado"}), 404
    return jsonify(cliente), 200

@jwt_required()
def get_cliente_by_documento(numero_documento):
    cliente = model.get_by_documento(numero_documento)
    if not cliente:
        return jsonify({"error": "Cliente no encontrado"}), 404
    return jsonify(cliente), 200


@requiere_permiso('clientes.crear')
def create_cliente():
    data = request.json
    if not data or not data.get('numero_documento') or not data.get('nombre') or not data.get('apellido'):
        return jsonify({"error": "numero_documento, nombre y apellido son requeridos"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Cliente creado", "id": new_id}), 201

@requiere_permiso('clientes.crear')
def update_cliente(id):
    data = request.json
    affected = model.update(id, data)
    if not affected:
        return jsonify({"error": "Cliente no encontrado"}), 404
    return jsonify({"mensaje": "Cliente actualizado"}), 200

@requiere_permiso('clientes.crear')
def delete_cliente(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Cliente no encontrado"}), 404
    return jsonify({"mensaje": "Cliente eliminado"}), 200

@jwt_required()
def search_clientes():
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Parámetro de búsqueda requerido"}), 400
    clientes = model.search(query)
    return jsonify(clientes), 200