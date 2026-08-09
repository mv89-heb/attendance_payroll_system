from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo
from flask import current_app

def get_tz() -> ZoneInfo:
    try:
        # ניסיון למשוך את אזור הזמן מתוך קונפיגורציית Flask פעילה
        tz_name = current_app.config["SYSTEM_TIMEZONE"]
    except RuntimeError:
        # Fallback בטוח כאשר פועלים מחוץ לקונטקסט של Flask (כמו בהרצת בדיקות יחידה)
        tz_name = "Asia/Jerusalem"
    return ZoneInfo(tz_name)

def now_utc() -> datetime:
    return datetime.now(ZoneInfo("UTC"))

def utc_to_local(utc_dt: datetime) -> datetime:
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
    return utc_dt.astimezone(get_tz())

def local_to_utc(local_dt: datetime) -> datetime:
    if local_dt.tzinfo is None:
        local_dt = local_dt.replace(tzinfo=get_tz())
    return local_dt.astimezone(ZoneInfo("UTC"))

def calculate_work_date(punch_time_utc: datetime) -> date:
    local_time = utc_to_local(punch_time_utc)
    if local_time.time() < time(4, 0):
        return (local_time - timedelta(days=1)).date()
    return local_time.date()