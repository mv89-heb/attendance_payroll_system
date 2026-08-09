import re
import logging
from typing import List, Dict, Any
from decimal import Decimal
from app.utils.money import to_decimal, round_money

logger = logging.getLogger(__name__)

class OCRService:

    @staticmethod
    def parse_payslip_text(text: str) -> List[Dict[str, Any]]:
        """
        מנתח טקסט גולמי שהופק מתלוש שכר באמצעות Heuristic Regex Engine.
        מזהה רכיבי בסיס, תוספות וניכויים ומחזיר מבנה נתונים מנורמל עם ציוני ביטחון.
        """
        extracted = []
        
        # תבניות Regex ייעודיות לאיתור ערכים בעברית
        patterns = {
            "שכר יסוד": (r"(?:שכר יסוד|משכורת יסוד|שכר בסיס)[\s:-]+([\d\.,]+)", "BASE_SALARY"),
            "החזר נסיעות": (r"(?:נסיעות|החזר נסיעות|קצובת נסיעה)[\s:-]+([\d\.,]+)", "ADDITION"),
            "פנסיה": (r"(?:פנסיה|הפרשת פנסיה|ניכוי פנסיה)[\s:-]+([\d\.,]+)", "DEDUCTION"),
            "ברוטו": (r"(?:סה\"כ ברוטו|סהכ ברוטו|ברוטו לתשלום)[\s:-]+([\d\.,]+)", "STATUTORY"),
            "נטו": (r"(?:נטו לתשלום|סה\"כ נטו|נטו)[\s:-]+([\d\.,]+)", "STATUTORY")
        }

        # עיבוד שורות התלוש
        lines = text.split("\n")
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            for name, (regex, category) in patterns.items():
                match = re.search(regex, line_clean)
                if match:
                    val_str = match.group(1).replace(",", "")
                    try:
                        amount = round_money(to_decimal(val_str))
                        extracted.append({
                            "original_name": name,
                            "category": category,
                            "quantity": Decimal("1.00"),
                            "unit_rate": amount,
                            "amount": amount,
                            "confidence": Decimal("95.00")
                        })
                    except Exception as e:
                        logger.error(f"Error parsing amount '{val_str}' on line: {line_clean}. Error: {e}")

        return extracted