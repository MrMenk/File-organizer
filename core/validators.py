import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional


class PathValidator:
    """Provides path validation, safety checks, and system directory exclusions."""

    # Standard critical system paths by platform
    SYSTEM_PATHS_WINDOWS = [
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
    ]

    SYSTEM_PATHS_POSIX = [
        "/bin",
        "/boot",
        "/dev",
        "/etc",
        "/lib",
        "/lib64",
        "/proc",
        "/root",
        "/run",
        "/sbin",
        "/sys",
        "/usr",
        "/var",
    ]

    INVALID_FILENAME_CHARS = r'[\\/*?:"<>|]'

    @classmethod
    def get_system_directories(cls, extra_protected: Optional[List[str]] = None) -> List[Path]:
        """Returns a list of resolved Path objects for protected system directories."""
        system_paths = []
        raw_paths = cls.SYSTEM_PATHS_WINDOWS if sys.platform.startswith("win") else cls.SYSTEM_PATHS_POSIX
        
        if extra_protected:
            raw_paths = raw_paths + extra_protected

        for path_str in raw_paths:
            try:
                p = Path(path_str).resolve()
                system_paths.append(p)
            except Exception:
                continue
        return system_paths

    @classmethod
    def validate_target_directory(
        cls,
        target_path: Path,
        app_dirs: Optional[List[Path]] = None,
        extra_protected: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """
        Validates whether a directory exists, is accessible, and is safe to modify.
        Prevents operating on root, system, or application internal folders.
        """
        try:
            resolved_target = target_path.resolve()
        except Exception as e:
            return False, f"Invalid path resolution: {e}"

        if not resolved_target.exists():
            return False, f"Target directory does not exist: {resolved_target}"

        if not resolved_target.is_dir():
            return False, f"Target path is not a directory: {resolved_target}"

        # Root directory protection
        if resolved_target == resolved_target.anchor or str(resolved_target) in ("/", "\\"):
            return False, f"Refusing to operate on root directory: {resolved_target}"

        # Protected system directory protection
        system_dirs = cls.get_system_directories(extra_protected)
        for sys_dir in system_dirs:
            if resolved_target == sys_dir or sys_dir in resolved_target.parents:
                return False, f"Target directory is a protected system directory: {resolved_target}"

        # App internal folder protection (database, log directories)
        if app_dirs:
            for app_dir in app_dirs:
                try:
                    resolved_app = app_dir.resolve()
                    if resolved_target == resolved_app or resolved_app in resolved_target.parents:
                        return False, f"Target directory overlaps with internal application path: {resolved_app}"
                except Exception:
                    continue

        # Check write permissions
        if not os.access(resolved_target, os.W_OK | os.X_OK):
            return False, f"Permission denied: cannot write to target directory {resolved_target}"

        return True, "Directory is valid and safe."

    @classmethod
    def is_safe_subpath(cls, child: Path, parent: Path) -> bool:
        """Verifies that child path is strictly located within parent path (prevents directory traversal)."""
        try:
            resolved_child = child.resolve()
            resolved_parent = parent.resolve()
            return resolved_parent in resolved_child.parents or resolved_child == resolved_parent
        except Exception:
            return False

    @classmethod
    def sanitize_filename(cls, filename: str, replacement: str = "_") -> str:
        """Removes illegal OS characters from a proposed filename."""
        sanitized = re.sub(cls.INVALID_FILENAME_CHARS, replacement, filename)
        # Strip leading/trailing spaces or dots (problematic on Windows)
        return sanitized.strip(" .")