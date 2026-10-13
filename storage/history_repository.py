import sqlite3
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from storage.database import DatabaseManager

logger = logging.getLogger(__name__)


class HistoryRepository:
    """
    Data access layer for reading, writing, and filtering operation history
    and transaction metadata in SQLite.
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    @staticmethod
    def generate_batch_id() -> str:
        """Generates a unique identifier for grouping operations into atomic batches."""
        return str(uuid.uuid4())

    def record_operation(
        self,
        batch_id: str,
        operation_type: str,
        source_path: str,
        destination_path: str,
        status: str,
        file_size: int = 0,
        error_message: Optional[str] = None
    ) -> int:
        """Records an individual file operation entry in the database."""
        query = """
        INSERT INTO operations (
            batch_id, operation_type, source_path, destination_path,
            file_size, status, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    query,
                    (
                        batch_id,
                        operation_type,
                        source_path,
                        destination_path,
                        file_size,
                        status,
                        error_message
                    )
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Failed to record operation to history: {e}")
            return -1

    def record_batch_operations(
        self,
        batch_id: str,
        operation_type: str,
        successful_ops: List[Dict[str, Any]],
        failed_ops: List[Dict[str, Any]]
    ) -> None:
        """Records all successful and failed operations in a single batch transaction."""
        query = """
        INSERT INTO operations (
            batch_id, operation_type, source_path, destination_path,
            file_size, status, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        records = []
        for op in successful_ops:
            records.append((
                batch_id,
                operation_type,
                op.get("source", ""),
                op.get("destination", ""),
                op.get("file_size", 0),
                "SUCCESS",
                None
            ))

        for op in failed_ops:
            records.append((
                batch_id,
                operation_type,
                op.get("source", ""),
                op.get("destination", ""),
                0,
                "FAILED",
                op.get("error", "Unknown error")
            ))

        if not records:
            return

        try:
            with self.db.get_connection() as conn:
                conn.executemany(query, records)
                conn.commit()
            logger.info(f"Recorded batch {batch_id} with {len(records)} entries.")
        except sqlite3.Error as e:
            logger.error(f"Failed to record batch operations: {e}")

    def get_last_undoable_batch(self) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent batch ID and operation details that have not been undone."""
        query = """
        SELECT batch_id, operation_type, COUNT(*) as record_count, MIN(timestamp) as batch_time
        FROM operations
        WHERE status = 'SUCCESS' AND is_undone = 0
        GROUP BY batch_id, operation_type
        ORDER BY id DESC
        LIMIT 1
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                row = cursor.execute(query).fetchone()
                if row:
                    return dict(row)
                return None
        except sqlite3.Error as e:
            logger.error(f"Error fetching last undoable batch: {e}")
            return None

    def get_batch_records(self, batch_id: str) -> List[Dict[str, Any]]:
        """Retrieves all operation records belonging to a specific batch ID."""
        query = """
        SELECT * FROM operations
        WHERE batch_id = ? AND status = 'SUCCESS' AND is_undone = 0
        ORDER BY id DESC
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                rows = cursor.execute(query, (batch_id,)).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error fetching records for batch {batch_id}: {e}")
            return []

    def mark_batch_as_undone(self, batch_id: str) -> bool:
        """Marks all records in a batch as undone."""
        query = """
        UPDATE operations
        SET is_undone = 1, undone_at = CURRENT_TIMESTAMP
        WHERE batch_id = ?
        """
        try:
            with self.db.get_connection() as conn:
                conn.execute(query, (batch_id,))
                conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to mark batch {batch_id} as undone: {e}")
            return False

    def fetch_history(
        self,
        operation_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Retrieves historical operation records with optional filtering."""
        query = "SELECT * FROM operations WHERE 1=1"
        params = []

        if operation_type:
            query += " AND operation_type = ?"
            params.append(operation_type)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                rows = cursor.execute(query, params).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch operation history: {e}")
            return []