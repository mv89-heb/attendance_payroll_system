import logging
from datetime import date
from app.db import db

logger = logging.getLogger(__name__)

class PayrollPeriodService:

    @staticmethod
    def create_period(year: int, month: int, start_date: date, end_date: date) -> int:
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO payroll_periods (year, month, start_date, end_date, status)
                VALUES (%s, %s, %s, %s, 'OPEN') RETURNING id;
            """, (year, month, start_date, end_date))
            return cur.fetchone()[0]

    @staticmethod
    def lock_period(period_id: int, locked_by_user_id: int):
        """נועל את תקופת השכר לחלוטין ברמת ה-Database."""
        with db.cursor() as cur:
            cur.execute("""
                UPDATE payroll_periods
                SET status = 'LOCKED', locked_at = CURRENT_TIMESTAMP, locked_by_user_id = %s
                WHERE id = %s;
            """, (locked_by_user_id, period_id))
