from flask import request, jsonify
from Models.inventario_model import InventarioModel
from utils.decorators import requiere_permiso

model = InventarioModel()

tipos_movimiento = ['entrada', 'salida', 'ajuste']

@requiere_permiso('inventario.ver')
def get_all_productos():
    return jsonify(model.get_all()), 200

@requiere_permiso('inventario.ver')
def get_producto(id):
    producto = model.get_by_id(id)
    if not producto:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify(producto), 200

@requiere_permiso('inventario.ver')
def get_productos_por_reponer():
    return jsonify(model.get_por_reponer()), 200

@requiere_permiso('inventario.mover')
def create_producto():
    data = request.json
    if not data or not data.get('nombre'):
        return jsonify({"error": "nombre es requerido"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Producto creado", "id": new_id}), 201

@requiere_permiso('inventario.mover')
def update_producto(id):
    data = request.json
    affected = model.update(id, data)
    if not affected:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify({"mensaje": "Producto actualizado"}), 200

@requiere_permiso('inventario.mover')
def delete_producto(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify({"mensaje": "Producto desactivado"}), 200

@requiere_permiso('inventario.ver')
def get_movimientos_producto(producto_id):
    return jsonify(model.get_movimientos(producto_id)), 200

@requiere_permiso('inventario.mover')
def registrar_movimiento():
    data = request.json
    if not data or not data.get('producto_id') or not data.get('tipo_movimiento') or not data.get('cantidad'):
        return jsonify({"error": "producto_id, tipo_movimiento y cantidad son requeridos"}), 400
    if data['tipo_movimiento'] not in tipos_movimiento:
        return jsonify({"error": f"tipo_movimiento debe ser uno de: {tipos_movimiento}"}), 400
    new_id = model.registrar_movimiento(data)
    return jsonify({"mensaje": "Movimiento registrado", "id": new_id}), 201