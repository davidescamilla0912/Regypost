from flask import request, jsonify
from Models.pago_model import PagoModel

model = PagoModel()

def get_pagos_reserva(reserva_id):
    return jsonify(model.get_by_reserva(reserva_id)), 200

def get_pago(id):
    pago = model.get_by_id(id)
    if not pago:
        return jsonify({"error": "Pago no encontrado"}), 404
    return jsonify(pago), 200

def get_pagos_fecha(fecha):
    return jsonify(model.get_by_fecha(fecha)), 200

def get_total_pagado(reserva_id):
    total = model.get_total_by_reserva(reserva_id)
    return jsonify(total or {"reserva_id": reserva_id, "total_pagado": 0, "num_pagos": 0}), 200

def create_pago():
    data = request.json
    if not data or not data.get('reserva_id') or not data.get('monto'):
        return jsonify({"error": "reserva_id y monto son requeridos"}), 400
    new_id = model.create(data)
    return jsonify({"mensaje": "Pago registrado", "id": new_id}), 201

def delete_pago(id):
    affected = model.delete(id)
    if not affected:
        return jsonify({"error": "Pago no encontrado"}), 404
    return jsonify({"mensaje": "Pago eliminado"}), 200