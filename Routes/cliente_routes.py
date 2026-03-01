from flask import Blueprint
from Controllers.cliente_controller import (
    get_all_clientes, get_cliente, get_cliente_by_documento,
    create_cliente, update_cliente, delete_cliente, search_clientes
)

cliente_bp = Blueprint('clientes', __name__)

cliente_bp.route('/clientes',                        methods=['GET']   )(get_all_clientes)
cliente_bp.route('/clientes/<int:id>',               methods=['GET']   )(get_cliente)
cliente_bp.route('/clientes/documento/<numero_documento>', methods=['GET'])(get_cliente_by_documento)
cliente_bp.route('/clientes/buscar',                 methods=['GET']   )(search_clientes)
cliente_bp.route('/clientes',                        methods=['POST']  )(create_cliente)
cliente_bp.route('/clientes/<int:id>',               methods=['PUT']   )(update_cliente)
cliente_bp.route('/clientes/<int:id>',               methods=['DELETE'])(delete_cliente)