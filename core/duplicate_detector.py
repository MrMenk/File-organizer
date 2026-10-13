import hashlib
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """
    Identifies duplicate files using file-size grouping followed by SHA-256 hash verification.
    Safely ignores symbolic links and handles file access errors.
    """

    def __init__(self, chunk_size: int = 65536):
        self.chunk_size = chunk_size

    def calculate_file_hash(self, file_path: Path) -> Optional[str]:
        """Calculates SHA-256 hash of a file in streaming chunks."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(self.chunk_size):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (PermissionError, OSError, FileNotFoundError) as e:
            logger.warning(f"Could not hash file {file_path}: {e}")
            return None

    def scan_directory(
        self,
        target_dir: Path,
        recursive: bool = False,
        app_dirs: Optional[List[Path]] = None,
        progress_callback=None
    ) -> List[Dict[str, Any]]:
     
        target_dir = target_dir.resolve()

        def is_app_or_system(p: Path) -> bool:
            if app_dirs:
                for app_d in app_dirs:
                    if p == app_d or app_d in p.parents:
                        return True
            return False

        # Gather files
        if recursive:
            file_candidates = [p for p in target_dir.rglob("*") if p.is_file() and not p.is_symlink()]
        else:
            file_candidates = [p for p in target_dir.iterdir() if p.is_file() and not p.is_symlink()]

        file_candidates = [p for p in file_candidates if not is_app_or_system(p)]

        # Pass 1: Group by size
        size_groups = defaultdict(list)
        for p in file_candidates:
            try:
                stat = p.stat()
                if stat.st_size > 0:  # Skip zero-byte files from duplicate matching
                    size_groups[stat.st_size].append(p)
            except (OSError, PermissionError):
                continue

        # Filter sizes with at least two files
        potential_duplicates = [
            (size, paths) for size, paths in size_groups.items() if len(paths) > 1
        ]

        total_to_hash = sum(len(paths) for _, paths in potential_duplicates)
        hashed_count = 0

        # Pass 2: Calculate SHA-256 hashes for size collisions
        hash_groups = defaultdict(list)
        for size, paths in potential_duplicates:
            for path in paths:
                file_hash = self.calculate_file_hash(path)
                if file_hash:
                    hash_groups[(size, file_hash)].append(path)

                hashed_count += 1
                if progress_callback:
                    progress_callback(hashed_count, total_to_hash, path.name)

        # Build duplicate report groups (only groups with >1 file)
        duplicate_results = []
        for (size, file_hash), file_list in hash_groups.items():
            if len(file_list) > 1:
                duplicate_results.append({
                    "hash": file_hash,
                    "size": size,
                    "count": len(file_list),
                    "files": [
                        {
                            "path": str(p),
                            "name": p.name,
                            "modified": p.stat().st_mtime if p.exists() else 0
                        }
                        for p in file_list
                    ]
                })

        return duplicate_results