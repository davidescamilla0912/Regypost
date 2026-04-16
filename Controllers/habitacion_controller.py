from flask import request, jsonify
from Models.habitacion_model import HabitacionModel
from utils.decorators import requiere_permiso

model = HabitacionModel()
ESTADOS_VALIDOS_HABITACION = ['disponible', 'ocupada', 'mantenimiento', 'bloqueada']

@requiere_permiso('habitaciones.ver')
def get_all_habitaciones():
    return jsonify(model.get_all()), 200

@requiere_permiso('habitaciones.ver')
def get_habitacion(id):
    hab = model.get_by_id(id)
    if not hab:
        return jsonify({"error": "Habitación no encontrada"}), 404
    return jsonify(hab), 200

@requiere_permiso('habitaciones.ver')
def get_habitaciones_disponibles():
    return jsonify(model.get_disponibles()), 200

@requiere_permiso('habitaciones.ver')
def get_habitaciones_by_estado(estado):
    estados_validos = ESTADOS_VALIDOS_HABITACION
    if estado not in estados_validos:
        return jsonify({"error": f"Estado debe ser uno de: {estados_validos}"}), 400
    return jsonify(model.get_by_estado(estado)), 200

@requiere_permiso('habitaciones.editar')
def create_habitacion():
    data = request.json
    if not data or not data.get('numero') or not data.get('piso') or not data.get('tipo_id'):
        return jsonify({"error": "numero, piso y tipo_id son requeridos"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Habitación creada", "id": new_id}), 201

@requiere_permiso('habitaciones.editar')
def update_habitacion(id):
    data = request.json
    affected = model.update(id, data)
    if not affected:
        return jsonify({"error": "Habitación no encontrada"}), 404
    return jsonify({"mensaje": "Habitación actualizada"}), 200

@requiere_permiso('habitaciones.editar')
def update_estado_habitacion(id):
    data = request.json
    estado = data.get('estado')
    estados_validos = ESTADOS_VALIDOS_HABITACION
    if estado not in estados_validos:
        return jsonify({"error": f"Estado debe ser uno de: {estados_validos}"}), 400
    affected = model.update_estado(id, estado)
    if not affected:
        return jsonify({"error": "Habitación no encontrada"}), 404
    return jsonify({"mensaje": "Estado actualizado"}), 200

@requiere_permiso('habitaciones.editar')
def delete_habitacion(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Habitación no encontrada"}), 404
    return jsonify({"mensaje": "Habitación eliminada"}), 200