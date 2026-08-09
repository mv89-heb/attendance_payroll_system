import os
import pytest
from app import create_app
from app.db import db
from migrations.runner import run_migrations

@pytest.fixture(scope="session")
def app():
    test_db_url = os.getenv("DATABASE_URL")
    if not test_db_url:
        pytest.skip("DATABASE_URL environment variable is required to execute Phase 0 tests.")

    _app = create_app()
    _app.config.update({
        "TESTING": True,
        "DATABASE_URL": test_db_url,
        "FLASK_ENV": "development"
    })

    with db.connection() as conn:
        run_migrations(conn)

    yield _app

    # Teardown: סגירת ה-Pool בצורה מפורשת לפני סגירת ה-Interpreter
    db.close()

@pytest.fixture(autouse=True)
def clean_db(app):
    """מבצע ניקוי ממוקד של טבלאות הנתונים הדינמיות לפני כל בדיקה בנפרד לבידוד מוחלט."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                TRUNCATE TABLE 
                    attendance_corrections,
                    attendance_punches,
                    shifts,
                    timesheet_entry_items,
                    timesheet_entries,
                    payroll_result_items,
                    payroll_results,
                    payroll_runs,
                    employee_deduction_components,
                    employee_pay_components,
                    employee_pay_rates,
                    employee_employment_terms,
                    employee_domains,
                    user_roles,
                    users,
                    employees,
                    work_domains,
                    payroll_periods
                CASCADE;
            """)
            conn.commit()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def db_conn(app):
    with db.connection() as conn:
        yield conn