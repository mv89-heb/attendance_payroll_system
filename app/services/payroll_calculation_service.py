import logging
import json
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import date
from app.db import db
from app.utils.money import to_decimal, round_money
from app.services.employment_service import EmploymentService

logger = logging.getLogger(__name__)

class PayrollCalculationService:

    @staticmethod
    def calculate_period_payroll(payroll_period_id: int, user_id: int) -> int:
        """
        מריץ חישוב שכר מלא לכל העובדים הפעילים עבור תקופת שכר מבוקשת.
        יוצר ריצת שכר (Payroll Run) ותוצאות מפורטות לכל עובד כולל Snapshot מתמטי.
        """
        with db.cursor() as cur:
            # 1. שליפת פרטי תקופת השכר
            cur.execute("""
                SELECT id, start_date, end_date, status FROM payroll_periods WHERE id = %s;
            """, (payroll_period_id,))
            period = cur.fetchone()
            if not period:
                raise ValueError("תקופת שכר לא נמצאה.")
            p_id, start_date, end_date, status = period

            if status == "LOCKED":
                raise ValueError("MIGRATION_LOCK_ERROR: תקופת השכר נעולה ולא ניתן לחשב אותה מחדש.")

            # 2. מחיקת ריצות שכר לא נעולות קודמות של אותה תקופה כדי לשמור על בסיס נתונים נקי
            cur.execute("SELECT id FROM payroll_runs WHERE payroll_period_id = %s AND status != 'LOCKED';", (p_id,))
            old_runs = [r[0] for r in cur.fetchall()]
            for old_run_id in old_runs:
                cur.execute("DELETE FROM payroll_results WHERE payroll_run_id = %s;", (old_run_id,))
                cur.execute("DELETE FROM payroll_runs WHERE id = %s;", (old_run_id,))

            # 3. יצירת ריצת שכר חדשה (DRAFT)
            cur.execute("""
                INSERT INTO payroll_runs (payroll_period_id, version, status, created_by_user_id)
                VALUES (%s, 1, 'DRAFT', %s) RETURNING id;
            """, (p_id, user_id))
            run_id = cur.fetchone()[0]

            # 4. שליפת כל העובדים הפעילים
            cur.execute("SELECT id, first_name, last_name, employee_number FROM employees WHERE active = TRUE;")
            employees = cur.fetchall()

            for emp_id, first_name, last_name, emp_num in employees:
                # א. שליפת תנאי העסקה פעילים לתקופה זו (לפי תאריך סיום התקופה)
                terms = EmploymentService.get_active_term_for_date(emp_id, end_date)
                if not terms:
                    logger.warning(f"No active employment terms found for employee ID {emp_id}. Skipping calculation.")
                    continue

                emp_type = terms["employment_type"]
                base_salary = to_decimal(terms["base_salary"])
                hourly_rate = to_decimal(terms["hourly_rate"])
                travel_rate = to_decimal(terms["travel_rate"])

                # ב. שליפת משמרות מאושרות (APPROVED) בלבד וסיכום שעות וימי עבודה ייחודיים
                cur.execute("""
                    SELECT start_time, end_time, break_minutes, shift_date
                    FROM shifts
                    WHERE employee_id = %s
                      AND shift_date BETWEEN %s AND %s
                      AND status = 'APPROVED';
                """, (emp_id, start_date, end_date))
                shifts = cur.fetchall()

                total_hours = Decimal("0.0000")
                unique_work_days = set()

                for s_start, s_end, s_break, s_date in shifts:
                    duration = s_end - s_start
                    hours = Decimal(str(duration.total_seconds() / 3600.0)) - (Decimal(str(s_break)) / Decimal("60.0"))
                    if hours < 0:
                        hours = Decimal("0.0000")
                    total_hours += hours
                    unique_work_days.add(s_date)

                work_days_count = len(unique_work_days)

                # ג. חישוב ברוטו יסוד
                if emp_type == "HOURLY":
                    base_pay = round_money(total_hours * hourly_rate)
                else: # SALARIED
                    base_pay = round_money(base_salary)

                # ד. חישוב החזר נסיעות לפי ימי עבודה בפועל
                travel_pay = round_money(Decimal(str(work_days_count)) * travel_rate)

                # ה. שליפת תוספות שכר גנריות קבועות לעובד
                cur.execute("""
                    SELECT epc.value, epc.calculation_type, pc.name
                    FROM employee_pay_components epc
                    JOIN pay_components pc ON epc.component_id = pc.id
                    WHERE epc.employee_id = %s AND pc.active = TRUE
                      AND epc.valid_from <= %s AND (epc.valid_until >= %s OR epc.valid_until IS NULL);
                """, (emp_id, end_date, start_date))
                additions = cur.fetchall()

                additions_total = Decimal("0.0000")
                additions_items = []
                for val, calc_type, name in additions:
                    val_dec = to_decimal(val)
                    if calc_type == "FIXED":
                        amt = round_money(val_dec)
                    elif calc_type == "PER_SHIFT":
                        amt = round_money(val_dec * Decimal(str(len(shifts))))
                    else:
                        amt = Decimal("0.0000")
                    additions_total += amt
                    additions_items.append({"name": name, "amount": str(amt), "type": calc_type})

                # ו. שליפת ניכויי שכר גנריים קבועים לעובד
                cur.execute("""
                    SELECT edc.value, edc.calculation_type, dc.name
                    FROM employee_deduction_components edc
                    JOIN deduction_components dc ON edc.deduction_id = dc.id
                    WHERE edc.employee_id = %s AND dc.active = TRUE
                      AND edc.valid_from <= %s AND (edc.valid_until >= %s OR edc.valid_until IS NULL);
                """, (emp_id, end_date, start_date))
                deductions = cur.fetchall()

                deductions_total = Decimal("0.0000")
                deductions_items = []
                for val, calc_type, name in deductions:
                    val_dec = to_decimal(val)
                    if calc_type == "FIXED":
                        amt = round_money(val_dec)
                    elif calc_type == "PERCENTAGE_OF_BASE":
                        amt = round_money(base_pay * (val_dec / Decimal("100.0")))
                    else:
                        amt = Decimal("0.0000")
                    deductions_total += amt
                    deductions_items.append({"name": name, "amount": str(amt), "type": calc_type})

                # ז. סיכומי ברוטו ונטו סופיים
                total_gross = base_pay + travel_pay + additions_total
                total_net = total_gross - deductions_total

                # ח. יצירת ה-Calculations Snapshot להסבר מתמטי מלא ב-UI (Explainable Calculation)
                snapshot = {
                    "employee_details": {
                        "name": f"{first_name} {last_name}",
                        "number": emp_num
                    },
                    "employment_type": emp_type,
                    "calculation_steps": [
                        {
                            "step": "שכר יסוד מחושב",
                            "formula": f"{total_hours:.2f} שעות עבודה X ₪{hourly_rate:.2f}" if emp_type == "HOURLY" else "שכר גלובלי חודשי קבוע",
                            "result": str(base_pay)
                        },
                        {
                            "step": "החזר נסיעות",
                            "formula": f"{work_days_count} ימי עבודה בפועל X ₪{travel_rate:.2f}",
                            "result": str(travel_pay)
                        }
                    ],
                    "additions_breakdown": additions_items,
                    "deductions_breakdown": deductions_items
                }

                # ט. שמירת תוצאת החישוב הראשית לעובד
                cur.execute("""
                    INSERT INTO payroll_results (payroll_run_id, employee_id, total_gross, total_deductions, total_net, calculations_snapshot)
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
                """, (run_id, emp_id, total_gross, deductions_total, total_net, json.dumps(snapshot)))
                result_id = cur.fetchone()[0]

                # י. רישום פריטי תוצאה מנורמלים לעובד (payroll_result_items)
                # שכר יסוד
                cur.execute("""
                    INSERT INTO payroll_result_items (payroll_result_id, component_type, name, quantity, unit, rate, amount)
                    VALUES (%s, 'BASE_PAY', 'שכר יסוד', %s, %s, %s, %s);
                """, (result_id, total_hours if emp_type == "HOURLY" else Decimal("1.00"),
                      "HOURS" if emp_type == "HOURLY" else "MONTHLY", hourly_rate if emp_type == "HOURLY" else base_pay, base_pay))

                # נסיעות
                cur.execute("""
                    INSERT INTO payroll_result_items (payroll_result_id, component_type, name, quantity, unit, rate, amount)
                    VALUES (%s, 'ADDITION', 'החזר נסיעות', %s, 'DAYS', %s, %s);
                """, (result_id, Decimal(str(work_days_count)), travel_rate, travel_pay))

                # תוספות גנריות
                for add_item in additions_items:
                    cur.execute("""
                        INSERT INTO payroll_result_items (payroll_result_id, component_type, name, quantity, unit, rate, amount)
                        VALUES (%s, 'ADDITION', %s, 1.00, 'FIXED', %s, %s);
                    """, (result_id, add_item["name"], to_decimal(add_item["amount"]), to_decimal(add_item["amount"])))

                # ניכויים גנריים
                for ded_item in deductions_items:
                    cur.execute("""
                        INSERT INTO payroll_result_items (payroll_result_id, component_type, name, quantity, unit, rate, amount)
                        VALUES (%s, 'DEDUCTION', %s, 1.00, 'FIXED', %s, %s);
                    """, (result_id, ded_item["name"], to_decimal(ded_item["amount"]), to_decimal(ded_item["amount"])))

            # 5. עדכון סטטוס ריצת השכר ל-APPROVED
            cur.execute("UPDATE payroll_runs SET status = 'APPROVED' WHERE id = %s;", (run_id,))
            db.connection() # Auto-commit
            return run_id
