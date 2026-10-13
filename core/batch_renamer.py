import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from core.file_operations import SafeFileOps
from core.validators import PathValidator

logger = logging.getLogger(__name__)


class BatchRenamer:
    """
    Pattern-based batch renamer with collision checking, validation,
    and support for custom templates, counters, dates, and text replacement.
    """

    @staticmethod
    def apply_case_change(text: str, case_mode: str) -> str:
        """Applies letter casing mode to text."""
        if case_mode == "lower":
            return text.lower()
        elif case_mode == "upper":
            return text.upper()
        elif case_mode == "title":
            return text.title()
        return text

    @staticmethod
    def sanitize_spaces(text: str) -> str:
        """Replaces multiple spaces or special characters with clean underscores."""
        cleaned = re.sub(r"\s+", "_", text)
        return re.sub(r"[^\w\.-]", "_", cleaned)

    @classmethod
    def generate_new_name(
        cls,
        source_path: Path,
        index: int,
        prefix: str = "",
        suffix: str = "",
        find_text: str = "",
        replace_text: str = "",
        counter_start: int = 1,
        counter_padding: int = 3,
        case_mode: str = "none",
        clean_spaces: bool = False,
        custom_template: str = "",
        preserve_extension: bool = True,
    ) -> str:
    
        stem = source_path.stem
        ext = source_path.suffix if preserve_extension else ""

        if custom_template:
            try:
                counter_val = f"{counter_start + index - 1:0{counter_padding}d}"
                date_val = datetime.now().strftime("%Y-%m-%d")
                clean_ext = ext.lstrip(".")

                new_stem = custom_template.format(
                    original=stem,
                    counter=counter_val,
                    date=date_val,
                    ext=clean_ext
                )
            except (KeyError, ValueError) as e:
                logger.warning(f"Template formatting error, falling back to original stem: {e}")
                new_stem = stem
        else:
            new_stem = stem

            # Text Replacement
            if find_text:
                new_stem = new_stem.replace(find_text, replace_text)

            # Prefix and Suffix
            new_stem = f"{prefix}{new_stem}{suffix}"

            # Counter
            if counter_padding > 0:
                counter_str = f"_{counter_start + index - 1:0{counter_padding}d}"
                new_stem = f"{new_stem}{counter_str}"

        # Casing
        new_stem = cls.apply_case_change(new_stem, case_mode)

        # Space cleaning
        if clean_spaces:
            new_stem = cls.sanitize_spaces(new_stem)

        # Sanitize OS invalid characters
        new_stem = PathValidator.sanitize_filename(new_stem)

        return f"{new_stem}{ext}"

    @classmethod
    def generate_preview(
        cls,
        files: List[Path],
        **renaming_kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generates a preview plan for batch renaming.
        Detects internal name collisions and conflicts with existing files.
        """
        preview_plan = []
        proposed_destinations = set()

        for idx, file_path in enumerate(files, start=1):
            new_name = cls.generate_new_name(file_path, idx, **renaming_kwargs)
            target_path = file_path.parent / new_name

            has_conflict = False
            conflict_reason = ""

            # Check duplicate within this batch run
            if target_path in proposed_destinations:
                has_conflict = True
                conflict_reason = "Duplicate destination in batch operation."
            elif target_path.exists() and target_path != file_path:
                has_conflict = True
                conflict_reason = "File already exists on disk."

            proposed_destinations.add(target_path)

            preview_plan.append({
                "source": file_path,
                "old_name": file_path.name,
                "new_name": new_name,
                "target_path": target_path,
                "has_conflict": has_conflict,
                "conflict_reason": conflict_reason,
            })

        return preview_plan

    @classmethod
    def execute_renaming(
        cls,
        preview_plan: List[Dict[str, Any]],
        progress_callback=None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Executes batch renaming on files in the preview plan.
        Returns tuple of (successful_renames, failed_renames).
        """
        successful = []
        failed = []
        total = len(preview_plan)

        # Abort batch run if collisions exist
        conflicts = [item for item in preview_plan if item["has_conflict"]]
        if conflicts:
            err_msg = f"Aborting batch rename: {len(conflicts)} naming collisions detected."
            logger.error(err_msg)
            return [], [{"source": str(c["source"]), "error": c["conflict_reason"]} for c in conflicts]

        for idx, item in enumerate(preview_plan, start=1):
            source: Path = item["source"]
            new_name: str = item["new_name"]

            success, actual_dest, message = SafeFileOps.safe_rename(
                source=source,
                new_name=new_name,
                overwrite=False
            )

            if success:
                successful.append({
                    "source": str(source),
                    "destination": str(actual_dest),
                    "old_name": item["old_name"],
                    "new_name": new_name
                })
            else:
                failed.append({
                    "source": str(source),
                    "destination": str(item["target_path"]),
                    "error": message
                })

            if progress_callback:
                progress_callback(idx, total, new_name)

        return successful, failed