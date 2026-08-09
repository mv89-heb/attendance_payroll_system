import os
import logging
from contextlib import contextmanager
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self._pool = None
        self._pid = None
        self._conninfo = None
        self._pool_config = {}

    def init_app(self, app):
        db_url = app.config["DATABASE_URL"]
        
        if "sslmode" not in db_url and app.config["FLASK_ENV"] == "production":
            if "?" in db_url:
                db_url += "&sslmode=require"
            else:
                db_url += "?sslmode=require"
        
        scheme = db_url.split("://")[0] if "://" in db_url else "none"
        host_present = "yes" if "@" in db_url or ("://" in db_url and "@" not in db_url) else "no"
        port = db_url.split(":")[-1].split("/")[0] if len(db_url.split(":")) > 2 else "default"
        ssl_present = "sslmode" in db_url
        
        logger.info("DATABASE_URL metadata analysis:")
        logger.info(f"DATABASE_URL present: True")
        logger.info(f"DATABASE_URL scheme: {scheme}")
        logger.info(f"DATABASE_URL host present: {host_present}")
        logger.info(f"DATABASE_URL port: {port}")
        logger.info(f"DATABASE_URL sslmode present: {ssl_present}")

        self._conninfo = db_url
        self._pool_config = {
            "min_size": app.config["DB_POOL_MIN"],
            "max_size": app.config["DB_POOL_MAX"],
            "timeout": app.config["DB_POOL_TIMEOUT"]
        }

    def _get_pool(self) -> ConnectionPool:
        current_pid = os.getpid()
        if self._pool is None or self._pid != current_pid:
            if self._pool is not None:
                try:
                    self._pool.close()
                except Exception:
                    pass
            
            logger.info(f"Initializing process-safe ConnectionPool for PID {current_pid}...")
            self._pool = ConnectionPool(
                conninfo=self._conninfo,
                min_size=self._pool_config["min_size"],
                max_size=self._pool_config["max_size"],
                timeout=self._pool_config["timeout"],
                open=True
            )
            self._pid = current_pid
        return self._pool

    def close(self):
        """סוגר בצורה יזומה ומפורשת את כל חיבורי ה-Pool וה-Threads המלווים."""
        if self._pool:
            logger.info("Closing database connection pool.")
            try:
                self._pool.close()
            except Exception as e:
                logger.error(f"Error closing connection pool: {e}")
            self._pool = None
            self._pid = None

    @contextmanager
    def connection(self):
        pool = self._get_pool()
        with pool.connection() as conn:
            yield conn

    @contextmanager
    def cursor(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                yield cur

db = Database()
