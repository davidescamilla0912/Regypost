"""
§5 — Autorización.

El backend ya protegía cada endpoint con `requiere_permiso`; lo que faltaba era
poder saber QUIÉN llama sin creerle al cliente. `empleado_actual_id()` toma la
identidad del JWT, y con eso `empleado_id` deja de viajar en el body (F34).
"""
from functools import wraps

from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from utils.respuestas import error


def requiere_permiso(permiso):
    """Exige un permiso concreto. 401 si no hay token, 403 si le falta."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            if not tiene_permiso(permiso):
                return error(
                    f'No tienes permiso para esta operación: {permiso}',
                    403,
                    codigo='PERMISO_DENEGADO',
                    permiso=permiso,
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def requiere_alguno(*permisos):
    """Exige al menos uno de varios permisos."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            if not any(tiene_permiso(p) for p in permisos):
                return error(
                    'No tienes permiso para esta operación',
                    403,
                    codigo='PERMISO_DENEGADO',
                    permisos_requeridos=list(permisos),
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def permisos_actuales():
    """Lista de permisos del empleado autenticado, tomada del JWT."""
    try:
        return get_jwt().get('permisos') or []
    except Exception:
        return []


def roles_actuales():
    """Lista de roles del empleado autenticado, tomada del JWT."""
    try:
        roles = get_jwt().get('roles') or []
    except Exception:
        return []
    # El login los arma con GROUP_CONCAT, así que pueden llegar como cadena.
    if isinstance(roles, str):
        return [r.strip() for r in roles.split(',') if r.strip()]
    return list(roles)


def tiene_permiso(permiso):
    """True si el empleado autenticado tiene ese permiso."""
    return permiso in permisos_actuales()


def es_admin():
    return 'admin' in roles_actuales()


def empleado_actual_id():
    """
    Id del empleado autenticado, tomado del JWT y NUNCA del body.

    Este es el cambio que impide falsificar quién cobró (F34): antes el
    `empleado_id` salía de `localStorage` y viajaba en el request.
    """
    try:
        identidad = get_jwt_identity()
    except Exception:
        return None
    if identidad is None:
        return None
    try:
        return int(identidad)
    except (TypeError, ValueError):
        return None
