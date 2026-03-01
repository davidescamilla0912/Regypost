from flask import Flask
from Routes.cliente_routes import cliente_bp
from Routes.habitacion_routes import habitacion_bp
from Routes.empleado_routes import empleado_bp

app = Flask(__name__)
app.register_blueprint(cliente_bp)
app.register_blueprint(habitacion_bp)
app.register_blueprint(empleado_bp)

if __name__ == '__main__':
    app.run(debug=True)