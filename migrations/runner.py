import os
import sys
import logging
from psycopg import Connection

# הגדרת לוגר
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# טעינה דינמית ואופציונלית של .env מתיקיית השורש של הפרויקט
try:
    from dotenv import load_dotenv
    # קבלת הנתיב המוחלט של תיקיית המיגרציות
    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    # עלייה שלב אחד למעלה לתיקיית השורש של הפרויקט
    project_root = os.path.dirname(migrations_dir)
    env_path = os.path.join(project_root, ".env")
    
    if os.path.exists(env_path):
        # override=False מבטיח שמשתני סביבה קיימים במערכת (כמו ב-Render) לא יידרסו
        load_dotenv(env_path, override=False)
        logger.info("Successfully loaded environment configuration from .env")
    else:
        logger.info(".env file not found at project root; relying on OS environment variables.")
except ImportError:
    logger.info("python-dotenv module is not installed; relying on OS environment variables.")

def run_migrations(conn: Connection):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS migration_history (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
        """)
        conn.commit()

    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    sql_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])

    for sql_file in sql_files:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM migration_history WHERE migration_name = %s", (sql_file,))
            if cur.fetchone():
                continue

            logger.info(f"Applying migration: {sql_file}")
            file_path = os.path.join(migrations_dir, sql_file)
            with open(file_path, "r", encoding="utf-8") as f:
                sql_content = f.read()

            try:
                cur.execute(sql_content)
                cur.execute("INSERT INTO migration_history (migration_name) VALUES (%s)", (sql_file,))
                conn.commit()
                logger.info(f"Successfully applied: {sql_file}")
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to apply migration {sql_file}: {e}")
                raise e

if __name__ == "__main__":
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable missing.")
        sys.exit(1)

    import psycopg
    try:
        with psycopg.connect(db_url) as conn:
            run_migrations(conn)
    except Exception as e:
        logger.error(f"Migration runner exited with error: {e}")
        sys.exit(1)