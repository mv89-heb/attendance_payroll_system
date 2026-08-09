import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from app.db import db
from app.utils.time import calculate_work_date

logger = logging.getLogger(__name__)

class AttendanceService:
    
    @staticmethod
    def record_kiosk_punch(employee_id: int, domain_id: int, punch_type: str, punch_time_utc: datetime) -> Dict[str, Any]:
        work_date = calculate_work_date(punch_time_utc)
        
        with db.cursor() as cur:
            cur.execute("""
                SELECT punch_type, punched_at 
                FROM attendance_punches 
                WHERE employee_id = %s 
                ORDER BY punched_at DESC LIMIT 1;
            """, (employee_id,))
            last_punch = cur.fetchone()
            
            integrity_status = "VALID"
            if last_punch:
                last_type, last_time = last_punch
                time_diff = punch_time_utc - last_time
                
                if time_diff < timedelta(seconds=120) and last_type == punch_type:
                    logger.warning(f"Double-click punch rejected for employee ID {employee_id}.")
                    return {
                        "status": "REJECTED",
                        "reason": "DOUBLE_CLICK_PREVENTION",
                        "time_since_last": time_diff.total_seconds()
                    }
                
                if last_type == punch_type:
                    integrity_status = "MISMATCHED_PUNCH"
            elif punch_type == "OUT":
                integrity_status = "MISMATCHED_PUNCH"

            cur.execute("""
                INSERT INTO attendance_punches (employee_id, domain_id, punch_type, punched_at, work_date, source, integrity_status)
                VALUES (%s, %s, %s, %s, %s, 'KIOSK', %s) RETURNING id;
            """, (employee_id, domain_id, punch_type, punch_time_utc, work_date, integrity_status))
            
            punch_id = cur.fetchone()[0]
            
            return {
                "status": "ACCEPTED",
                "punch_id": punch_id,
                "integrity_status": integrity_status,
                "work_date": work_date.isoformat()
            }