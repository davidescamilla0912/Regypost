from functools import wraps   # proteger endpoints con permisos
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def requiere_permiso(permiso):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            permisos = claims.get('permisos', [])
            if permiso not in permisos:
                return jsonify({"error": f"No tienes permiso: {permiso}"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator