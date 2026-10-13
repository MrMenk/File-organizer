import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Callable, Optional, Dict, List, Any


class DashboardTab(ttk.Frame):
    """
    Main dashboard view providing direct directory selection, quick action shortcuts,
    recent operation history stats, and an explicit undo trigger.
    """

    def __init__(
        self,
        parent: ttk.Notebook,
        on_select_directory: Callable[[Path], None],
        on_undo_request: Callable[[], None],
        on_navigate_tab: Callable[[int], None]
    ):
        super().__init__(parent, padding=15)
        self.on_select_directory = on_select_directory
        self.on_undo_request = on_undo_request
        self.on_navigate_tab = on_navigate_tab

        self.selected_directory: Optional[Path] = None

        self._build_ui()

    def _build_ui(self) -> None:
        # Top Header Section
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        title_lbl = ttk.Label(
            header_frame,
            text="File Organizer Dashboard",
            font=("Helvetica", 16, "bold")
        )
        title_lbl.pack(anchor=tk.W)

        subtitle_lbl = ttk.Label(
            header_frame,
            text="Select a working directory to begin organizing, detecting duplicates, or batch renaming.",
            font=("Helvetica", 10)
        )
        subtitle_lbl.pack(anchor=tk.W, pady=(2, 0))

        # Directory Selector Panel
        dir_frame = ttk.LabelFrame(self, text=" Working Directory ", padding=12)
        dir_frame.pack(fill=tk.X, pady=(0, 15))

        self.dir_path_var = tk.StringVar(value="No directory selected.")
        dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_path_var, state="readonly", font=("Consolas", 10))
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        browse_btn = ttk.Button(dir_frame, text="Browse Folder...", command=self._browse_directory)
        browse_btn.pack(side=tk.RIGHT)

        # Quick Actions Panel
        actions_frame = ttk.LabelFrame(self, text=" Quick Actions ", padding=12)
        actions_frame.pack(fill=tk.X, pady=(0, 15))

        organize_btn = ttk.Button(
            actions_frame,
            text="Automatic Organizer",
            command=lambda: self.on_navigate_tab(1)
        )
        organize_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        duplicates_btn = ttk.Button(
            actions_frame,
            text="Find Duplicates",
            command=lambda: self.on_navigate_tab(2)
        )
        duplicates_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        renamer_btn = ttk.Button(
            actions_frame,
            text="Batch Renamer",
            command=lambda: self.on_navigate_tab(3)
        )
        renamer_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # Transaction & Safety Panel
        safety_frame = ttk.LabelFrame(self, text=" Safety & System Controls ", padding=12)
        safety_frame.pack(fill=tk.X, pady=(0, 15))

        self.last_op_var = tk.StringVar(value="Last Operation: None / No active history")
        last_op_lbl = ttk.Label(safety_frame, textvariable=self.last_op_var, font=("Helvetica", 10))
        last_op_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        undo_btn = ttk.Button(
            safety_frame,
            text="Undo Last Operation",
            command=self.on_undo_request
        )
        undo_btn.pack(side=tk.RIGHT)

        # System Status Summary Box
        status_frame = ttk.LabelFrame(self, text=" Directory Summary ", padding=12)
        status_frame.pack(fill=tk.BOTH, expand=True)

        self.summary_text = tk.Text(
            status_frame,
            wrap=tk.WORD,
            height=8,
            state="disabled",
            font=("Consolas", 9),
            bg="#f8f9fa",
            relief="flat"
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True)

    def _browse_directory(self) -> None:
        chosen = filedialog.askdirectory(title="Select Directory to Organize")
        if chosen:
            path = Path(chosen).resolve()
            self.set_selected_directory(path)

    def set_selected_directory(self, path: Path) -> None:
        self.selected_directory = path
        self.dir_path_var.set(str(path))
        self.on_select_directory(path)
        self.update_directory_summary()

    def update_last_operation_info(self, info: Optional[Dict[str, Any]]) -> None:
        if info:
            self.last_op_var.set(
                f"Last Operation: {info.get('operation_type', 'N/A')} "
                f"({info.get('record_count', 0)} files at {info.get('batch_time', '')})"
            )
        else:
            self.last_op_var.set("Last Operation: None / No active undoable transaction")

    def update_directory_summary(self) -> None:
        if not self.selected_directory or not self.selected_directory.exists():
            return

        try:
            files = [p for p in self.selected_directory.iterdir() if p.is_file()]
            dirs = [p for p in self.selected_directory.iterdir() if p.is_dir()]
            total_size = sum(p.stat().st_size for p in files)

            summary = (
                f"Path: {self.selected_directory}\n"
                f"Files in top-level directory: {len(files)}\n"
                f"Subdirectories: {len(dirs)}\n"
                f"Total File Size: {total_size / (1024 * 1024):.2f} MB\n\n"
                f"Ready to execute operations safely with automatic undo logging."
            )
        except Exception as e:
            summary = f"Error reading directory details: {e}"

        self.summary_text.config(state="normal")
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert(tk.END, summary)
        self.summary_text.config(state="disabled")