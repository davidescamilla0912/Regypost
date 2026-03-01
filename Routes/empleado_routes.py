from flask import Blueprint
from Controllers.rol_controller import (
    get_all_roles, get_rol, create_rol, update_rol, delete_rol,
    get_permisos_rol, asignar_permiso_rol, quitar_permiso_rol
)
from Controllers.empleado_controller import (
    get_all_empleados, get_empleado, create_empleado, update_empleado,
    update_contrasena_empleado, delete_empleado,
    asignar_rol_empleado, quitar_rol_empleado
)

empleado_bp = Blueprint('empleados', __name__)

# Roles
empleado_bp.route('/roles',                                    methods=['GET']   )(get_all_roles)
empleado_bp.route('/roles/<int:id>',                           methods=['GET']   )(get_rol)
empleado_bp.route('/roles',                                    methods=['POST']  )(create_rol)
empleado_bp.route('/roles/<int:id>',                           methods=['PUT']   )(update_rol)
empleado_bp.route('/roles/<int:id>',                           methods=['DELETE'])(delete_rol)
empleado_bp.route('/roles/<int:rol_id>/permisos',              methods=['GET']   )(get_permisos_rol)
empleado_bp.route('/roles/<int:rol_id>/permisos',              methods=['POST']  )(asignar_permiso_rol)
empleado_bp.route('/roles/<int:rol_id>/permisos/<int:permiso_id>', methods=['DELETE'])(quitar_permiso_rol)

# Empleados
empleado_bp.route('/empleados',                                      methods=['GET']   )(get_all_empleados)
empleado_bp.route('/empleados/<int:id>',                             methods=['GET']   )(get_empleado)
empleado_bp.route('/empleados',                                      methods=['POST']  )(create_empleado)
empleado_bp.route('/empleados/<int:id>',                             methods=['PUT']   )(update_empleado)
empleado_bp.route('/empleados/<int:id>/contrasena',                  methods=['PATCH'] )(update_contrasena_empleado)
empleado_bp.route('/empleados/<int:id>',                             methods=['DELETE'])(delete_empleado)
empleado_bp.route('/empleados/<int:empleado_id>/roles',              methods=['POST']  )(asignar_rol_empleado)
empleado_bp.route('/empleados/<int:empleado_id>/roles/<int:rol_id>', methods=['DELETE'])(quitar_rol_empleado)