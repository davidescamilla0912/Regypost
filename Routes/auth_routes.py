from flask import Blueprint
from Controllers.auth_controller import login

auth_bp = Blueprint('auth', __name__)

auth_bp.route('/auth/login', methods=['POST'])(login)