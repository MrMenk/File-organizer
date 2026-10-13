import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from storage.history_repository import HistoryRepository
from core.file_operations import SafeFileOps

logger = logging.getLogger(__name__)


class UndoManager:
    """
    Transaction-based undo engine.
    Reverses the last completed file operation batch recorded in the persistent database.
    """

    def __init__(self, history_repo: HistoryRepository):
        self.history_repo = history_repo

    def get_last_undoable_batch_info(self) -> Optional[Dict[str, Any]]:
        """Returns metadata about the most recent batch available to undo."""
        return self.history_repo.get_last_undoable_batch()

    def undo_last_operation(
        self,
        progress_callback=None
    ) -> Tuple[bool, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Reverses the most recent supported operation batch in reverse execution order.

        Returns:
            Tuple[
                success: bool,
                summary_message: str,
                restored_records: List[Dict],
                failed_records: List[Dict]
            ]
        """
        batch_info = self.history_repo.get_last_undoable_batch()
        if not batch_info:
            return False, "No undoable operations found in history.", [], []

        batch_id = batch_info["batch_id"]
        op_type = batch_info["operation_type"]
        records = self.history_repo.get_batch_records(batch_id)

        if not records:
            return False, f"No active records found for batch ID {batch_id}.", [], []

        restored = []
        failed = []
        total_records = len(records)

        for idx, rec in enumerate(records, start=1):
            current_path = Path(rec["destination_path"])
            original_path = Path(rec["source_path"])

            # Verify that the file to reverse currently exists at its destination
            if not current_path.exists():
                failed.append({
                    "id": rec["id"],
                    "source": str(current_path),
                    "destination": str(original_path),
                    "error": f"File no longer exists at destination path: {current_path}"
                })
                continue

            # Verify original location is not occupied by another file
            if original_path.exists() and not current_path.samefile(original_path):
                failed.append({
                    "id": rec["id"],
                    "source": str(current_path),
                    "destination": str(original_path),
                    "error": f"Original path is occupied by another file: {original_path}"
                })
                continue

            # Perform the reverse move/rename
            success, actual_dest, message = SafeFileOps.safe_move(
                source=current_path,
                destination=original_path,
                overwrite=False,
                auto_rename=False
            )

            if success:
                restored.append({
                    "id": rec["id"],
                    "source": str(current_path),
                    "destination": str(actual_dest)
                })
            else:
                failed.append({
                    "id": rec["id"],
                    "source": str(current_path),
                    "destination": str(original_path),
                    "error": message
                })

            if progress_callback:
                progress_callback(idx, total_records, current_path.name)

        # Mark batch as undone in database if at least one file was restored
        if restored:
            self.history_repo.mark_batch_as_undone(batch_id)

        summary = (
            f"Undo operation complete for batch '{batch_id}' ({op_type}). "
            f"Restored: {len(restored)}/{total_records}, Failed: {len(failed)}."
        )
        logger.info(summary)

        return True, summary, restored, failed