from flask import Blueprint
from Controllers.reserva_controller import (
    get_all_reservas, get_reserva, get_reservas_activas,
    get_reservas_by_estado, create_reserva, update_reserva,
    update_estado_reserva, confirmar_reserva, delete_reserva,
    get_habitaciones_reserva, agregar_habitacion_reserva,
    quitar_habitacion_reserva, get_reservas_futuras_habitacion,extender_reserva,
    cambiar_habitacion,get_habitaciones_para_cambio,update_personas_reserva
)
from Controllers.acompanante_controller import (
    get_acompanantes_reserva,
    create_acompanante,
    create_acompanantes_bulk,
    update_acompanante,
    delete_acompanante
)

reserva_bp = Blueprint('reservas', __name__)

reserva_bp.route('/reservas',                                              methods=['GET']   )(get_all_reservas)
reserva_bp.route('/reservas/activas',                                      methods=['GET']   )(get_reservas_activas)
reserva_bp.route('/reservas/estado/<estado>',                              methods=['GET']   )(get_reservas_by_estado)
reserva_bp.route('/reservas/<int:id>',                                     methods=['GET']   )(get_reserva)
reserva_bp.route('/reservas',                                              methods=['POST']  )(create_reserva)
reserva_bp.route('/reservas/<int:id>',                                     methods=['PUT']   )(update_reserva)
reserva_bp.route('/reservas/<int:id>/estado',                              methods=['PATCH'] )(update_estado_reserva)
reserva_bp.route('/reservas/<int:id>/confirmar',                           methods=['PATCH'] )(confirmar_reserva)
reserva_bp.route('/reservas/<int:id>',                                     methods=['DELETE'])(delete_reserva)
reserva_bp.route('/reservas/<int:reserva_id>/habitaciones',                methods=['GET']   )(get_habitaciones_reserva)
reserva_bp.route('/reservas/<int:reserva_id>/habitaciones',                methods=['POST']  )(agregar_habitacion_reserva)
reserva_bp.route('/reservas/<int:reserva_id>/habitaciones/<int:habitacion_id>', methods=['DELETE'])(quitar_habitacion_reserva)
reserva_bp.route('/reservas/habitacion/<int:habitacion_id>/futuras', methods=['GET'])(get_reservas_futuras_habitacion)
reserva_bp.route('/reservas/<int:id>/extender', methods=['PATCH'])(extender_reserva)
reserva_bp.route('/reservas/<int:id>/cambiar-habitacion', methods=['POST'])(cambiar_habitacion)
reserva_bp.route('/reservas/<int:id>/habitaciones-para-cambio', methods=['GET'])(get_habitaciones_para_cambio)
reserva_bp.route('/reservas/<int:id>/personas', methods=['PATCH'])(update_personas_reserva)
# ── Acompañantes ──────────────────────────────────────────────────────────────

reserva_bp.route('/reservas/<int:reserva_id>/acompanantes',                              methods=['GET'])(get_acompanantes_reserva)
reserva_bp.route('/reservas/<int:reserva_id>/acompanantes',                              methods=['POST'])(create_acompanante)
reserva_bp.route('/reservas/<int:reserva_id>/acompanantes/bulk',                         methods=['POST'])(create_acompanantes_bulk)
reserva_bp.route('/acompanantes/<int:id>',                                               methods=['PUT'])(update_acompanante)
reserva_bp.route('/acompanantes/<int:id>',                                               methods=['DELETE'])(delete_acompanante)