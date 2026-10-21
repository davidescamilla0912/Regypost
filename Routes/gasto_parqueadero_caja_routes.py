from flask import Blueprint
from Controllers.gasto_controller import (
    get_all_gastos, get_gasto, get_gastos_fecha,
    get_gastos_categoria, create_gasto, update_gasto, delete_gasto
)
from Controllers.parqueadero_controller import (
    get_all_parqueadero, get_parqueadero, get_parqueadero_activos,
    get_parqueadero_placa, create_parqueadero, registrar_salida, delete_parqueadero
)
from Controllers.cuadre_caja_controller import (
    get_all_cuadres, get_cuadre, get_cuadres_fecha,
    create_cuadre, update_cuadre, delete_cuadre, get_resumen_dia
)

gasto_parqueadero_caja_bp = Blueprint('gasto_parqueadero_caja', __name__)

# Gastos
gasto_parqueadero_caja_bp.route('/gastos',                      methods=['GET']   )(get_all_gastos)
gasto_parqueadero_caja_bp.route('/gastos/<int:id>',             methods=['GET']   )(get_gasto)
gasto_parqueadero_caja_bp.route('/gastos/fecha/<fecha>',        methods=['GET']   )(get_gastos_fecha)
gasto_parqueadero_caja_bp.route('/gastos/categoria/<categoria>', methods=['GET']  )(get_gastos_categoria)
gasto_parqueadero_caja_bp.route('/gastos',                      methods=['POST']  )(create_gasto)
gasto_parqueadero_caja_bp.route('/gastos/<int:id>',             methods=['PUT']   )(update_gasto)
gasto_parqueadero_caja_bp.route('/gastos/<int:id>',             methods=['DELETE'])(delete_gasto)

# Parqueadero
gasto_parqueadero_caja_bp.route('/parqueadero',                      methods=['GET']   )(get_all_parqueadero)
gasto_parqueadero_caja_bp.route('/parqueadero/activos',              methods=['GET']   )(get_parqueadero_activos)
gasto_parqueadero_caja_bp.route('/parqueadero/placa/<placa>',        methods=['GET']   )(get_parqueadero_placa)
gasto_parqueadero_caja_bp.route('/parqueadero/<int:id>',             methods=['GET']   )(get_parqueadero)
gasto_parqueadero_caja_bp.route('/parqueadero',                      methods=['POST']  )(create_parqueadero)
gasto_parqueadero_caja_bp.route('/parqueadero/<int:id>/salida',      methods=['PATCH'] )(registrar_salida)
gasto_parqueadero_caja_bp.route('/parqueadero/<int:id>',             methods=['DELETE'])(delete_parqueadero)

# Cuadre de caja
gasto_parqueadero_caja_bp.route('/caja',                   methods=['GET']   )(get_all_cuadres)
gasto_parqueadero_caja_bp.route('/caja/<int:id>',          methods=['GET']   )(get_cuadre)
gasto_parqueadero_caja_bp.route('/caja/fecha/<fecha>',     methods=['GET']   )(get_cuadres_fecha)
gasto_parqueadero_caja_bp.route('/caja/resumen/<fecha>',   methods=['GET']   )(get_resumen_dia)
gasto_parqueadero_caja_bp.route('/caja',                   methods=['POST']  )(create_cuadre)
gasto_parqueadero_caja_bp.route('/caja/<int:id>',          methods=['PUT']   )(update_cuadre)
gasto_parqueadero_caja_bp.route('/caja/<int:id>',          methods=['DELETE'])(delete_cuadre)