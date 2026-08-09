import os
import sys
import psycopg

print("==========================================")
print("      DIAGNOSTIC CONNECTION TESTER        ")
print("==========================================")

url = os.getenv("DATABASE_URL")
if not url:
    print("Error: DATABASE_URL is not set.")
    sys.exit(1)

# אילוץ SSLmode ידני בייצור
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
            sys.exit(0)
except Exception as e:
    print(f"✗ Connection failed: {e}")
    sys.exit(1)