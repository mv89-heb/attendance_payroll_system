import os
import sys
import psycopg

def main():
    print("==========================================")
    print("      DIAGNOSTIC CONNECTION TESTER        ")
    print("==========================================")

    # טעינה יחסית של קובץ ה-.env מתיקיית השורש
    try:
        from dotenv import load_dotenv
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        env_path = os.path.join(project_root, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)
            print("Successfully loaded configuration from .env")
        else:
            print(".env file not found at project root; relying on OS variables.")
    except ImportError:
        print("python-dotenv not installed; relying on OS variables.")

    url = os.getenv("DATABASE_URL")
    if not url:
        print("Error: DATABASE_URL is not set.")
        sys.exit(1)

    # אילוץ SSLmode בייצור
    if "sslmode" not in url:
        if "?" in url:
            url += "&sslmode=require"
        else:
            url += "?sslmode=require"

    print("DATABASE_URL metadata checked. Attempting direct connection...")
    try:
        with psycopg.connect(url, connect_timeout=15) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print("✓ Connection successful!")
                print(f"PostgreSQL Version: {version}")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
