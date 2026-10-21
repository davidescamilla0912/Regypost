from flask import Blueprint
from Controllers.inventario_controller import (
    get_all_productos, get_producto, get_productos_por_reponer,
    create_producto, update_producto, delete_producto,
    get_movimientos_producto, registrar_movimiento, consumo_habitacion
)

inventario_bp = Blueprint('inventario', __name__)

inventario_bp.route('/inventario',                          methods=['GET']   )(get_all_productos)
inventario_bp.route('/inventario/reponer',                  methods=['GET']   )(get_productos_por_reponer)
inventario_bp.route('/inventario/<int:id>',                 methods=['GET']   )(get_producto)
inventario_bp.route('/inventario',                          methods=['POST']  )(create_producto)
inventario_bp.route('/inventario/<int:id>',                 methods=['PUT']   )(update_producto)
inventario_bp.route('/inventario/<int:id>',                 methods=['DELETE'])(delete_producto)
inventario_bp.route('/inventario/<int:producto_id>/movimientos', methods=['GET'] )(get_movimientos_producto)
inventario_bp.route('/inventario/movimientos',              methods=['POST']  )(registrar_movimiento)

# §7.1 — Descontar stock y cobrar el producto en una sola transacción.
inventario_bp.route('/inventario/consumo-habitacion',       methods=['POST']  )(consumo_habitacion)