import os
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "prod-security-fallback-key-3298-x")
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL must be specified in the environment variables.")
        
    if "sslmode" not in DATABASE_URL and FLASK_ENV == "production":
        if "?" in DATABASE_URL:
            DATABASE_URL += "&sslmode=require"
        else:
            DATABASE_URL += "?sslmode=require"

    DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "2"))
    DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))
    DB_POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "5.0"))

    SYSTEM_TIMEZONE = "Asia/Jerusalem"
    RECONCILIATION_TOLERANCE = Decimal(os.getenv("RECONCILIATION_TOLERANCE", "1.00"))
    
    KIOSK_MAX_ATTEMPTS = int(os.getenv("KIOSK_MAX_ATTEMPTS", "5"))
    KIOSK_LOCKOUT_MINUTES = int(os.getenv("KIOSK_LOCKOUT_MINUTES", "15"))
