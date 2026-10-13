import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from storage.database import DatabaseManager
from cli import setup_cli_parser, handle_cli_commands


def setup_logging(base_dir: Path) -> Path:
    """Sets up application-wide file and console logging with automatic rotation."""
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "file_organizer.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logs_dir

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
    )

    # Rotating File Handler (Max 10 MB per file, keep up to 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler for CLI output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logs_dir


def main() -> None:
    """Application entry point for both CLI and GUI modes."""
    base_dir = Path(__file__).resolve().parent

    # Internal app directories to exclude from recursion & modification
    logs_dir = setup_logging(base_dir)
    storage_dir = base_dir / "storage"
    db_path = storage_dir / "organizer.db"

    app_internal_dirs = [base_dir, logs_dir, storage_dir]

    # Initialize SQLite Database & Schema
    db_manager = DatabaseManager(db_path)

    categories_config = base_dir / "config" / "categories.json"
    settings_config = base_dir / "config" / "settings.json"

    parser = setup_cli_parser()

    # Launch GUI if no CLI subcommand is provided
    if len(sys.argv) == 1:
        try:
            from gui.app import FileOrganizerGUI
            app = FileOrganizerGUI(
                db_manager=db_manager,
                categories_path=categories_config,
                settings_path=settings_config,
                app_dirs=app_internal_dirs
            )
            app.mainloop()
        except ImportError as e:
            logging.error(f"Tkinter visual framework unavailable: {e}")
            print("\n[ERROR] Tkinter GUI module not found. Run CLI subcommands using `--help`.")
            sys.exit(1)
    else:
        args = parser.parse_args()
        exit_code = handle_cli_commands(
            args=args,
            db_manager=db_manager,
            categories_path=categories_config,
            settings_path=settings_config,
            app_dirs=app_internal_dirs
        )
        sys.exit(exit_code)


if __name__ == "__main__":
    main()