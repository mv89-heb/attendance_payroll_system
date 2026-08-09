import logging
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from app.db import db

logger = logging.getLogger(__name__)

class ShiftService:

    @staticmethod
    def process_raw_punches_to_shifts(employee_id: int, target_date: date):
        """
        סורק את כל החתמות ה-IN וה-OUT הגולמיות של העובד ביום עבודה מוגדר,
        ומבצע צימוד (Pairing) שלהן למשמרות סגורות תחת ה-Work Date.
        """
        with db.cursor() as cur:
            cur.execute("""
                SELECT id, domain_id, punch_type, punched_at 
                FROM attendance_punches
                WHERE employee_id = %s AND work_date = %s
                ORDER BY punched_at ASC;
            """, (employee_id, target_date))
            punches = cur.fetchall()

            if not punches:
                return

            active_in_punch = None
            for p_id, domain_id, p_type, p_time in punches:
                if p_type == "IN":
                    active_in_punch = (domain_id, p_time)
                elif p_type == "OUT" and active_in_punch:
                    in_domain_id, in_time = active_in_punch
                    # יצירת משמרת סגורה מנורמלת
                    cur.execute("""
                        INSERT INTO shifts (employee_id, domain_id, shift_date, start_time, end_time, break_minutes, status, source)
                        VALUES (%s, %s, %s, %s, %s, 0, 'PENDING', 'AUTO')
                        ON CONFLICT DO NOTHING;
                    """, (employee_id, in_domain_id, target_date, in_time, p_time))
                    active_in_punch = None
            db.connection() # Trigger auto-commit

    @staticmethod
    def approve_shift(shift_id: int, approved_by_user_id: int):
        """מאשר משמרת על מנת להפוך את השעות למאושרות לחישוב שכר (Approved hours)."""
        with db.cursor() as cur:
            cur.execute("""
                UPDATE shifts 
                SET status = 'APPROVED', approved_by_user_id = %s, approved_at = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (approved_by_user_id, shift_id))
