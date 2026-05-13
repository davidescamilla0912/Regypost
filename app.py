from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from Config import JWT_SECRET_KEY
from extensions import limiter

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
    "https://regypost-frontend.vercel.app",
    "http://localhost:3000"
])
app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY

jwt = JWTManager(app)
limiter.init_app(app)


@app.route("/")
def home():
    return "API funcionando correctamente"

app.register_blueprint(auth_bp)
app.register_blueprint(cliente_bp)
app.register_blueprint(habitacion_bp)
app.register_blueprint(empleado_bp)
app.register_blueprint(reserva_bp)
app.register_blueprint(consumo_pago_bp)
app.register_blueprint(inventario_bp)
app.register_blueprint(gasto_parqueadero_caja_bp)

if __name__ == '__main__':
    app.run(debug=True)