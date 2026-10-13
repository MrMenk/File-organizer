import argparse
import sys
import logging
from pathlib import Path
from typing import List, Optional

from storage.database import DatabaseManager
from storage.history_repository import HistoryRepository
from core.validators import PathValidator
from core.organizer import FileOrganizer
from core.duplicate_detector import DuplicateDetector
from core.batch_renamer import BatchRenamer
from core.undo_manager import UndoManager

logger = logging.getLogger(__name__)


def setup_cli_parser() -> argparse.ArgumentParser:
    """Configures argument parser and command sub-commands for the CLI."""
    parser = argparse.ArgumentParser(
        description="File Organizer Tool - Modular Python File Management CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: organize
    org_parser = subparsers.add_parser("organize", help="Automatically organize files into category folders.")
    org_parser.add_argument("--path", required=True, type=str, help="Target directory path to organize.")
    org_parser.add_argument("--dry-run", action="store_true", help="Preview planned changes without modifying files.")
    org_parser.add_argument("--recursive", action="store_true", help="Scan subdirectories recursively.")

    # Command: duplicates
    dup_parser = subparsers.add_parser("duplicates", help="Scan for duplicate files using SHA-256 hashes.")
    dup_parser.add_argument("--path", required=True, type=str, help="Target directory path to scan.")
    dup_parser.add_argument("--recursive", action="store_true", help="Scan subdirectories recursively.")

    # Command: rename
    ren_parser = subparsers.add_parser("rename", help="Batch rename files using pattern templates.")
    ren_parser.add_argument("--path", required=True, type=str, help="Target directory containing files to rename.")
    ren_parser.add_argument("--pattern", required=True, type=str, help="Rename template, e.g., 'Vacation_{counter:03d}' or '{original}_backup'")
    ren_parser.add_argument("--dry-run", action="store_true", help="Preview new names without renaming files.")

    # Command: history
    subparsers.add_parser("history", help="Display operation audit history.")

    # Command: undo
    subparsers.add_parser("undo", help="Revert the most recent operation batch.")

    return parser


def handle_cli_commands(
    args: argparse.Namespace,
    db_manager: DatabaseManager,
    categories_path: Path,
    settings_path: Path,
    app_dirs: Optional[List[Path]] = None
) -> int:
    """Executes the appropriate business logic depending on parsed CLI arguments."""
    history_repo = HistoryRepository(db_manager)
    undo_manager = UndoManager(history_repo)

    if args.command == "organize":
        target_path = Path(args.path).resolve()
        valid, err_msg = PathValidator.validate_target_directory(target_path, app_dirs)
        if not valid:
            print(f"[ERROR] {err_msg}")
            return 1

        organizer = FileOrganizer.load_from_config(categories_path, settings_path, recursive_override=args.recursive)
        preview_plan = organizer.generate_preview(target_path, app_dirs=app_dirs)

        print(f"Found {len(preview_plan)} file(s) to process in '{target_path}'.")

        if args.dry_run:
            print("\n--- DRY-RUN PREVIEW ---")
            for item in preview_plan:
                conflict_flag = " [CONFLICT -> AUTO-RENAME]" if item["has_conflict"] else ""
                print(f"  [MOVE] {item['source'].name} -> {item['category']}/{item['proposed_destination'].name}{conflict_flag}")
            print("\nDry-run finished. No files were modified.")
            return 0

        succ, fail = organizer.execute_organization(target_path, preview_plan=preview_plan, app_dirs=app_dirs)
        batch_id = history_repo.generate_batch_id()
        history_repo.record_batch_operations(batch_id, "ORGANIZE", succ, fail)

        print(f"\n[SUCCESS] Successfully moved {len(succ)} file(s).")
        if fail:
            print(f"[WARNING] Failed to move {len(fail)} file(s). Check logs for details.")
        return 0

    elif args.command == "duplicates":
        target_path = Path(args.path).resolve()
        valid, err_msg = PathValidator.validate_target_directory(target_path, app_dirs)
        if not valid:
            print(f"[ERROR] {err_msg}")
            return 1

        detector = DuplicateDetector()
        print(f"Scanning for duplicate files in '{target_path}'...")
        groups = detector.scan_directory(target_path, recursive=args.recursive, app_dirs=app_dirs)

        if not groups:
            print("No duplicate files found.")
            return 0

        print(f"\nFound {len(groups)} duplicate group(s):\n")
        for i, grp in enumerate(groups, start=1):
            size_mb = grp['size'] / (1024 * 1024)
            print(f"Group #{i} [SHA-256: {grp['hash'][:16]}...] ({size_mb:.2f} MB):")
            for f in grp['files']:
                print(f"  • {f['path']}")
            print()
        return 0

    elif args.command == "rename":
        target_path = Path(args.path).resolve()
        valid, err_msg = PathValidator.validate_target_directory(target_path, app_dirs)
        if not valid:
            print(f"[ERROR] {err_msg}")
            return 1

        files = [p for p in target_path.iterdir() if p.is_file() and not p.is_symlink()]
        # Translate CLI pattern to template syntax
        template = args.pattern.replace("{counter:03d}", "{counter}")
        plan = BatchRenamer.generate_preview(files, custom_template=template)

        conflicts = [item for item in plan if item["has_conflict"]]

        if args.dry_run:
            print("\n--- BATCH RENAME PREVIEW ---")
            for item in plan:
                status = f" [CONFLICT: {item['conflict_reason']}]" if item["has_conflict"] else " [OK]"
                print(f"  {item['old_name']}  ==>  {item['new_name']}{status}")
            print(f"\nDry-run complete. Total files: {len(plan)}, Conflicts: {len(conflicts)}")
            return 0

        if conflicts:
            print(f"[ERROR] Cannot rename. {len(conflicts)} conflict(s) detected. Run with --dry-run to inspect.")
            return 1

        succ, fail = BatchRenamer.execute_renaming(plan)
        batch_id = history_repo.generate_batch_id()
        history_repo.record_batch_operations(batch_id, "RENAME", succ, fail)

        print(f"\n[SUCCESS] Successfully renamed {len(succ)} file(s).")
        if fail:
            print(f"[WARNING] Failed to rename {len(fail)} file(s).")
        return 0

    elif args.command == "history":
        records = history_repo.fetch_history(limit=50)
        if not records:
            print("No operation history recorded.")
            return 0

        print(f"{'ID':<6} {'Timestamp':<20} {'Type':<12} {'Status':<10} {'Source Path'}")
        print("-" * 80)
        for r in records:
            print(f"{r['id']:<6} {r['timestamp']:<20} {r['operation_type']:<12} {r['status']:<10} {r['source_path']}")
        return 0

    elif args.command == "undo":
        batch_info = undo_manager.get_last_undoable_batch_info()
        if not batch_info:
            print("No operations available to undo.")
            return 0

        print(f"Undoing batch '{batch_info['batch_id']}' ({batch_info['operation_type']}) with {batch_info['record_count']} record(s)...")
        ok, summary, restored, failed = undo_manager.undo_last_operation()
        print(f"Result: {summary}")
        return 0 if ok else 1

    return 0