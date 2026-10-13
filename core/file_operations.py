import os
import shutil
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


class SafeFileOps:
    """
    Handles file moves, copies, renames, and deletions safely across filesystems.
    Enforces collision rules, path validation, and transaction auditing.
    """

    @staticmethod
    def resolve_unique_path(destination: Path) -> Path:
        """
        Generates a non-conflicting path if the destination already exists.
        Example: file.txt -> file_1.txt -> file_2.txt
        """
        if not destination.exists():
            return destination

        parent = destination.parent
        stem = destination.stem
        suffix = destination.suffix
        counter = 1

        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def safe_move(
        source: Path,
        destination: Path,
        overwrite: bool = False,
        auto_rename: bool = True
    ) -> Tuple[bool, Path, str]:
        """
        Moves a file safely to a destination path. Handles cross-filesystem moves.

        Returns:
            Tuple[success: bool, actual_destination: Path, message: str]
        """
        try:
            source = source.resolve()
            if not source.exists():
                return False, destination, f"Source file does not exist: {source}"

            if not source.is_file() and not source.is_symlink():
                return False, destination, f"Source is not a regular file: {source}"

            target_dest = destination
            if target_dest.exists():
                if source.samefile(target_dest):
                    return True, target_dest, "Source and destination are identical file."

                if not overwrite:
                    if auto_rename:
                        target_dest = SafeFileOps.resolve_unique_path(target_dest)
                    else:
                        return False, destination, f"Destination already exists: {destination}"

            # Ensure parent directories exist
            target_dest.parent.mkdir(parents=True, exist_ok=True)

            # Perform atomic or cross-filesystem move
            shutil.move(str(source), str(target_dest))
            logger.info(f"Successfully moved file: {source} -> {target_dest}")
            return True, target_dest, f"Moved to {target_dest.name}"

        except PermissionError as pe:
            err_msg = f"Permission denied moving {source}: {pe}"
            logger.error(err_msg)
            return False, destination, err_msg
        except OSError as oe:
            err_msg = f"OS error during move operation: {oe}"
            logger.error(err_msg)
            return False, destination, err_msg
        except Exception as e:
            err_msg = f"Unexpected error moving file: {e}"
            logger.error(err_msg)
            return False, destination, err_msg

    @staticmethod
    def safe_rename(
        source: Path,
        new_name: str,
        overwrite: bool = False
    ) -> Tuple[bool, Path, str]:
        """
        Renames a file in its current directory.

        Returns:
            Tuple[success: bool, actual_destination: Path, message: str]
        """
        target_path = source.parent / new_name
        return SafeFileOps.safe_move(source, target_path, overwrite=overwrite, auto_rename=False)

    @staticmethod
    def safe_delete(source: Path) -> Tuple[bool, str]:
        """Deletes a file safely with error handling."""
        try:
            source = source.resolve()
            if not source.exists():
                return False, f"File does not exist: {source}"

            if source.is_dir():
                return False, f"Path is a directory, refusing to delete: {source}"

            source.unlink()
            logger.info(f"Successfully deleted file: {source}")
            return True, "File deleted successfully."
        except Exception as e:
            err_msg = f"Failed to delete file {source}: {e}"
            logger.error(err_msg)
            return False, err_msg

    @staticmethod
    def get_file_info(path: Path) -> Optional[Dict[str, Any]]:
        """Retrieves key metadata for a file safely."""
        try:
            stat = path.stat()
            return {
                "name": path.name,
                "path": str(path.resolve()),
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "is_symlink": path.is_symlink(),
            }
        except Exception as e:
            logger.warning(f"Failed to read file info for {path}: {e}")
            return None