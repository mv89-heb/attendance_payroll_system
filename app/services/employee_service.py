import logging
from typing import List, Dict, Any, Optional
from datetime import date
from werkzeug.security import generate_password_hash
from app.db import db

logger = logging.getLogger(__name__)

class EmployeeService:

    @staticmethod
    def create_employee(
        employee_number: str,
        first_name: str,
        last_name: str,
        phone: str,
        email: str,
        kiosk_pin: str,
        hire_date: date,
        termination_date: Optional[date] = None
    ) -> int:
        """יוצר עובד חדש ומאבטח את קוד ה-PIN שלו."""
        pin_hash = generate_password_hash(kiosk_pin, method="scrypt")
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO employees (employee_number, first_name, last_name, phone, email, kiosk_pin_hash, hire_date, termination_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """, (employee_number, first_name, last_name, phone, email, pin_hash, hire_date, termination_date))
            emp_id = cur.fetchone()[0]
            return emp_id

    @staticmethod
    def update_employee(
        employee_id: int,
        first_name: str,
        last_name: str,
        phone: str,
        email: str,
        hire_date: date,
        termination_date: Optional[date] = None,
        kiosk_pin: Optional[str] = None
    ):
        """מעדכן פרטי עובד. ה-PIN מעודכן רק במידה וסופק ערך חדש."""
        with db.cursor() as cur:
            cur.execute("""
                UPDATE employees
                SET first_name = %s, last_name = %s, phone = %s, email = %s, hire_date = %s, termination_date = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (first_name, last_name, phone, email, hire_date, termination_date, employee_id))
            
            if kiosk_pin:
                pin_hash = generate_password_hash(kiosk_pin, method="scrypt")
                cur.execute("UPDATE employees SET kiosk_pin_hash = %s WHERE id = %s;", (pin_hash, employee_id))

    @staticmethod
    def set_employee_status(employee_id: int, active: bool):
        """משבית או מפעיל מחדש עובד (Soft Deactivation) לשמירת היסטוריית שכר ונוכחות."""
        with db.cursor() as cur:
            cur.execute("UPDATE employees SET active = %s WHERE id = %s;", (active, employee_id))

    @staticmethod
    def get_employee(employee_id: int) -> Optional[Dict[str, Any]]:
        with db.cursor() as cur:
            cur.execute("""
                SELECT id, employee_number, first_name, last_name, phone, email, active, hire_date, termination_date
                FROM employees WHERE id = %s;
            """, (employee_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "employee_number": row[1],
                "first_name": row[2],
                "last_name": row[3],
                "phone": row[4],
                "email": row[5],
                "active": row[6],
                "hire_date": row[7],
                "termination_date": row[8]
            }

    @staticmethod
    def list_employees(search_query: Optional[str] = None, active_only: bool = False) -> List[Dict[str, Any]]:
        """מחזיר רשימת עובדים מפורטת כולל אפשרויות חיפוש וסינון."""
        sql = """
            SELECT id, employee_number, first_name, last_name, phone, email, active, hire_date, termination_date
            FROM employees WHERE 1=1
        """
        params = []
        if active_only:
            sql += " AND active = TRUE"
        if search_query:
            sql += " AND (first_name ILIKE %s OR last_name ILIKE %s OR employee_number ILIKE %s)"
            q = f"%{search_query}%"
            params.extend([q, q, q])
            
        sql += " ORDER BY id DESC;"
        
        with db.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [{
                "id": r[0],
                "employee_number": r[1],
                "first_name": r[2],
                "last_name": r[3],
                "phone": r[4],
                "email": r[5],
                "active": r[6],
                "hire_date": r[7],
                "termination_date": r[8]
            } for r in rows]

    @staticmethod
    def assign_employee_domain(employee_id: int, domain_id: int, valid_from: date, valid_until: Optional[date] = None):
        """משייך עובד לתחום עבודה לטווח תאריכים מוגדר."""
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO employee_domains (employee_id, domain_id, valid_from, valid_until)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (employee_id, domain_id, valid_from) 
                DO UPDATE SET valid_until = EXCLUDED.valid_until;
            """, (employee_id, domain_id, valid_from, valid_until))
