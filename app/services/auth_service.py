import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import db

logger = logging.getLogger(__name__)

class AuthService:
    
    @staticmethod
    def register_user(username: str, email: str, password: str, employee_id: Optional[int] = None) -> int:
        pw_hash = generate_password_hash(password, method="scrypt")
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO users (employee_id, username, email, password_hash)
                VALUES (%s, %s, %s, %s) RETURNING id;
            """, (employee_id, username, email, pw_hash))
            user_id = cur.fetchone()[0]
            return user_id

    @staticmethod
    def assign_role_to_user(user_id: int, role_name: str):
        with db.cursor() as cur:
            cur.execute("SELECT id FROM roles WHERE name = %s;", (role_name,))
            res = cur.fetchone()
            if not res:
                raise ValueError(f"Role {role_name} does not exist.")
            role_id = res[0]
            cur.execute("""
                INSERT INTO user_roles (user_id, role_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING;
            """, (user_id, role_id))

    @staticmethod
    def get_user_permissions(user_id: int) -> list:
        with db.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT p.name 
                FROM permissions p
                JOIN role_permissions rp ON rp.permission_id = p.id
                JOIN user_roles ur ON ur.role_id = rp.role_id
                WHERE ur.user_id = %s;
            """, (user_id,))
            return [row[0] for row in cur.fetchall()]

    @staticmethod
    def authenticate_web_user(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
        with db.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.username, u.password_hash, u.active, u.employee_id
                FROM users u
                WHERE u.username = %s OR u.email = %s;
            """, (username_or_email, username_or_email))
            user = cur.fetchone()
            if not user:
                return None
            
            user_id, username, pwd_hash, active, emp_id = user
            if not active or not check_password_hash(pwd_hash, password):
                return None
                
            cur.execute("""
                SELECT r.name FROM roles r
                JOIN user_roles ur ON ur.role_id = r.id
                WHERE ur.user_id = %s;
            """, (user_id,))
            roles = [row[0] for row in cur.fetchall()]
            
            permissions = AuthService.get_user_permissions(user_id)
            
            return {
                "user_id": user_id,
                "username": username,
                "employee_id": emp_id,
                "roles": roles,
                "permissions": permissions
            }

    # =========================================================================
    # KIOSK BRUTE-FORCE PROTECTION & PIN AUTH (Security Hardening)
    # =========================================================================

    @staticmethod
    def is_kiosk_locked(employee_number: str) -> tuple[bool, Optional[str]]:
        """בודק האם עובד נחסם זמנית להחתמות עקב מספר ניסיונות PIN כושלים."""
        with db.cursor() as cur:
            cur.execute("""
                SELECT failed_count, locked_until 
                FROM kiosk_failed_attempts 
                WHERE employee_number = %s;
            """, (employee_number,))
            row = cur.fetchone()
            if not row:
                return False, None
            
            failed_count, locked_until = row
            if locked_until and locked_until > datetime.now(ZoneInfo("UTC")):
                remaining = locked_until - datetime.now(ZoneInfo("UTC"))
                minutes_left = int(remaining.total_seconds() / 60) + 1
                return True, f"עמדת ההחתמה ננעלה זמנית עבור מספר עובד זה עקב ניסיונות כושלים מרובים. נותר זמן נעילה: {minutes_left} דקות."
            return False, None

    @staticmethod
    def record_kiosk_failed_attempt(employee_number: str):
        """רושם ניסיון כושל ונועל את העובד למשך 15 דקות במידה והגיע ל-5 כשלונות."""
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO kiosk_failed_attempts (employee_number, failed_count)
                VALUES (%s, 1)
                ON CONFLICT (employee_number) 
                DO UPDATE SET failed_count = kiosk_failed_attempts.failed_count + 1, updated_at = CURRENT_TIMESTAMP
                RETURNING failed_count;
            """, (employee_number,))
            failed_count = cur.fetchone()[0]

            if failed_count >= 5:
                locked_until = datetime.now(ZoneInfo("UTC")) + timedelta(minutes=15)
                cur.execute("""
                    UPDATE kiosk_failed_attempts 
                    SET locked_until = %s 
                    WHERE employee_number = %s;
                """, (locked_until, employee_number))
            db.connection()

    @staticmethod
    def reset_kiosk_attempts(employee_number: str):
        """מאפס את מונה הכשלונות והחסימה של העובד עם כניסתו המוצלחת."""
        with db.cursor() as cur:
            cur.execute("DELETE FROM kiosk_failed_attempts WHERE employee_number = %s;", (employee_number,))
            db.connection()

    @staticmethod
    def authenticate_kiosk_employee(employee_number: str, pin: str) -> Optional[Dict[str, Any]]:
        # בדיקת חסימת brute-force
        is_locked, lock_message = AuthService.is_kiosk_locked(employee_number)
        if is_locked:
            logger.warning(f"Blocked brute-force PIN attempt for locked employee number: {employee_number}")
            return None

        with db.cursor() as cur:
            cur.execute("""
                SELECT id, first_name, last_name, kiosk_pin_hash, active
                FROM employees
                WHERE employee_number = %s;
            """, (employee_number,))
            emp = cur.fetchone()
            if not emp:
                AuthService.record_kiosk_failed_attempt(employee_number)
                return None
                
            emp_id, first_name, last_name, pin_hash, active = emp
            if not active or not check_password_hash(pin_hash, pin):
                AuthService.record_kiosk_failed_attempt(employee_number)
                return None
                
            # איפוס כשלונות בכניסה מוצלחת
            AuthService.reset_kiosk_attempts(employee_number)
            
            return {
                "employee_id": emp_id,
                "first_name": first_name,
                "last_name": last_name
            }