from flask import Blueprint
from Controllers.auth_controller import login
from app import limiter

auth_bp = Blueprint('auth', __name__)

auth_bp.route('/auth/login', methods=['POST'])(login)
@limiter.limit("5 per minute")
def login_route():
    return login()