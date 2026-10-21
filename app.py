import logging
from datetime import timedelta

from flask import Flask, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from Config import JWT_ACCESS_TOKEN_EXPIRES, JWT_SECRET_KEY
from extensions import limiter
from utils import respuestas

from Routes.auth_routes import auth_bp
from Routes.cliente_routes import cliente_bp
from Routes.habitacion_routes import habitacion_bp
from Routes.empleado_routes import empleado_bp
from Routes.reserva_routes import reserva_bp
from Routes.consumo_pago_routes import consumo_pago_bp
from Routes.inventario_routes import inventario_bp
from Routes.gasto_parqueadero_caja_routes import gasto_parqueadero_caja_bp

app = Flask(__name__)
CORS(app, origins=[
    "http://localhost:3000"
], supports_credentials=True)

app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(seconds=JWT_ACCESS_TOKEN_EXPIRES)

jwt = JWTManager(app)
limiter.init_app(app)

logger = logging.getLogger(__name__)


@limiter.request_filter
def exempt_options():
    return request.method == "OPTIONS"


# ─── §2.2 y §5.4 — Todos los errores con la misma forma ──────────────────────
# El frontend cierra sesión al recibir un 401; para que eso funcione hace falta
# que el backend devuelva 401 de verdad con el token vencido, y con el mismo
# sobre `{"error": ..., "codigo": ...}` que el resto de la API.

@jwt.expired_token_loader
def token_expirado(header, payload):
    return respuestas.error('Tu sesión expiró. Vuelve a iniciar sesión.', 401,
                            codigo='TOKEN_EXPIRADO')


@jwt.invalid_token_loader
def token_invalido(motivo):
    return respuestas.error('Token inválido. Vuelve a iniciar sesión.', 401,
                            codigo='TOKEN_INVALIDO')


@jwt.unauthorized_loader
def falta_token(motivo):
    return respuestas.error('Necesitas iniciar sesión para hacer esto.', 401,
                            codigo='NO_AUTENTICADO')


@jwt.revoked_token_loader
def token_revocado(header, payload):
    return respuestas.error('Tu sesión fue cerrada. Vuelve a iniciar sesión.',
                            401, codigo='TOKEN_REVOCADO')


@app.errorhandler(404)
def no_encontrado(error):
    return respuestas.error('Recurso no encontrado', 404, codigo='NO_ENCONTRADO')


@app.errorhandler(405)
def metodo_no_permitido(error):
    return respuestas.error('Método no permitido para esta ruta', 405,
                            codigo='METODO_NO_PERMITIDO')


@app.errorhandler(429)
def demasiadas_peticiones(error):
    return respuestas.error('Demasiados intentos. Espera un momento.', 429,
                            codigo='LIMITE_PETICIONES')


@app.errorhandler(Exception)
def error_no_controlado(error):
    """
    Red de seguridad: un fallo inesperado nunca debe devolver el HTML de
    depuración de Flask ni un traceback al navegador. Se registra completo en
    el log del servidor y el cliente recibe el sobre de error de siempre.
    """
    from werkzeug.exceptions import HTTPException

    if isinstance(error, HTTPException):
        return respuestas.error(error.description or error.name,
                                error.code or 500,
                                codigo='HTTP_ERROR')

    logger.exception('Error no controlado en %s %s', request.method, request.path)
    return respuestas.error(
        'Ocurrió un error interno. Intenta de nuevo o avisa a soporte.', 500,
        codigo='ERROR_INTERNO')


@app.route("/")
def home():
    return respuestas.recurso({'estado': 'ok', 'api': 'RegyHotel'})


app.register_blueprint(auth_bp)
app.register_blueprint(cliente_bp)
app.register_blueprint(habitacion_bp)
app.register_blueprint(empleado_bp)
app.register_blueprint(reserva_bp)
app.register_blueprint(consumo_pago_bp)
app.register_blueprint(inventario_bp)
app.register_blueprint(gasto_parqueadero_caja_bp)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True)
