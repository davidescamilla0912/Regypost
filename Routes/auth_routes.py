from flask import Blueprint
from Controllers.auth_controller import login
from extensions import limiter

auth_bp = Blueprint('auth', __name__)

@limiter.limit("5 per minute")
def login_route():
    return login()

auth_bp.route('/auth/login', methods=['POST'])(login_route)