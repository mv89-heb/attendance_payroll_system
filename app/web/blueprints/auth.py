import logging
from flask import Blueprint, request, jsonify, session

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
logger = logging.getLogger(__name__)

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400
        
    from app.services.auth_service import AuthService
    user_data = AuthService.authenticate_web_user(username, password)
    if not user_data:
        logger.warning(f"Failed web login attempt for username: {username}")
        return jsonify({"error": "Invalid credentials"}), 401
        
    session["user"] = user_data
    return jsonify({
        "status": "success",
        "user": {
            "username": user_data["username"],
            "roles": user_data["roles"]
        }
    }), 200

@auth_bp.route("/kiosk-punch", methods=["POST"])
def kiosk_punch():
    data = request.get_json() or {}
    emp_num = data.get("employee_number")
    pin = data.get("pin")
    
    if not emp_num or not pin:
        return jsonify({"error": "Missing identification data"}), 400
        
    from app.services.auth_service import AuthService
    emp_data = AuthService.authenticate_kiosk_employee(emp_num, pin)
    if not emp_data:
        logger.warning(f"Failed Kiosk auth attempt for employee number: {emp_num}")
        return jsonify({"error": "Invalid employee number or PIN"}), 401
        
    return jsonify({
        "status": "identified",
        "employee": {
            "id": emp_data["employee_id"],
            "name": f"{emp_data['first_name']} {emp_data['last_name']}"
        }
    }), 200
