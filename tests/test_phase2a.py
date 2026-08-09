import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from app.db import db
from app.services.employment_service import EmploymentService
from app.services.shift_service import ShiftService
from app.services.payroll_period_service import PayrollPeriodService
from app.services.payroll_calculation_service import PayrollCalculationService

def test_employment_terms_creation_and_lookup(app):
    """בדיקת יצירת תנאי העסקה היסטוריים ושליפתם המדוייקת לפי תאריך יעד."""
    with db.cursor() as cur:
        cur.execute("""
            INSERT INTO employees (employee_number, first_name, last_name, email, kiosk_pin_hash, hire_date)
            VALUES ('EMP_TERM_01', 'Avi', 'Levi', 'avi@test.com', 'pin', '2027-01-01') RETURNING id;
        """)
        emp_id = cur.fetchone()[0]
        db.connection()

    # 1. יצירת תנאים לתקופה ראשונה (שנת 2027 למניעת חפיפה עם תקופות נעולות של 2026)
    term_id = EmploymentService.create_employment_term(
        employee_id=emp_id,
        effective_from=date(2027, 1, 1),
        effective_to=date(2027, 6, 30),
        employment_type="HOURLY",
        base_salary=Decimal("0.00"),
        hourly_rate=Decimal("40.00"),
        monthly_hours=Decimal("150.00"),
        travel_rate=Decimal("15.00")
    )
    assert term_id is not None

    # 2. יצירת תנאים משופרים לתקופה שנייה
    term_id2 = EmploymentService.create_employment_term(
        employee_id=emp_id,
        effective_from=date(2027, 7, 1),
        effective_to=None,
        employment_type="HOURLY",
        base_salary=Decimal("0.00"),
        hourly_rate=Decimal("45.00"),
        monthly_hours=Decimal("150.00"),
        travel_rate=Decimal("20.00")
    )
    assert term_id2 is not None

    # 3. שליפה היסטורית לתקופה 1
    term_old = EmploymentService.get_active_term_for_date(emp_id, date(2027, 3, 15))
    assert term_old["hourly_rate"] == Decimal("40.0000")

    # 4. שליפה לתקופה הנוכחית
    term_new = EmploymentService.get_active_term_for_date(emp_id, date(2027, 8, 8))
    assert term_new["hourly_rate"] == Decimal("45.0000")

def test_prevent_employment_term_change_on_locked_period(app, db_conn):
    """בדיקת אכיפת שלמות נתוני מסד הנתונים: חסימת עדכון תנאי שכר בתוך חודש נעול."""
    with db_conn.cursor() as cur:
        # יצירת עובד
        cur.execute("""
            INSERT INTO employees (employee_number, first_name, last_name, email, kiosk_pin_hash, hire_date)
            VALUES ('EMP_LOCK_01', 'Noam', 'Gold', 'noam@test.com', 'pin', '2026-01-01') RETURNING id;
        """)
        emp_id = cur.fetchone()[0]

        # יצירת תקופת שכר נעולה
        cur.execute("""
            INSERT INTO payroll_periods (year, month, start_date, end_date, status)
            VALUES (2026, 5, '2026-05-01', '2026-05-31', 'LOCKED') RETURNING id;
        """)
        db_conn.commit()

    import psycopg
    with pytest.raises(psycopg.Error) as excinfo:
        # ניסיון ליצור תנאי העסקה החופפים לחודש הנעול 05/2026
        EmploymentService.create_employment_term(
            employee_id=emp_id,
            effective_from=date(2026, 5, 15),
            effective_to=date(2026, 5, 25),
            employment_type="HOURLY",
            base_salary=Decimal("0.00"),
            hourly_rate=Decimal("50.00"),
            monthly_hours=Decimal("100.00"),
            travel_rate=Decimal("10.00")
        )
    assert "MIGRATION_LOCK_ERROR" in str(excinfo.value)

def test_attendance_shift_pairing(app, db_conn):
    """בדיקת אגרגציית ה-Pairing שמחברת החתמות IN ו-OUT גולמיות למשמרת סגורה ומנורמלת."""
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO employees (employee_number, first_name, last_name, email, kiosk_pin_hash, hire_date)
            VALUES ('EMP_PAIR_01', 'Roy', 'Bar', 'roy@test.com', 'pin', '2027-01-01') RETURNING id;
        """)
        emp_id = cur.fetchone()[0]
        
        cur.execute("INSERT INTO work_domains (name, code) VALUES ('Global Service', 'GLOB_SRV') RETURNING id;")
        domain_id = cur.fetchone()[0]
        db_conn.commit()

    # שימוש בשנת 2027 למניעת חפיפה עם אוגוסט 2026 הנעול
    work_day = date(2027, 8, 8)
    now_in = datetime(2027, 8, 8, 8, 0, 0, tzinfo=ZoneInfo("UTC"))
    now_out = datetime(2027, 8, 8, 16, 0, 0, tzinfo=ZoneInfo("UTC"))

    # הקלטת החתמות
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO attendance_punches (employee_id, domain_id, punch_type, punched_at, work_date, source)
            VALUES (%s, %s, 'IN', %s, %s, 'KIOSK');
        """, (emp_id, domain_id, now_in, work_day))
        cur.execute("""
            INSERT INTO attendance_punches (employee_id, domain_id, punch_type, punched_at, work_date, source)
            VALUES (%s, %s, 'OUT', %s, %s, 'KIOSK');
        """, (emp_id, domain_id, now_out, work_day))
        db_conn.commit()

    # ביצוע צימוד משמרת מנורמלת
    ShiftService.process_raw_punches_to_shifts(emp_id, work_day)

    with db_conn.cursor() as cur:
        cur.execute("SELECT start_time, end_time, status FROM shifts WHERE employee_id = %s;", (emp_id,))
        shift = cur.fetchone()
        assert shift is not None
        assert shift[0] == now_in
        assert shift[1] == now_out
        assert shift[2] == "PENDING"