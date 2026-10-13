"""GUI dialogs scaffold."""
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional


class PreviewDialog(tk.Toplevel):
    """Dialog window displaying a preview table of planned file actions before execution."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        items: List[Dict[str, Any]],
        columns: List[Tuple[str, str, int]],
        on_confirm: Callable[[], None]
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("850x500")
        self.transient(parent)
        self.grab_set()

        self.items = items
        self.on_confirm = on_confirm
        self.confirmed = False

        self._build_ui(columns)

    def _build_ui(self, columns: List[Tuple[str, str, int]]) -> None:
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        header_label = ttk.Label(
            main_frame,
            text=f"Review Planned Actions ({len(self.items)} items)",
            font=("Helvetica", 11, "bold")
        )
        header_label.pack(anchor=tk.W, pady=(0, 10))

        # Treeview for planned changes
        col_ids = [c[0] for c in columns]
        self.tree = ttk.Treeview(main_frame, columns=col_ids, show="headings", height=15)

        scrollbar_y = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        for col_id, heading, width in columns:
            self.tree.heading(col_id, text=heading)
            self.tree.column(col_id, width=width, anchor=tk.W)

        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # Populate rows
        for item in self.items:
            row_vals = [item.get(c[0], "") for c in columns]
            self.tree.insert("", tk.END, values=row_vals)

        # Action Buttons
        btn_frame = ttk.Frame(main_frame, padding=(0, 10, 0, 0))
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        confirm_btn = ttk.Button(btn_frame, text="Confirm & Execute", command=self._confirm)
        confirm_btn.pack(side=tk.RIGHT, padx=5)

        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)

    def _confirm(self) -> None:
        self.confirmed = True
        self.destroy()
        self.on_confirm()


class CategoryConfigDialog(tk.Toplevel):
    """Dialog allowing users to inspect and update extension-to-category mappings."""

    def __init__(self, parent: tk.Widget, categories: Dict[str, List[str]], on_save: Callable[[Dict[str, List[str]]], None]):
        super().__init__(parent)
        self.title("Configure Category Mappings")
        self.geometry("600x450")
        self.transient(parent)
        self.grab_set()

        self.categories = {k: list(v) for k, v in categories.items()}
        self.on_save = on_save

        self._build_ui()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        info_lbl = ttk.Label(
            main_frame,
            text="Edit extensions separated by commas for each category:",
            font=("Helvetica", 10)
        )
        info_lbl.pack(anchor=tk.W, pady=(0, 10))

        # Form entries frame
        canvas = tk.Canvas(main_frame, borderwidth=0)
        frame_entries = ttk.Frame(canvas)
        vsb = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame_entries, anchor="nw")

        self.entries = {}
        for row, (cat, exts) in enumerate(self.categories.items()):
            lbl = ttk.Label(frame_entries, text=f"{cat}:", font=("Helvetica", 9, "bold"))
            lbl.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)

            ext_str = ", ".join(exts)
            ent = ttk.Entry(frame_entries, width=50)
            ent.insert(0, ext_str)
            ent.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
            self.entries[cat] = ent

        frame_entries.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        save_btn = ttk.Button(btn_frame, text="Save Settings", command=self._save)
        save_btn.pack(side=tk.RIGHT, padx=5)

        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)

    def _save(self) -> None:
        updated = {}
        for cat, ent in self.entries.items():
            raw = ent.get()
            ext_list = [x.strip().lower().lstrip(".") for x in raw.split(",") if x.strip()]
            updated[cat] = ext_list

        self.on_save(updated)
        self.destroy()