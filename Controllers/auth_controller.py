from flask import request, jsonify
from flask_jwt_extended import create_access_token
from Models.auth_model import AuthModel
from datetime import timedelta

model = AuthModel()

def login():
    data = request.json
    if not data or not data.get('usuario') or not data.get('contrasena'):
        return jsonify({"error": "usuario y contrasena son requeridos"}), 400

    empleado = model.login(data['usuario'], data['contrasena'])

    if not empleado:
        return jsonify({"error": "Credenciales incorrectas"}), 401

    permisos = model.get_permisos(empleado['id'])

    token = create_access_token(
        identity=str(empleado['id']),
        additional_claims={
            "nombre": empleado['nombre'],
            "apellido": empleado['apellido'],
            "usuario": empleado['usuario'],
            "roles": empleado['roles'],
            "permisos": permisos
        },
        expires_delta=timedelta(hours=8)
    )

    return jsonify({
        "mensaje": "Login exitoso",
        "token": token,
        "empleado": {
            "id": empleado['id'],
            "nombre": empleado['nombre'],
            "apellido": empleado['apellido'],
            "usuario": empleado['usuario'],
            "roles": empleado['roles'],
            "permisos": permisos
        }
    }), 200