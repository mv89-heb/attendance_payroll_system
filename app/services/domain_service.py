import logging
from typing import List, Dict, Any, Optional
from app.db import db

logger = logging.getLogger(__name__)

class DomainService:

    @staticmethod
    def create_domain(name: str, code: str) -> int:
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO work_domains (name, code)
                VALUES (%s, %s) RETURNING id;
            """, (name, code))
            return cur.fetchone()[0]

    @staticmethod
    def update_domain(domain_id: int, name: str, code: str, active: bool):
        with db.cursor() as cur:
            cur.execute("""
                UPDATE work_domains
                SET name = %s, code = %s, active = %s
                WHERE id = %s;
            """, (name, code, active, domain_id))

    @staticmethod
    def get_domain(domain_id: int) -> Optional[Dict[str, Any]]:
        with db.cursor() as cur:
            cur.execute("SELECT id, name, code, active FROM work_domains WHERE id = %s;", (domain_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {"id": row[0], "name": row[1], "code": row[2], "active": row[3]}

    @staticmethod
    def list_domains(active_only: bool = False) -> List[Dict[str, Any]]:
        """מחזיר רשימת תחומים מלאה כולל כמות העובדים הפעילים המשוייכים לכל תחום."""
        sql = """
            SELECT wd.id, wd.name, wd.code, wd.active, COUNT(ed.id) as employee_count
            FROM work_domains wd
            LEFT JOIN employee_domains ed ON ed.domain_id = wd.id
            WHERE 1=1
        """
        if active_only:
            sql += " AND wd.active = TRUE"
        sql += " GROUP BY wd.id, wd.name, wd.code, wd.active ORDER BY wd.name ASC;"
        
        with db.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [{
                "id": r[0],
                "name": r[1],
                "code": r[2],
                "active": r[3],
                "employee_count": r[4]
            } for r in rows]
