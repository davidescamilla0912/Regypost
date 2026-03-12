from flask import request, jsonify
from Models.reserva_model import ReservaModel
from utils.decorators import requiere_permiso

model = ReservaModel()

estados_validos = ['pendiente', 'confirmada', 'checkin', 'checkout', 'cancelada']

@requiere_permiso('reservas.ver')
def get_all_reservas():
    return jsonify(model.get_all()), 200

@requiere_permiso('reservas.ver')
def get_reserva(id):
    reserva = model.get_by_id(id)
    if not reserva:
        return jsonify({"error": "Reserva no encontrada"}), 404
    return jsonify(reserva), 200

@requiere_permiso('reservas.ver')
def get_reservas_activas():
    return jsonify(model.get_activas()), 200

@requiere_permiso('reservas.ver')
def get_reservas_by_estado(estado):
    if estado not in estados_validos:
        return jsonify({"error": f"Estado debe ser uno de: {estados_validos}"}), 400
    return jsonify(model.get_by_estado(estado)), 200

@requiere_permiso('reservas.crear')
def create_reserva():
    data = request.json
    if not data or not data.get('cliente_id') or not data.get('fecha_entrada') or not data.get('fecha_salida'):
        return jsonify({"error": "cliente_id, fecha_entrada y fecha_salida son requeridos"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Reserva creada", "id": new_id}), 201

@requiere_permiso('reservas.editar')
def update_reserva(id):
    data = request.json
    affected = model.update(id, data)
    if not affected:
        return jsonify({"error": "Reserva no encontrada"}), 404
    return jsonify({"mensaje": "Reserva actualizada"}), 200

@requiere_permiso('reservas.editar')
def update_estado_reserva(id):
    data = request.json
    estado = data.get('estado')
    if estado not in estados_validos:
        return jsonify({"error": f"Estado debe ser uno de: {estados_validos}"}), 400
    affected = model.update_estado(id, estado)
    if not affected:
        return jsonify({"error": "Reserva no encontrada"}), 404
    return jsonify({"mensaje": f"Estado actualizado a {estado}"}), 200

@requiere_permiso('reservas.cancelar')
def delete_reserva(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Reserva no encontrada"}), 404
    return jsonify({"mensaje": "Reserva eliminada"}), 200

@requiere_permiso('reservas.ver')
def get_habitaciones_reserva(reserva_id):
    habitaciones = model.get_habitaciones(reserva_id)
    return jsonify(habitaciones), 200

@requiere_permiso('reservas.crear')
def agregar_habitacion_reserva(reserva_id):
    data = request.json
    if not data or not data.get('habitacion_id'):
        return jsonify({"error": "habitacion_id es requerido"}), 400
    new_id = model.agregar_habitacion(reserva_id, data)
    return jsonify({"mensaje": "Habitación agregada a la reserva", "id": new_id}), 201

@requiere_permiso('reservas.editar')
def quitar_habitacion_reserva(reserva_id, habitacion_id):
    model.quitar_habitacion(reserva_id, habitacion_id)
    return jsonify({"mensaje": "Habitación removida de la reserva"}), 200