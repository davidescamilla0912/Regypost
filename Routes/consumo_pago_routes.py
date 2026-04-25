from flask import Blueprint, jsonify
from Controllers.consumo_controller import (
    get_consumos_reserva, get_consumo, get_consumos_fecha,
    get_tipos_consumo, create_consumo, update_consumo, delete_consumo
)
from Controllers.pago_controller import (
    get_pagos, get_pagos_reserva, get_pago, get_pagos_fecha,
    get_total_pagado, create_pago, update_pago, delete_pago
)

consumo_pago_bp = Blueprint('consumos_pagos', __name__)

# Tipos de consumo
consumo_pago_bp.route('/tipos-consumo',               methods=['GET'])(get_tipos_consumo)

# Consumos
consumo_pago_bp.route('/consumos/<int:id>',            methods=['GET']   )(get_consumo)
consumo_pago_bp.route('/consumos/fecha/<fecha>',       methods=['GET']   )(get_consumos_fecha)
consumo_pago_bp.route('/consumos',                     methods=['POST']  )(create_consumo)
consumo_pago_bp.route('/consumos/<int:id>',            methods=['PUT']   )(update_consumo)
consumo_pago_bp.route('/consumos/<int:id>',            methods=['DELETE'])(delete_consumo)
consumo_pago_bp.route('/reservas/<int:reserva_id>/consumos', methods=['GET'])(get_consumos_reserva)

# Pagos
consumo_pago_bp.route('/pagos',                       methods=['GET']   )(get_pagos)
consumo_pago_bp.route('/pagos/',                      methods=['GET']   )(get_pagos)
consumo_pago_bp.route('/pagos/<int:id>',               methods=['GET']   )(get_pago)
consumo_pago_bp.route('/pagos/fecha/<fecha>',          methods=['GET']   )(get_pagos_fecha)
consumo_pago_bp.route('/pagos',                        methods=['POST']  )(create_pago)
consumo_pago_bp.route('/pagos/<int:id>',               methods=['PUT']   )(update_pago)
consumo_pago_bp.route('/pagos/<int:id>',               methods=['DELETE'])(delete_pago)
consumo_pago_bp.route('/reservas/<int:reserva_id>/pagos',        methods=['GET'])(get_pagos_reserva)
consumo_pago_bp.route('/reservas/<int:reserva_id>/pagos/total',  methods=['GET'])(get_total_pagado)


@consumo_pago_bp.route('/pagos', methods=['OPTIONS'])
@consumo_pago_bp.route('/pagos/', methods=['OPTIONS'])
def pagos_options():
    return jsonify({"ok": True}), 200