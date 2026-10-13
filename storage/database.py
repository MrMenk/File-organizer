import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database initialization, connection management,
    and schema migrations for persistent operation logging and undo metadata.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_db_dir()
        self.init_database()

    def _ensure_db_dir(self) -> None:
        """Ensures the parent directory for the database file exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Creates and returns a SQLite database connection with row factory enabled."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency and durability
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def init_database(self) -> None:
        """Creates required tables if they do not exist."""
        schema = """
        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_path TEXT NOT NULL,
            destination_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            status TEXT NOT NULL,
            error_message TEXT,
            is_undone INTEGER DEFAULT 0,
            undone_at DATETIME
        );

        CREATE INDEX IF NOT EXISTS idx_batch_id ON operations(batch_id);
        CREATE INDEX IF NOT EXISTS idx_operation_type ON operations(operation_type);
        CREATE INDEX IF NOT EXISTS idx_status ON operations(status);
        CREATE INDEX IF NOT EXISTS idx_timestamp ON operations(timestamp);
        """
        try:
            with self.get_connection() as conn:
                conn.executescript(schema)
                conn.commit()
            logger.info(f"Database initialized successfully at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise