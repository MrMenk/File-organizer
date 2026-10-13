"""
Storage and persistence module for the File Organizer Tool.
Provides SQLite database initialization and repository methods
for storing structured operation history and undo metadata.
"""

from storage.database import DatabaseManager
from storage.history_repository import HistoryRepository

__all__ = ["DatabaseManager", "HistoryRepository"]