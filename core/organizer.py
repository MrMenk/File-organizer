import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any
from core.file_operations import SafeFileOps
from core.validators import PathValidator

logger = logging.getLogger(__name__)


class FileOrganizer:
    """
    Core engine for extension-based file organization, categorization preview,
    and automatic folder structure generation.
    """

    def __init__(
        self,
        categories: Optional[Dict[str, List[str]]] = None,
        organize_others: bool = True,
        others_folder: str = "Others",
        recursive: bool = False
    ):
        self.categories = categories or {}
        self.organize_others = organize_others
        self.others_folder = others_folder
        self.recursive = recursive
        self._ext_map = self._build_extension_mapping()

    @classmethod
    def load_from_config(
        cls,
        categories_path: Path,
        settings_path: Path,
        recursive_override: Optional[bool] = None
    ) -> "FileOrganizer":
        """Loads categories and settings directly from JSON configuration files."""
        categories = {}
        if categories_path.exists():
            try:
                with open(categories_path, "r", encoding="utf-8") as f:
                    categories = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load categories config: {e}")

        settings = {}
        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load settings config: {e}")

        recursive = recursive_override if recursive_override is not None else settings.get("recursive_scan", False)
        organize_others = settings.get("organize_others", True)
        others_folder = settings.get("others_folder_name", "Others")

        return cls(
            categories=categories,
            organize_others=organize_others,
            others_folder=others_folder,
            recursive=recursive
        )

    def _build_extension_mapping(self) -> Dict[str, str]:
        """Inverts category list into a fast extension lookup map (extension -> category)."""
        mapping = {}
        for category, extensions in self.categories.items():
            for ext in extensions:
                clean_ext = ext.strip().lower().lstrip(".")
                if clean_ext:
                    mapping[clean_ext] = category
        return mapping

    def get_category_for_extension(self, extension: str) -> Optional[str]:
        """Maps a file extension to its configured category name."""
        clean_ext = extension.strip().lower().lstrip(".")
        if not clean_ext:
            return self.others_folder if self.organize_others else None
        
        category = self._ext_map.get(clean_ext)
        if category:
            return category
        
        return self.others_folder if self.organize_others else None

    def scan_files(
        self,
        target_dir: Path,
        selected_categories: Optional[Set[str]] = None,
        app_dirs: Optional[List[Path]] = None
    ) -> List[Path]:
        """Scans the target directory for eligible files."""
        target_dir = target_dir.resolve()
        files_to_process = []

        def is_app_or_system(p: Path) -> bool:
            if app_dirs:
                for app_d in app_dirs:
                    if p == app_d or app_d in p.parents:
                        return True
            return False

        if self.recursive:
            file_iter = (p for p in target_dir.rglob("*") if p.is_file())
        else:
            file_iter = (p for p in target_dir.iterdir() if p.is_file())

        for file_path in file_iter:
            if file_path.is_symlink() or is_app_or_system(file_path):
                continue

            ext = file_path.suffix
            category = self.get_category_for_extension(ext)

            if category is None:
                continue

            if selected_categories and category not in selected_categories:
                continue

            # Don't re-organize files already inside their target category folder
            if file_path.parent.name == category and file_path.parent.parent == target_dir:
                continue

            files_to_process.append(file_path)

        return files_to_process

    def generate_preview(
        self,
        target_dir: Path,
        selected_categories: Optional[Set[str]] = None,
        app_dirs: Optional[List[Path]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates a dry-run preview of planned moves without modifying the filesystem.
        """
        files = self.scan_files(target_dir, selected_categories, app_dirs)
        preview_plan = []

        for source in files:
            ext = source.suffix
            category = self.get_category_for_extension(ext) or self.others_folder
            destination = target_dir / category / source.name

            # Detect potential naming collisions
            will_conflict = destination.exists()
            resolved_dest = SafeFileOps.resolve_unique_path(destination) if will_conflict else destination

            preview_plan.append({
                "source": source,
                "proposed_destination": destination,
                "resolved_destination": resolved_dest,
                "category": category,
                "size": source.stat().st_size if source.exists() else 0,
                "has_conflict": will_conflict
            })

        return preview_plan

    def execute_organization(
        self,
        target_dir: Path,
        preview_plan: Optional[List[Dict[str, Any]]] = None,
        selected_categories: Optional[Set[str]] = None,
        app_dirs: Optional[List[Path]] = None,
        progress_callback=None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Executes file moves based on the plan or scans directly.
        Returns tuple of (successful_operations, failed_operations).
        """
        if preview_plan is None:
            preview_plan = self.generate_preview(target_dir, selected_categories, app_dirs)

        successful = []
        failed = []
        total_files = len(preview_plan)

        for idx, item in enumerate(preview_plan, start=1):
            source: Path = item["source"]
            destination: Path = item["proposed_destination"]

            if not source.exists():
                failed.append({
                    "source": str(source),
                    "destination": str(destination),
                    "error": "Source file was deleted or moved prior to operation."
                })
                continue

            success, actual_dest, message = SafeFileOps.safe_move(
                source=source,
                destination=destination,
                overwrite=False,
                auto_rename=True
            )

            if success:
                successful.append({
                    "source": str(source),
                    "destination": str(actual_dest),
                    "category": item["category"],
                    "file_size": item["size"]
                })
            else:
                failed.append({
                    "source": str(source),
                    "destination": str(destination),
                    "error": message
                })

            if progress_callback:
                progress_callback(idx, total_files, str(source.name))

        return successful, failed