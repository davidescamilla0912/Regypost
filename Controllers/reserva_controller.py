from flask import request, jsonify
from Models.reserva_model import ReservaModel
from utils.decorators import requiere_permiso
## error reserva nueva prueba, se modifico get_all_reservas,get_reserva,get_reservas_activas,get_reservas_by_estado para serializar los objetos datetime y decimal a json, se agrego la funcion serializar para esto, se modifico el return de estas funciones para usar json.dumps con la funcion serializar, se agrego el import de json, datetime y decimal
import json
from datetime import timedelta, date
from decimal import Decimal
def serializar(obj):
    if isinstance(obj, timedelta):
        total = int(obj.total_seconds())
        return f"{total//3600:02d}:{(total%3600)//60:02d}"
    if isinstance(obj, (date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

model = ReservaModel()

estados_validos = ['pendiente', 'confirmada', 'checkin', 'checkout', 'cancelada']

@requiere_permiso('reservas.ver')
def get_all_reservas():
    reservas = model.get_all()
    return json.dumps(reservas, default=serializar), 200, {'Content-Type': 'application/json'}


@requiere_permiso('reservas.ver')
def get_reserva(id):
    reserva = model.get_by_id(id)
    if not reserva:
        return jsonify({"error": "Reserva no encontrada"}), 404
    return json.dumps(reserva, default=serializar), 200, {'Content-Type': 'application/json'}

@requiere_permiso('reservas.ver')
def get_reservas_activas():
    return json.dumps(model.get_activas(), default=serializar), 200, {'Content-Type': 'application/json'}

@requiere_permiso('reservas.ver')
def get_reservas_by_estado(estado):
    if estado not in estados_validos:
        return jsonify({"error": f"Estado debe ser uno de: {estados_validos}"}), 400
    return json.dumps(model.get_by_estado(estado), default=serializar), 200, {'Content-Type': 'application/json'}

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

@requiere_permiso('reservas.editar')
def confirmar_reserva(id):
    data = request.json or {}
    anticipo = data.get('anticipo')

    if anticipo is None:
        return jsonify({"error": "anticipo es requerido"}), 400

    try:
        anticipo = Decimal(str(anticipo))
    except Exception:
        return jsonify({"error": "anticipo debe ser un número válido"}), 400

    if anticipo < 0:
        return jsonify({"error": "anticipo debe ser mayor o igual a 0"}), 400

    reserva_actual = model.get_by_id(id)
    if not reserva_actual:
        return jsonify({"error": "Reserva no encontrada"}), 404

    total = reserva_actual.get('total') or Decimal('0')
    if anticipo > total:
        return jsonify({"error": "anticipo no puede ser mayor que el total de la reserva"}), 400

    reserva, status = model.confirmar_reserva(id, anticipo)
    if status == "not_found":
        return jsonify({"error": "Reserva no encontrada"}), 404
    if status == "invalid_state":
        return jsonify({"error": "Solo se puede confirmar una reserva en estado pendiente"}), 400

    return json.dumps(reserva, default=serializar), 200, {'Content-Type': 'application/json'}

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

@requiere_permiso('reservas.ver')
def get_reservas_futuras_habitacion(habitacion_id):
    """Verifica si una habitación tiene reservas futuras."""
    tiene = model.tiene_reservas_futuras(habitacion_id)
    return jsonify({"tiene_reservas_futuras": tiene}), 200