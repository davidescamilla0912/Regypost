from flask import Blueprint
from Controllers.tipo_habitacion_controller import (
    get_all_tipos, get_tipo, create_tipo, update_tipo, delete_tipo
)
from Controllers.habitacion_controller import (
    get_all_habitaciones, get_habitacion, get_habitaciones_disponibles,
    get_habitaciones_by_estado, create_habitacion, update_habitacion,
    update_estado_habitacion, delete_habitacion
)

habitacion_bp = Blueprint('habitaciones', __name__)

# Tipos de habitación
habitacion_bp.route('/tipos-habitacion',          methods=['GET']   )(get_all_tipos)
habitacion_bp.route('/tipos-habitacion/<int:id>', methods=['GET']   )(get_tipo)
habitacion_bp.route('/tipos-habitacion',          methods=['POST']  )(create_tipo)
habitacion_bp.route('/tipos-habitacion/<int:id>', methods=['PUT']   )(update_tipo)
habitacion_bp.route('/tipos-habitacion/<int:id>', methods=['DELETE'])(delete_tipo)

# Habitaciones
habitacion_bp.route('/habitaciones',                     methods=['GET']   )(get_all_habitaciones)
habitacion_bp.route('/habitaciones/disponibles',         methods=['GET']   )(get_habitaciones_disponibles)
habitacion_bp.route('/habitaciones/estado/<estado>',     methods=['GET']   )(get_habitaciones_by_estado)
habitacion_bp.route('/habitaciones/<int:id>',            methods=['GET']   )(get_habitacion)
habitacion_bp.route('/habitaciones',                     methods=['POST']  )(create_habitacion)
habitacion_bp.route('/habitaciones/<int:id>',            methods=['PUT']   )(update_habitacion)
habitacion_bp.route('/habitaciones/<int:id>/estado',     methods=['PATCH'] )(update_estado_habitacion)
habitacion_bp.route('/habitaciones/<int:id>',            methods=['DELETE'])(delete_habitacion)