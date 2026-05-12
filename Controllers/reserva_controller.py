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

@requiere_permiso('reservas.editar')
def extender_reserva(id):
    data = request.json or {}
    dias_extra = data.get('dias_extra')

    if not dias_extra or not isinstance(dias_extra, int) or dias_extra <= 0:
        return jsonify({"error": "dias_extra debe ser un número entero mayor a 0"}), 400

    resultado, status = model.extender_dias(id, dias_extra)

    if status == "not_found":
        return jsonify({"error": "Reserva no encontrada"}), 404
    if status == "invalid_state":
        return jsonify({"error": "Solo se pueden extender reservas en estado check-in"}), 400

    return jsonify(resultado), 200

@requiere_permiso('reservas.editar')
def cambiar_habitacion(id):
    """
    POST /reservas/<id>/cambiar-habitacion
    Body: { "nueva_habitacion_id": int, "motivo": str }
    """
    data = request.json or {}
 
    nueva_habitacion_id = data.get('nueva_habitacion_id')
    motivo              = (data.get('motivo') or '').strip()
 
    if not nueva_habitacion_id or not isinstance(nueva_habitacion_id, int):
        return jsonify({"error": "nueva_habitacion_id (int) es requerido"}), 400
 
    if not motivo:
        return jsonify({"error": "motivo es requerido"}), 400
 
    if len(motivo) > 500:
        return jsonify({"error": "motivo no puede superar 500 caracteres"}), 400
 
    # Obtener empleado de la sesión (si tu sistema lo expone en el token/JWT)
    empleado_id = None
    try:
        from flask import g
        empleado_id = getattr(g, 'empleado_id', None)
    except Exception:
        pass
 
    resultado, status = model.cambiar_habitacion(
        reserva_id          = id,
        nueva_habitacion_id = nueva_habitacion_id,
        motivo              = motivo,
        empleado_id         = empleado_id
    )
 
    errores = {
        "not_found":        ("Reserva no encontrada", 404),
        "invalid_state":    ("Solo se puede cambiar una reserva en estado checkin", 400),
        "no_room_linked":   ("La reserva no tiene habitación asignada", 400),
        "same_room":        ("La habitación destino es la misma que la actual", 400),
        "dest_not_found":   ("Habitación destino no encontrada", 404),
        "dest_not_available": ("La habitación destino no está disponible (ocupada/mantenimiento/bloqueada)", 409),
        "dest_occupied":    ("La habitación destino tiene un checkin activo en este momento", 409),
        "date_conflict":    ("La habitación destino tiene una reserva futura que choca con el checkout actual", 409),
    }
 
    if status in errores:
        msg, code = errores[status]
        return jsonify({"error": msg}), code
 
    return json.dumps(resultado, default=serializar), 200, {'Content-Type': 'application/json'}
 
 
@requiere_permiso('reservas.ver')
def get_habitaciones_para_cambio(id):
    """
    GET /reservas/<reserva_id>/habitaciones-para-cambio
    Retorna habitaciones disponibles y reservadas-sin-conflicto para el cambio.
    """
    from datetime import date, timedelta
    from decimal import Decimal
 
    habitaciones = model.get_habitaciones_para_cambio(id)
 
    # serializar Decimal/date que puedan venir del model
    def _serial(obj):
        if isinstance(obj, (date,)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, timedelta):
            return str(obj)
        raise TypeError
 
    return json.dumps(habitaciones, default=_serial), 200, {'Content-Type': 'application/json'}

@requiere_permiso('reservas.editar')
def update_personas_reserva(id):
    data = request.get_json()
    num_adultos = data.get('num_adultos')
    num_ninos   = data.get('num_ninos')

    if num_adultos is None or num_ninos is None:
        return jsonify({'error': 'num_adultos y num_ninos son requeridos'}), 400
    if int(num_adultos) < 1:
        return jsonify({'error': 'Debe haber al menos 1 adulto'}), 400

    affected = model.update_personas(id, int(num_adultos), int(num_ninos))
    if not affected:
        return jsonify({'error': 'Reserva no encontrada'}), 404

    return jsonify({'ok': True, 'num_adultos': int(num_adultos), 'num_ninos': int(num_ninos)})
 