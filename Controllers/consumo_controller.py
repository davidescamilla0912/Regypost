from flask import request, jsonify
from flask_jwt_extended import jwt_required
from Models.consumo_model import ConsumoModel
from utils.decorators import requiere_permiso

model = ConsumoModel()

@requiere_permiso('consumos.registrar')
def get_consumos_reserva(reserva_id):
    return jsonify(model.get_by_reserva(reserva_id)), 200

@requiere_permiso('consumos.registrar')
def get_consumo(id):
    consumo = model.get_by_id(id)
    if not consumo:
        return jsonify({"error": "Consumo no encontrado"}), 404
    return jsonify(consumo), 200

@requiere_permiso('consumos.consultar')
def get_consumos_fecha(fecha):
    return jsonify(model.get_by_fecha(fecha)), 200

@jwt_required()
def get_tipos_consumo():
    return jsonify(model.get_tipos_consumo()), 200

@requiere_permiso('consumos.registrar')
def create_consumo():
    data = request.json
    if not data or not data.get('reserva_habitacion_id') or not data.get('tipo_consumo_id') or not data.get('fecha'):
        return jsonify({"error": "reserva_habitacion_id, tipo_consumo_id y fecha son requeridos"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Consumo registrado", "id": new_id}), 201

@requiere_permiso('consumos.registrar')
def create_daño():
    data = request.json

    # Validaciones específicas para daños
    if not data:
        return jsonify({"error": "No se recibieron datos"}), 400

    errores = []
    if not data.get('reserva_habitacion_id'):
        errores.append("reserva_habitacion_id es requerido")
    if not data.get('descripcion') or not data['descripcion'].strip():
        errores.append("descripcion es requerida (detalla el daño)")
    if not data.get('precio_unitario') or data['precio_unitario'] <= 0:
        errores.append("precio_unitario debe ser mayor a 0")
    if not data.get('fecha'):
        errores.append("fecha es requerida")
    if not data.get('empleado_id'):
        errores.append("empleado_id es requerido")

    if errores:
        return jsonify({"error": "Datos inválidos", "detalles": errores}), 400

    try:
        new_id = model.create_daño(data)
        return jsonify({"mensaje": "Daño registrado correctamente", "id": new_id}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 500

@requiere_permiso('consumos.registrar')
def update_consumo(id):
    data = request.json
    affected = model.update(id, data)
    if not affected:
        return jsonify({"error": "Consumo no encontrado"}), 404
    return jsonify({"mensaje": "Consumo actualizado"}), 200

@requiere_permiso('consumos.registrar')
def delete_consumo(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Consumo no encontrado"}), 404
    return jsonify({"mensaje": "Consumo eliminado"}), 200