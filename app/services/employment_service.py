import logging
from typing import List, Dict, Any, Optional
from datetime import date
from decimal import Decimal
from app.db import db
from app.utils.money import to_decimal

logger = logging.getLogger(__name__)

class EmploymentService:

    @staticmethod
    def create_employment_term(
        employee_id: int,
        effective_from: date,
        effective_to: Optional[date],
        employment_type: str, # 'HOURLY', 'SALARIED'
        base_salary: Decimal,
        hourly_rate: Decimal,
        monthly_hours: Decimal,
        travel_rate: Decimal
    ) -> int:
        """יוצר תנאי העסקה היסטוריים לעובד."""
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO employee_employment_terms 
                (employee_id, effective_from, effective_to, employment_type, base_salary, hourly_rate, monthly_hours, travel_rate)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """, (employee_id, effective_from, effective_to, employment_type, 
                  to_decimal(base_salary), to_decimal(hourly_rate), to_decimal(monthly_hours), to_decimal(travel_rate)))
            return cur.fetchone()[0]

    @staticmethod
    def get_active_term_for_date(employee_id: int, target_date: date) -> Optional[Dict[str, Any]]:
        """שולף את תנאי ההעסקה שהיו בתוקף במועד העבודה המבוקש."""
        with db.cursor() as cur:
            cur.execute("""
                SELECT id, employee_id, effective_from, effective_to, employment_type, base_salary, hourly_rate, monthly_hours, travel_rate, active
                FROM employee_employment_terms
                WHERE employee_id = %s 
                  AND %s >= effective_from 
                  AND (%s <= effective_to OR effective_to IS NULL)
                ORDER BY effective_from DESC LIMIT 1;
            """, (employee_id, target_date, target_date))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "employee_id": row[1],
                "effective_from": row[2],
                "effective_to": row[3],
                "employment_type": row[4],
                "base_salary": row[5],
                "hourly_rate": row[6],
                "monthly_hours": row[7],
                "travel_rate": row[8],
                "active": row[9]
            }
