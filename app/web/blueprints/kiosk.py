import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, session
from zoneinfo import ZoneInfo
from app.services.auth_service import AuthService
from app.services.attendance_service import AttendanceService
from app.db import db

kiosk_bp = Blueprint("kiosk", __name__, url_prefix="/kiosk")
logger = logging.getLogger(__name__)

@kiosk_bp.route("", methods=["GET"])
def kiosk_index():
    return render_template("kiosk.html")

@kiosk_bp.route("/verify", methods=["POST"])
def verify_employee():
    data = request.get_json() or {}
    emp_num = data.get("employee_number")
    pin = data.get("pin")

    if not emp_num or not pin:
        return jsonify({"error": "נא להזין מספר עובד וקוד PIN"}), 400

    # 1. בדיקת חסימת Brute Force זמנית לעובד
    is_locked, lock_message = AuthService.is_kiosk_locked(emp_num)
    if is_locked:
        return jsonify({"error": lock_message}), 403

    emp_data = AuthService.authenticate_kiosk_employee(emp_num, pin)
    if not emp_data:
        return jsonify({"error": "קוד PIN או מספר עובד שגויים"}), 401

    emp_id = emp_data["employee_id"]

    # 2. שליפת תחומי העבודה הפעילים של העובד
    domains = []
    with db.cursor() as cur:
        cur.execute("""
            SELECT wd.id, wd.name, wd.code
            FROM work_domains wd
            JOIN employee_domains ed ON ed.domain_id = wd.id
            WHERE ed.employee_id = %s 
              AND ed.valid_from <= CURRENT_DATE 
              AND (ed.valid_until >= CURRENT_DATE OR ed.valid_until IS NULL)
              AND wd.active = TRUE;
        """, (emp_id,))
        domains = [{"id": r[0], "name": r[1], "code": r[2]} for r in cur.fetchall()]

    if not domains:
        return jsonify({"error": "לעובד זה לא הוגדר תחום עבודה פעיל. יש לפנות למנהל."}), 403

    session["kiosk_employee_id"] = emp_id

    return jsonify({
        "status": "verified",
        "employee": emp_data,
        "domains": domains
    }), 200

@kiosk_bp.route("/punch", methods=["POST"])
def record_punch():
    data = request.get_json() or {}
    domain_id = data.get("domain_id")
    punch_type = data.get("punch_type")

    emp_id = session.get("kiosk_employee_id")
    if not emp_id:
        return jsonify({"error": "אנא בצע אימות PIN מחדש"}), 401

    if not domain_id or not punch_type:
        return jsonify({"error": "נתוני החתמה חסרים"}), 400

    now = datetime.now(ZoneInfo("UTC"))
    res = AttendanceService.record_kiosk_punch(emp_id, domain_id, punch_type, now)

    if res["status"] == "REJECTED":
        return jsonify({"error": "החתמה כפולה נחסמה. נא להמתין 2 דקות בין לחיצות."}), 400

    session.pop("kiosk_employee_id", None)

    return jsonify({
        "status": "success",
        "integrity_status": res["integrity_status"],
        "work_date": res["work_date"]
    }), 200

@kiosk_bp.route("/reset", methods=["POST"])
def reset_session():
    session.pop("kiosk_employee_id", None)
    return jsonify({"status": "reset"}), 200