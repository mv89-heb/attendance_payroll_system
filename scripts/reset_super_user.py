import os
import sys
from getpass import getpass

import psycopg
from werkzeug.security import generate_password_hash


USERNAME = "super_user"


def main():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("ERROR: DATABASE_URL is not set.")
        print()
        print("Set DATABASE_URL in the current PowerShell session and run again.")
        sys.exit(1)

    password = getpass(f"Enter new password for '{USERNAME}': ")
    confirm = getpass("Confirm new password: ")

    if not password:
        print("ERROR: Password cannot be empty.")
        sys.exit(1)

    if password != confirm:
        print("ERROR: Passwords do not match.")
        sys.exit(1)

    password_hash = generate_password_hash(password, method="scrypt")

    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET password_hash = %s
                    WHERE username = %s
                    RETURNING id, username;
                    """,
                    (password_hash, USERNAME),
                )

                user = cur.fetchone()

                if user is None:
                    conn.rollback()
                    print(f"ERROR: User '{USERNAME}' was not found.")
                    sys.exit(1)

                conn.commit()

                print()
                print(f"SUCCESS: Password reset for '{user[1]}'.")
                print("Only password_hash was changed.")

    except Exception as exc:
        print()
        print(f"ERROR: Database operation failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()