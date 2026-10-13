# File Organizer Tool (Python)

A modular, cross-platform Python application designed to automatically organize files, detect duplicates using SHA-256 cryptographic hashing, perform batch file renaming with collision checks, record structured audit logs in SQLite, and safely reverse multi-file operations with a transaction-based undo engine.

---

## Key Features

1. **Automatic Categorization & Organization**
   - Scans target folders and sorts files into configurable categories (`Images`, `Documents`, `Spreadsheets`, `Code`, `Audio`, `Videos`, `Archives`, `Executables`, `Others`).
   - Supports optional recursive scanning of subdirectories.
   - Prevents overwriting existing files by appending incremental counters (e.g., `file_1.txt`).
   - Offers a dry-run preview before executing file operations.

2. **Duplicate Detection**
   - Fast, two-pass detection: filters files by size before computing SHA-256 content hashes.
   - Ignores symbolic links to prevent circular folder traversal.
   - Never deletes duplicates automatically; requires explicit user selection.

3. **Batch Renaming Engine**
   - Rename files using customizable templates with placeholders (`{original}`, `{counter}`, `{date}`, `{ext}`).
   - Supports prefixes, suffixes, text find-and-replace, casing changes, and space sanitization.
   - Pre-validates destination names to catch and block naming collisions before execution.

4. **Transaction-Based Undo System**
   - Persists operation metadata in an SQLite database.
   - Reverses operations in reverse execution order.
   - Ensures no file is overwritten during an undo operation if the original destination path is occupied.
   - Operations remain undoable across application restarts.

5. **Dual User Interface**
   - **GUI**: Built with Python’s native Tkinter library. Features background threading to keep the UI responsive during large directory scans.
   - **CLI**: Standard command-line interface with verbose dry-run previews and structured output.

