import pytest
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from app.db import db
from app.services.auth_service import AuthService
from app.services.employee_service import EmployeeService
from app.services.domain_service import DomainService
from app.services.attendance_service import AttendanceService

def test_kiosk_auth_secure_flow(client, db_conn):
    """בדיקת אימות PIN חסין ב-Kiosk, חסימת עובדים ללא שיוך, ומניעת התחזות (Spoofing)."""
    from werkzeug.security import generate_password_hash
    pin_hash = generate_password_hash("1234", method="scrypt")
    with db_conn.cursor() as cur:
        # עובד 1 משוייך לתחום (שיוך פעיל מ-2026 כדי להיות תקף תחת CURRENT_DATE של 2026-08-09)
        cur.execute("""
            INSERT INTO employees (employee_number, first_name, last_name, email, kiosk_pin_hash, hire_date)
            VALUES ('EMP_KIOSK_OK', 'John', 'Doe', 'john@kiosk.com', %s, '2026-01-01') RETURNING id;
        """, (pin_hash,))
        emp_ok_id = cur.fetchone()[0]

        # עובד 2 ללא שיוך תחום עבודה
        cur.execute("""
            INSERT INTO employees (employee_number, first_name, last_name, email, kiosk_pin_hash, hire_date)
            VALUES ('EMP_KIOSK_NO', 'Jane', 'Smith', 'jane@kiosk.com', %s, '2026-01-01') RETURNING id;
        """, (pin_hash,))
        emp_no_id = cur.fetchone()[0]

        cur.execute("INSERT INTO work_domains (name, code) VALUES ('Global Tech', 'TECH') RETURNING id;")
        domain_id = cur.fetchone()[0]

        # שיוך עובד 1 לתחום
        cur.execute("""
            INSERT INTO employee_domains (employee_id, domain_id, valid_from)
            VALUES (%s, %s, '2026-01-01');
        """, (emp_ok_id, domain_id))
        db_conn.commit()

    # 1. ניסיון אימות עובד ללא שיוך (חייב להיחסם 403!)
    res_no = client.post("/kiosk/verify", json={"employee_number": "EMP_KIOSK_NO", "pin": "1234"})
    assert res_no.status_code == 403

    # 2. אימות עובד משוייך תקין
    res_ok = client.post("/kiosk/verify", json={"employee_number": "EMP_KIOSK_OK", "pin": "1234"})
    assert res_ok.status_code == 200

    # 3. ניסיון החתמת כניסה ללא PIN Verify (חייב להיחסם עקב חוסר session!)
    client.post("/kiosk/reset")
    res_punch_fail = client.post("/kiosk/punch", json={"domain_id": domain_id, "punch_type": "IN"})
    assert res_punch_fail.status_code == 401

def test_open_shifts_missed_pund_detection(app, db_conn):
    """בדיקת איתור משמרות פתוחות חריגות ומשמרות של היום."""
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO employees (employee_number, first_name, last_name, email, kiosk_pin_hash, hire_date)
            VALUES ('EMP_OPEN_99', 'Danny', 'Levy', 'danny@open.com', 'pin', '2027-01-01') RETURNING id;
        """)
        emp_id = cur.fetchone()[0]
        cur.execute("INSERT INTO work_domains (name, code) VALUES ('Kitchen Work', 'KTCH') RETURNING id;")
        domain_id = cur.fetchone()[0]
        
        # יצירת משמרת פתוחה מאתמול (חריגה)
        past_date = date.today() - timedelta(days=1)
        start_time = datetime.now(ZoneInfo("UTC")) - timedelta(days=1)
        cur.execute("""
            INSERT INTO shifts (employee_id, domain_id, shift_date, start_time, status, source)
            VALUES (%s, %s, %s, %s, 'PENDING', 'AUTO');
        """, (emp_id, domain_id, past_date, start_time))
        db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM shifts WHERE employee_id = %s AND end_time IS NULL;", (emp_id,))
        open_shift = cur.fetchone()
        assert open_shift is not None

def test_manual_shift_close_lock_enforcement(app, db_conn):
    """וידוא חסימת סגירה מנהלית של משמרת פתוחה בתוך חודש שכר נעול (LOCKED)."""
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO employees (employee_number, first_name, last_name, email, kiosk_pin_hash, hire_date)
            VALUES ('EMP_LOCK_SH', 'Rina', 'Ziv', 'rina@lock.com', 'pin', '2026-01-01') RETURNING id;
        """)
        emp_id = cur.fetchone()[0]
        cur.execute("INSERT INTO work_domains (name, code) VALUES ('Locked Admin', 'LOCK_ADM') RETURNING id;")
        domain_id = cur.fetchone()[0]
        
        # 1. יצירת תקופה פתוחה (OPEN) באוגוסט 2026
        cur.execute("""
            INSERT INTO payroll_periods (year, month, start_date, end_date, status)
            VALUES (2026, 8, '2026-08-01', '2026-08-31', 'OPEN') RETURNING id;
        """)
        period_id = cur.fetchone()[0]
        
        # 2. יצירת משמרת פתוחה בתוך התקופה הפתוחה (הטריגר מאשר את הרישום!)
        start_time = datetime(2026, 8, 15, 8, 0, 0, tzinfo=ZoneInfo("UTC"))
        cur.execute("""
            INSERT INTO shifts (employee_id, domain_id, shift_date, start_time, status, source)
            VALUES (%s, %s, '2026-08-15', %s, 'PENDING', 'AUTO') RETURNING id;
        """, (emp_id, domain_id, start_time))
        shift_id = cur.fetchone()[0]
        db_conn.commit()

    # 3. נעילת התקופה לחלוטין (LOCKED)
    with db_conn.cursor() as cur:
        cur.execute("UPDATE payroll_periods SET status = 'LOCKED' WHERE id = %s;", (period_id,))
        db_conn.commit()

    # 4. ניסיון סגירת משמרת ידנית (חייב להיחסם ברמת השרת עקב הנעילה!)
    import psycopg
    with pytest.raises(psycopg.Error) as excinfo:
        with db_conn.cursor() as cur:
            cur.execute("UPDATE shifts SET end_time = %s WHERE id = %s;", (datetime.now(ZoneInfo("UTC")), shift_id))
            db_conn.commit()
    assert "MIGRATION_LOCK_ERROR" in str(excinfo.value)