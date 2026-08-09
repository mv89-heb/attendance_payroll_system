import pytest
import json
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from app.db import db
from app.services.payroll_calculation_service import PayrollCalculationService
from app.services.employment_service import EmploymentService
from app.services.payroll_period_service import PayrollPeriodService

def test_stateless_payroll_calculation_flow(app, db_conn):
    """
    בדיקת אינטגרציה מלאה של מנוע השכר:
    מחשב שכר, החזר נסיעות, ברוטו ונטו תחת Decimal מדוייק ויוצר Snapshot תקין.
    """
    with db_conn.cursor() as cur:
        # יצירת עובד
        cur.execute("""
            INSERT INTO employees (employee_number, first_name, last_name, email, kiosk_pin_hash, hire_date)
            VALUES ('EMP_CALC_99', 'Rami', 'Levi', 'rami@test.com', 'pin', '2027-01-01') RETURNING id;
        """)
        emp_id = cur.fetchone()[0]

        # יצירת תחומי עבודה
        cur.execute("INSERT INTO work_domains (name, code) VALUES ('Kitchen Work', 'KTCH') RETURNING id;")
        domain_id = cur.fetchone()[0]

        # יצירת תקופת שכר 09/2027
        cur.execute("""
            INSERT INTO payroll_periods (year, month, start_date, end_date, status)
            VALUES (2027, 9, '2027-09-01', '2027-09-30', 'OPEN') RETURNING id;
        """)
        period_id = cur.fetchone()[0]
        db_conn.commit()

    # יצירת תנאי העסקה (שנת 2027 למניעת חפיפה עם נעילות של 2026)
    EmploymentService.create_employment_term(
        employee_id=emp_id,
        effective_from=date(2027, 9, 1),
        effective_to=date(2027, 9, 30),
        employment_type="HOURLY",
        base_salary=Decimal("0.00"),
        hourly_rate=Decimal("45.50"),
        monthly_hours=Decimal("150.00"),
        travel_rate=Decimal("20.00")
    )

    # רישום משמרת מאושרת אחת של 8 שעות (APPROVED) ב-2027-09-15
    start_t = datetime(2027, 9, 15, 8, 0, 0, tzinfo=ZoneInfo("UTC"))
    end_t = datetime(2027, 9, 15, 16, 0, 0, tzinfo=ZoneInfo("UTC"))
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO shifts (employee_id, domain_id, shift_date, start_time, end_time, break_minutes, status, source)
            VALUES (%s, %s, '2027-09-15', %s, %s, 0, 'APPROVED', 'AUTO');
        """, (emp_id, domain_id, start_t, end_t))
        db_conn.commit()

    # יצירת משתמש מוסמך תקין להרצת השכר (מונע ForeignKeyViolation)
    from app.services.auth_service import AuthService
    user_id = AuthService.register_user("payroll_runner", "runner@payroll.com", "runnerpass")
    AuthService.assign_role_to_user(user_id, "SUPER_ADMIN")

    # הרצת מנוע השכר
    run_id = PayrollCalculationService.calculate_period_payroll(period_id, user_id)
    assert run_id is not None

    with db_conn.cursor() as cur:
        cur.execute("SELECT total_gross, total_net, calculations_snapshot FROM payroll_results WHERE payroll_run_id = %s;", (run_id,))
        res = cur.fetchone()
        assert res is not None
        # ברוטו צפוי: (8 שעות X 45.5 ש"ח) + 20 ש"ח נסיעות (יום אחד בפועל) = 384.00 ש"ח
        assert res[0] == Decimal("384.0000")
        assert res[1] == Decimal("384.0000")

        # Safe JSON Deserialization (תומך במילון פייתון ובמחרוזת מנוונת במקביל)
        raw_snap = res[2]
        if isinstance(raw_snap, dict):
            snapshot = raw_snap
        else:
            snapshot = json.loads(raw_snap) if raw_snap else {}

        assert snapshot["employment_type"] == "HOURLY"
        assert len(snapshot["calculation_steps"]) == 2

def test_payroll_lock_immutability(app, db_conn):
    """בדיקת אכיפת Immutability: חסימת הרצת חישוב שכר חדש עבור חודש נעול."""
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO payroll_periods (year, month, start_date, end_date, status)
            VALUES (2027, 10, '2027-10-01', '2027-10-31', 'LOCKED') RETURNING id;
        """)
        period_id = cur.fetchone()[0]
        db_conn.commit()

    with pytest.raises(ValueError) as excinfo:
        # הרצת מנוע שכר על חודש נעול
        PayrollCalculationService.calculate_period_payroll(period_id, 1)
    assert "MIGRATION_LOCK_ERROR" in str(excinfo.value)

def test_payroll_web_routes_auth_check(client):
    """וידוא אבטחה (Authorization) של נתיבי השכר הראשיים בממשק ה-Web."""
    response = client.get("/payroll-periods")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]