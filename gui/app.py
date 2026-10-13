import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

from storage.database import DatabaseManager
from storage.history_repository import HistoryRepository
from core.file_operations import SafeFileOps
from core.validators import PathValidator
from core.organizer import FileOrganizer
from core.duplicate_detector import DuplicateDetector
from core.batch_renamer import BatchRenamer
from core.undo_manager import UndoManager

from gui.dashboard import DashboardTab
from gui.dialogs import PreviewDialog, CategoryConfigDialog

logger = logging.getLogger(__name__)


class FileOrganizerGUI(tk.Tk):
    """
    Main Application Window integrating all features:
    Dashboard, Automatic Categorization, Duplicate Detection, Batch Renamer, History, and Undo.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        categories_path: Path,
        settings_path: Path,
        app_dirs: Optional[List[Path]] = None
    ):
        super().__init__()
        self.title("File Organizer Tool - Professional Edition")
        self.geometry("1024x700")
        self.minsize(900, 600)

        self.db_manager = db_manager
        self.history_repo = HistoryRepository(db_manager)
        self.undo_manager = UndoManager(self.history_repo)
        self.categories_path = categories_path
        self.settings_path = settings_path
        self.app_dirs = app_dirs or []

        self.organizer = FileOrganizer.load_from_config(categories_path, settings_path)
        self.selected_directory: Optional[Path] = None

        self._build_ui()
        self._refresh_undo_status()

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 0: Dashboard
        self.dashboard_tab = DashboardTab(
            self.notebook,
            on_select_directory=self.on_directory_selected,
            on_undo_request=self.execute_undo,
            on_navigate_tab=self.notebook.select
        )
        self.notebook.add(self.dashboard_tab, text=" Dashboard ")

        # Tab 1: Organizer
        self.organizer_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.organizer_frame, text=" Automatic Organizer ")
        self._build_organizer_tab()

        # Tab 2: Duplicate Detector
        self.duplicates_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.duplicates_frame, text=" Duplicate Detector ")
        self._build_duplicates_tab()

        # Tab 3: Batch Renamer
        self.renamer_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.renamer_frame, text=" Batch Renamer ")
        self._build_renamer_tab()

        # Tab 4: History & Audit Logs
        self.history_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.history_frame, text=" Operation History ")
        self._build_history_tab()

        # Status Bar
        self.status_bar = ttk.Label(
            self,
            text="Ready. Please select a working directory.",
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=5
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # TAB 1: ORGANIZER
    # ------------------------------------------------------------------
    def _build_organizer_tab(self) -> None:
        top_frame = ttk.Frame(self.organizer_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(top_frame, text="Select categories to organize:", font=("Helvetica", 10, "bold")).pack(anchor=tk.W)

        self.category_vars: Dict[str, tk.BooleanVar] = {}
        cat_frame = ttk.Frame(top_frame)
        cat_frame.pack(fill=tk.X, pady=5)

        row, col = 0, 0
        for cat in self.organizer.categories.keys():
            var = tk.BooleanVar(value=True)
            self.category_vars[cat] = var
            chk = ttk.Checkbutton(cat_frame, text=cat, variable=var)
            chk.grid(row=row, column=col, sticky=tk.W, padx=10, pady=2)
            col += 1
            if col > 3:
                col = 0
                row += 1

        opt_frame = ttk.Frame(self.organizer_frame)
        opt_frame.pack(fill=tk.X, pady=5)

        self.recursive_var = tk.BooleanVar(value=self.organizer.recursive)
        chk_rec = ttk.Checkbutton(opt_frame, text="Recursive Scan (Include Subdirectories)", variable=self.recursive_var)
        chk_rec.pack(side=tk.LEFT, padx=(0, 15))

        cfg_btn = ttk.Button(opt_frame, text="Configure Category Mappings...", command=self._open_category_config)
        cfg_btn.pack(side=tk.LEFT)

        btn_frame = ttk.Frame(self.organizer_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        preview_btn = ttk.Button(btn_frame, text="Preview Organization", command=self._preview_organization)
        preview_btn.pack(side=tk.LEFT, padx=(0, 10))

        run_btn = ttk.Button(btn_frame, text="Organize Now", command=self._execute_organization)
        run_btn.pack(side=tk.LEFT)

        # Preview Log Box
        self.org_log_text = tk.Text(self.organizer_frame, height=15, font=("Consolas", 9))
        self.org_log_text.pack(fill=tk.BOTH, expand=True)

    def _open_category_config(self) -> None:
        def on_save(new_cats: Dict[str, List[str]]):
            self.organizer.categories = new_cats
            self.organizer._ext_map = self.organizer._build_extension_mapping()
            messagebox.showinfo("Success", "Category mappings updated successfully.")

        CategoryConfigDialog(self, self.organizer.categories, on_save)

    def _get_selected_categories(self) -> Set[str]:
        return {cat for cat, var in self.category_vars.items() if var.get()}

    def _preview_organization(self) -> None:
        if not self._validate_directory_selected():
            return

        self.organizer.recursive = self.recursive_var.get()
        selected_cats = self._get_selected_categories()
        plan = self.organizer.generate_preview(self.selected_directory, selected_cats, self.app_dirs)

        self.org_log_text.delete("1.0", tk.END)
        self.org_log_text.insert(tk.END, f"Found {len(plan)} files to organize:\n\n")

        for item in plan:
            status = " [CONFLICT - AUTO RENAME]" if item["has_conflict"] else ""
            line = f"• {item['source'].name} -> {item['category']}/{item['proposed_destination'].name}{status}\n"
            self.org_log_text.insert(tk.END, line)

    def _execute_organization(self) -> None:
        if not self._validate_directory_selected():
            return

        self.organizer.recursive = self.recursive_var.get()
        selected_cats = self._get_selected_categories()
        plan = self.organizer.generate_preview(self.selected_directory, selected_cats, self.app_dirs)

        if not plan:
            messagebox.showinfo("Notice", "No files found matching the organization criteria.")
            return

        cols = [
            ("source", "Source File", 300),
            ("category", "Target Category", 150),
            ("resolved_destination", "Destination Path", 350)
        ]

        def on_confirm():
            def run_task():
                self.set_status("Organizing files...")
                succ, fail = self.organizer.execute_organization(
                    self.selected_directory,
                    preview_plan=plan,
                    app_dirs=self.app_dirs
                )
                batch_id = self.history_repo.generate_batch_id()
                self.history_repo.record_batch_operations(
                    batch_id, "ORGANIZE", succ, fail
                )
                self.after(0, lambda: self._on_org_complete(len(succ), len(fail)))

            threading.Thread(target=run_task, daemon=True).start()

        PreviewDialog(self, "Confirm File Organization", plan, cols, on_confirm)

    def _on_org_complete(self, success_count: int, fail_count: int) -> None:
        self.set_status(f"Organization complete: {success_count} moved, {fail_count} failed.")
        messagebox.showinfo("Execution Complete", f"Successfully moved {success_count} files.\nFailures: {fail_count}")
        self._refresh_undo_status()
        self.dashboard_tab.update_directory_summary()

    # ------------------------------------------------------------------
    # TAB 2: DUPLICATES
    # ------------------------------------------------------------------
    def _build_duplicates_tab(self) -> None:
        ctrl_frame = ttk.Frame(self.duplicates_frame)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))

        scan_btn = ttk.Button(ctrl_frame, text="Scan for Duplicates (SHA-256)", command=self._scan_duplicates)
        scan_btn.pack(side=tk.LEFT, padx=(0, 10))

        remove_btn = ttk.Button(ctrl_frame, text="Delete Selected Duplicates", command=self._delete_selected_duplicates)
        remove_btn.pack(side=tk.LEFT)

        cols = ("select", "file_name", "size_mb", "path", "hash")
        self.dup_tree = ttk.Treeview(self.duplicates_frame, columns=cols, show="headings", height=15)
        self.dup_tree.heading("select", text="Delete?")
        self.dup_tree.heading("file_name", text="File Name")
        self.dup_tree.heading("size_mb", text="Size (MB)")
        self.dup_tree.heading("path", text="Full Path")
        self.dup_tree.heading("hash", text="SHA-256 Hash")

        self.dup_tree.column("select", width=60, anchor=tk.CENTER)
        self.dup_tree.column("file_name", width=180)
        self.dup_tree.column("size_mb", width=80, anchor=tk.E)
        self.dup_tree.column("path", width=350)
        self.dup_tree.column("hash", width=150)

        self.dup_tree.pack(fill=tk.BOTH, expand=True)
        self.dup_tree.bind("<Double-1>", self._toggle_dup_selection)

    def _scan_duplicates(self) -> None:
        if not self._validate_directory_selected():
            return

        def run_scan():
            self.set_status("Scanning directory for duplicates...")
            detector = DuplicateDetector()
            dup_groups = detector.scan_directory(
                self.selected_directory,
                recursive=self.recursive_var.get(),
                app_dirs=self.app_dirs
            )
            self.after(0, lambda: self._populate_duplicates(dup_groups))

        threading.Thread(target=run_scan, daemon=True).start()

    def _populate_duplicates(self, dup_groups: List[Dict[str, Any]]) -> None:
        for item in self.dup_tree.get_children():
            self.dup_tree.delete(item)

        total_dups = 0
        for group in dup_groups:
            files = group["files"]
            size_mb = f"{group['size'] / (1024 * 1024):.2f}"
            hash_abbr = group["hash"][:12] + "..."

            for idx, f in enumerate(files):
                flag = "[ ]"
                self.dup_tree.insert(
                    "",
                    tk.END,
                    values=(flag, f["name"], size_mb, f["path"], hash_abbr)
                )
                if idx > 0:
                    total_dups += 1

        self.set_status(f"Duplicate scan finished. Found {len(dup_groups)} groups ({total_dups} duplicate copies).")

    def _toggle_dup_selection(self, event) -> None:
        selected_item = self.dup_tree.selection()
        if not selected_item:
            return
        item_id = selected_item[0]
        vals = list(self.dup_tree.item(item_id, "values"))
        vals[0] = "[X]" if vals[0] == "[ ]" else "[ ]"
        self.dup_tree.item(item_id, values=vals)

    def _delete_selected_duplicates(self) -> None:
        to_delete = []
        for item_id in self.dup_tree.get_children():
            vals = self.dup_tree.item(item_id, "values")
            if vals[0] == "[X]":
                to_delete.append(Path(vals[3]))

        if not to_delete:
            messagebox.showwarning("No Selection", "Please double-click items to mark them '[X]' for deletion.")
            return

        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {len(to_delete)} marked duplicate files?"):
            return

        succ, fail = [], []
        batch_id = self.history_repo.generate_batch_id()

        for p in to_delete:
            ok, msg = SafeFileOps.safe_delete(p)
            if ok:
                succ.append({"source": str(p), "destination": "DELETED"})
            else:
                fail.append({"source": str(p), "destination": "DELETED", "error": msg})

        self.history_repo.record_batch_operations(batch_id, "DELETE_DUPLICATE", succ, fail)
        messagebox.showinfo("Delete Complete", f"Deleted {len(succ)} files. Failures: {len(fail)}.")
        self._scan_duplicates()

    # ------------------------------------------------------------------
    # TAB 3: BATCH RENAMER
    # ------------------------------------------------------------------
    def _build_renamer_tab(self) -> None:
        ctrl_frame = ttk.LabelFrame(self.renamer_frame, text=" Rename Rules ", padding=10)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(ctrl_frame, text="Prefix:").grid(row=0, column=0, sticky=tk.W)
        self.rename_prefix_ent = ttk.Entry(ctrl_frame, width=15)
        self.rename_prefix_ent.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(ctrl_frame, text="Suffix:").grid(row=0, column=2, sticky=tk.W)
        self.rename_suffix_ent = ttk.Entry(ctrl_frame, width=15)
        self.rename_suffix_ent.grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(ctrl_frame, text="Find Text:").grid(row=1, column=0, sticky=tk.W)
        self.rename_find_ent = ttk.Entry(ctrl_frame, width=15)
        self.rename_find_ent.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(ctrl_frame, text="Replace Text:").grid(row=1, column=2, sticky=tk.W)
        self.rename_replace_ent = ttk.Entry(ctrl_frame, width=15)
        self.rename_replace_ent.grid(row=1, column=3, padx=5, pady=2)

        ttk.Label(ctrl_frame, text="Custom Template:").grid(row=2, column=0, sticky=tk.W)
        self.rename_tmpl_ent = ttk.Entry(ctrl_frame, width=35)
        self.rename_tmpl_ent.insert(0, "{original}_{counter}")
        self.rename_tmpl_ent.grid(row=2, column=1, columnspan=3, sticky=tk.W, padx=5, pady=2)

        btn_frame = ttk.Frame(self.renamer_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        prev_btn = ttk.Button(btn_frame, text="Preview Rename", command=self._preview_rename)
        prev_btn.pack(side=tk.LEFT, padx=(0, 10))

        run_btn = ttk.Button(btn_frame, text="Execute Batch Rename", command=self._execute_rename)
        run_btn.pack(side=tk.LEFT)

        cols = ("old_name", "new_name", "status")
        self.rename_tree = ttk.Treeview(self.renamer_frame, columns=cols, show="headings", height=12)
        self.rename_tree.heading("old_name", text="Original Filename")
        self.rename_tree.heading("new_name", text="Proposed Filename")
        self.rename_tree.heading("status", text="Conflict Status")
        self.rename_tree.column("old_name", width=300)
        self.rename_tree.column("new_name", width=300)
        self.rename_tree.column("status", width=200)

        self.rename_tree.pack(fill=tk.BOTH, expand=True)

    def _get_rename_kwargs(self) -> Dict[str, Any]:
        return {
            "prefix": self.rename_prefix_ent.get(),
            "suffix": self.rename_suffix_ent.get(),
            "find_text": self.rename_find_ent.get(),
            "replace_text": self.rename_replace_ent.get(),
            "custom_template": self.rename_tmpl_ent.get(),
        }

    def _preview_rename(self) -> None:
        if not self._validate_directory_selected():
            return

        files = [p for p in self.selected_directory.iterdir() if p.is_file() and not p.is_symlink()]
        plan = BatchRenamer.generate_preview(files, **self._get_rename_kwargs())

        for item in self.rename_tree.get_children():
            self.rename_tree.delete(item)

        for row in plan:
            status = row["conflict_reason"] if row["has_conflict"] else "OK"
            self.rename_tree.insert("", tk.END, values=(row["old_name"], row["new_name"], status))

    def _execute_rename(self) -> None:
        if not self._validate_directory_selected():
            return

        files = [p for p in self.selected_directory.iterdir() if p.is_file() and not p.is_symlink()]
        plan = BatchRenamer.generate_preview(files, **self._get_rename_kwargs())

        conflicts = [p for p in plan if p["has_conflict"]]
        if conflicts:
            messagebox.showerror("Conflict Error", f"Cannot execute rename: {len(conflicts)} naming conflicts detected.")
            return

        succ, fail = BatchRenamer.execute_renaming(plan)
        batch_id = self.history_repo.generate_batch_id()
        self.history_repo.record_batch_operations(batch_id, "RENAME", succ, fail)

        messagebox.showinfo("Rename Complete", f"Successfully renamed {len(succ)} files. Failures: {len(fail)}.")
        self._refresh_undo_status()
        self._preview_rename()

    # ------------------------------------------------------------------
    # TAB 4: HISTORY
    # ------------------------------------------------------------------
    def _build_history_tab(self) -> None:
        ctrl_frame = ttk.Frame(self.history_frame)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))

        refresh_btn = ttk.Button(ctrl_frame, text="Refresh History", command=self._load_history)
        refresh_btn.pack(side=tk.LEFT)

        cols = ("id", "timestamp", "type", "source", "destination", "status", "undone")
        self.history_tree = ttk.Treeview(self.history_frame, columns=cols, show="headings", height=15)
        self.history_tree.heading("id", text="ID")
        self.history_tree.heading("timestamp", text="Timestamp")
        self.history_tree.heading("type", text="Type")
        self.history_tree.heading("source", text="Source Path")
        self.history_tree.heading("destination", text="Destination Path")
        self.history_tree.heading("status", text="Status")
        self.history_tree.heading("undone", text="Undone?")

        self.history_tree.column("id", width=50)
        self.history_tree.column("timestamp", width=140)
        self.history_tree.column("type", width=100)
        self.history_tree.column("source", width=250)
        self.history_tree.column("destination", width=250)
        self.history_tree.column("status", width=80)
        self.history_tree.column("undone", width=70)

        self.history_tree.pack(fill=tk.BOTH, expand=True)

    def _load_history(self) -> None:
        records = self.history_repo.fetch_history(limit=200)
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        for r in records:
            undone_str = "YES" if r["is_undone"] else "NO"
            self.history_tree.insert(
                "",
                tk.END,
                values=(r["id"], r["timestamp"], r["operation_type"], r["source_path"], r["destination_path"], r["status"], undone_str)
            )

    # ------------------------------------------------------------------
    # GENERAL APP HELPERS & UNDO
    # ------------------------------------------------------------------
    def on_directory_selected(self, path: Path) -> None:
        self.selected_directory = path
        self.set_status(f"Working Directory set to: {path}")

    def _validate_directory_selected(self) -> bool:
        if not self.selected_directory:
            messagebox.showwarning("Missing Directory", "Please select a working directory first on the Dashboard tab.")
            return False
        valid, msg = PathValidator.validate_target_directory(self.selected_directory, self.app_dirs)
        if not valid:
            messagebox.showerror("Invalid Directory", msg)
            return False
        return True

    def execute_undo(self) -> None:
        info = self.undo_manager.get_last_undoable_batch_info()
        if not info:
            messagebox.showinfo("Undo Notice", "There are no operations available to undo.")
            return

        msg = f"Undo last batch '{info['operation_type']}' containing {info['record_count']} items executed at {info['batch_time']}?"
        if not messagebox.askyesno("Confirm Undo", msg):
            return

        ok, summary, restored, failed = self.undo_manager.undo_last_operation()
        messagebox.showinfo("Undo Results", summary)
        self._refresh_undo_status()
        self._load_history()

    def _refresh_undo_status(self) -> None:
        info = self.undo_manager.get_last_undoable_batch_info()
        self.dashboard_tab.update_last_operation_info(info)

    def set_status(self, message: str) -> None:
        self.status_bar.config(text=message)