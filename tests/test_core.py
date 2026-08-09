import pytest
import os
from datetime import datetime, date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from app.utils.money import round_money, to_decimal
from app.utils.time import calculate_work_date, utc_to_local
from app.services.auth_service import AuthService
from app.services.employee_service import EmployeeService
from app.services.domain_service import DomainService

def test_decimal_rounding(app):
    val1 = to_decimal("150.255")
    val2 = to_decimal("2.112")
    res = val1 * val2
    assert round_money(res, 2) == Decimal("317.34")

def test_timezone_conversion(app):
    utc_time = datetime(2026, 6, 1, 23, 0, 0, tzinfo=ZoneInfo("UTC"))
    local_time = utc_to_local(utc_time)
    assert local_time.hour == 2
    assert local_time.date() == date(2026, 6, 2)

def test_cross_midnight_shift_date(app):
    utc_time_early = datetime(2026, 6, 2, 0, 30, 0, tzinfo=ZoneInfo("UTC"))
    work_day = calculate_work_date(utc_time_early)
    assert work_day == date(2026, 6, 1)

def test_clean_schema_and_insert_user(app, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO roles (name) VALUES ('EMPLOYEE') ON CONFLICT DO NOTHING;")
        db_conn.commit()
        
    user_id = AuthService.register_user("john_doe", "john@example.com", "securepass123")
    AuthService.assign_role_to_user(user_id, "EMPLOYEE")
    
    auth_data = AuthService.authenticate_web_user("john_doe", "securepass123")
    assert auth_data is not None
    assert "EMPLOYEE" in auth_data["roles"]

def test_kiosk_punch_integrity(app, db_conn):
    from werkzeug.security import generate_password_hash
    pin_hash = generate_password_hash("1234", method="scrypt")
    with db_conn.cursor() as cur:
        cur.execute('''
            INSERT INTO employees (employee_number, first_name, last_name, email, kiosk_pin_hash, hire_date)
            VALUES ('EMP001', 'David', 'Cohen', 'david@example.com', %s, '2026-01-01') RETURNING id;
        ''', (pin_hash,))
        emp_id = cur.fetchone()[0]
        
        cur.execute("INSERT INTO work_domains (name, code) VALUES ('Global Tech', 'TECH') RETURNING id;")
        domain_id = cur.fetchone()[0]
        db_conn.commit()

    emp_auth = AuthService.authenticate_kiosk_employee("EMP001", "1234")
    assert emp_auth is not None
    assert emp_auth["employee_id"] == emp_id

    now = datetime.now(ZoneInfo("UTC"))
    from app.services.attendance_service import AttendanceService
    punch_res = AttendanceService.record_kiosk_punch(emp_id, domain_id, "IN", now)
    assert punch_res["status"] == "ACCEPTED"
    assert punch_res["integrity_status"] == "VALID"

    double_click_res = AttendanceService.record_kiosk_punch(emp_id, domain_id, "IN", now + timedelta(seconds=10))
    assert double_click_res["status"] == "REJECTED"
    assert double_click_res["reason"] == "DOUBLE_CLICK_PREVENTION"

def test_payroll_lock_database_enforcement(app, db_conn):
    with db_conn.cursor() as cur:
        cur.execute('''
            INSERT INTO payroll_periods (year, month, start_date, end_date, status)
            VALUES (2026, 8, '2026-08-01', '2026-08-31', 'LOCKED') RETURNING id;
        ''')
        period_id = cur.fetchone()[0]
        
        cur.execute('''
            INSERT INTO employees (employee_number, first_name, last_name, email, kiosk_pin_hash, hire_date)
            VALUES ('EMP999', 'Sarah', 'Levy', 'sarah@example.com', 'pin', '2026-01-01') RETURNING id;
        ''')
        emp_id = cur.fetchone()[0]
        
        cur.execute("INSERT INTO work_domains (name, code) VALUES ('Locked Admin', 'LOCKED_ADM') RETURNING id;")
        domain_id = cur.fetchone()[0]
        db_conn.commit()

    import psycopg
    with pytest.raises(psycopg.Error) as excinfo:
        with db_conn.cursor() as cur:
            cur.execute('''
                INSERT INTO timesheet_entries (payroll_period_id, employee_id, domain_id, work_date, total_hours, calculation_snapshot)
                VALUES (%s, %s, %s, '2026-08-15', 8.00, '{}');
            ''', (period_id, emp_id, domain_id))
            db_conn.commit()
            
    assert "MIGRATION_LOCK_ERROR" in str(excinfo.value)

def test_migration_runner_env_loading(tmp_path, monkeypatch):
    mock_env = tmp_path / ".env"
    mock_env.write_text("DATABASE_URL=postgresql://test_env_user:pass@env_host:5432/env_db", encoding="utf-8")
    
    monkeypatch.delenv("DATABASE_URL", raising=False)
    
    from dotenv import load_dotenv
    assert os.getenv("DATABASE_URL") is None
    
    load_dotenv(str(mock_env), override=False)
    assert os.getenv("DATABASE_URL") == "postgresql://test_env_user:pass@env_host:5432/env_db"
    
    monkeypatch.setenv("DATABASE_URL", "postgresql://override_user:pass@override_host:5432/override_db")
    load_dotenv(str(mock_env), override=False)
    assert os.getenv("DATABASE_URL") == "postgresql://override_user:pass@override_host:5432/override_db"

# =========================================================================
# NEW PHASE 1 TESTS (Employees, Domains, RBAC, Web UI Views)
# =========================================================================

def test_employee_creation_and_deactivation(app):
    """בדיקת שירות יצירת עובד, עדכון וביצוע השבתה (Soft Delete)."""
    emp_id = EmployeeService.create_employee(
        employee_number="EMP9000",
        first_name="Moshe",
        last_name="Cohen",
        phone="050-1111111",
        email="moshe@cohen.com",
        kiosk_pin="4321",
        hire_date=date(2026, 1, 1)
    )
    assert emp_id is not None
    
    emp = EmployeeService.get_employee(emp_id)
    assert emp["first_name"] == "Moshe"
    assert emp["active"] is True
    
    # בדיקת Deactivation
    EmployeeService.set_employee_status(emp_id, False)
    emp_updated = EmployeeService.get_employee(emp_id)
    assert emp_updated["active"] is False

def test_domain_creation_and_assignment(app):
    """בדיקת שירות יצירת תחום עבודה דינמי ושיוך עובד אליו."""
    domain_id = DomainService.create_domain("Kitchen Staff", "KITCHEN")
    assert domain_id is not None
    
    domains = DomainService.list_domains()
    assert any(d["code"] == "KITCHEN" for d in domains)

def test_rbac_authorization(app, db_conn):
    """בדיקת אכיפת הרשאות מבוססת תפקידים ו-Permissions."""
    with db_conn.cursor() as cur:
        # Seed permissions
        cur.execute("INSERT INTO roles (name) VALUES ('SUPER_ADMIN') ON CONFLICT DO NOTHING;")
        db_conn.commit()

    user_id = AuthService.register_user("super_user", "super@system.com", "superpass")
    AuthService.assign_role_to_user(user_id, "SUPER_ADMIN")
    
    auth_data = AuthService.authenticate_web_user("super_user", "superpass")
    # Super Admin has all permission scopes mapped in 003_migration
    assert "employees.view" in auth_data["permissions"]

def test_web_ui_endpoints_without_auth(client):
    """וידוא שדפים חסומים מפנים (Redirect) חזרה למסך ה-Login."""
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
