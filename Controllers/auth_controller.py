"""
§5.1 y §5.4 — Autenticación.

El JWT ya llevaba `roles` y `permisos`; el cambio aquí es que `roles` viaja
como **array** y no como la cadena de `GROUP_CONCAT`, y que la respuesta del
login trae sólo lo mínimo para pintar la cabecera, en vez del objeto empleado
completo que se guardaba en `localStorage`.

También se expone `GET /auth/me`, para que el frontend pueda reconstruir la
sesión sin confiar en lo que tenga guardado el navegador.
"""
from datetime import timedelta

from flask import request
from flask_jwt_extended import create_access_token, get_jwt, jwt_required

from Config import JWT_ACCESS_TOKEN_EXPIRES
from Models.auth_model import AuthModel
from utils import respuestas
from utils.decorators import empleado_actual_id

model = AuthModel()


def _lista_roles(valor):
    """`GROUP_CONCAT` devuelve 'admin,gerente'; el frontend quiere un array."""
    if not valor:
        return []
    if isinstance(valor, (list, tuple)):
        return list(valor)
    return [r.strip() for r in str(valor).split(',') if r.strip()]


def login():
    data = request.json or {}
    if not data.get('usuario') or not data.get('contrasena'):
        return respuestas.error('usuario y contrasena son requeridos', 400,
                                codigo='CAMPOS_REQUERIDOS')

    empleado = model.login(data['usuario'], data['contrasena'])
    if not empleado:
        return respuestas.error('Credenciales incorrectas', 401,
                                codigo='CREDENCIALES_INVALIDAS')

    roles = _lista_roles(empleado.get('roles'))
    permisos = model.get_permisos(empleado['id'])

    token = create_access_token(
        identity=str(empleado['id']),
        additional_claims={
            'nombre': empleado['nombre'],
            'apellido': empleado['apellido'],
            'usuario': empleado['usuario'],
            'roles': roles,
            'permisos': permisos,
        },
        expires_delta=timedelta(seconds=JWT_ACCESS_TOKEN_EXPIRES),
    )

    return respuestas.recurso(
        {
            'token': token,
            'expira_en': JWT_ACCESS_TOKEN_EXPIRES,
            'empleado': {
                'id': empleado['id'],
                'nombre': empleado['nombre'],
                'apellido': empleado['apellido'],
                'usuario': empleado['usuario'],
                'roles': roles,
                'permisos': permisos,
            },
        },
        mensaje='Login exitoso',
    )


@jwt_required()
def me():
    """
    GET /auth/me — quién soy según el token.

    Sirve para que el frontend arme su `useAuth()` y su `<RutaProtegida>` sin
    leer el empleado de `localStorage`.
    """
    claims = get_jwt()
    return respuestas.recurso({
        'id': empleado_actual_id(),
        'nombre': claims.get('nombre'),
        'apellido': claims.get('apellido'),
        'usuario': claims.get('usuario'),
        'roles': _lista_roles(claims.get('roles')),
        'permisos': claims.get('permisos') or [],
    })
