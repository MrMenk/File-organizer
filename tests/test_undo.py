import pytest
from pathlib import Path
from storage.database import DatabaseManager
from storage.history_repository import HistoryRepository
from core.organizer import FileOrganizer
from core.batch_renamer import BatchRenamer
from core.undo_manager import UndoManager


@pytest.fixture
def undo_env(tmp_path):
    """Fixture providing a full runtime environment for testing persistent undo transactions."""
    test_dir = tmp_path / "undo_workspace"
    test_dir.mkdir()

    db_path = tmp_path / "storage" / "test_organizer.db"
    db_mgr = DatabaseManager(db_path)
    repo = HistoryRepository(db_mgr)
    undo_mgr = UndoManager(repo)

    return {
        "dir": test_dir,
        "repo": repo,
        "undo_mgr": undo_mgr,
    }


def test_undo_organization_operation(undo_env):
    workspace = undo_env["dir"]
    repo = undo_env["repo"]
    undo_mgr = undo_env["undo_mgr"]

    # Setup files
    f1 = workspace / "report.pdf"
    f2 = workspace / "photo.png"
    f1.write_text("pdf contents")
    f2.write_text("png contents")

    categories = {"Documents": ["pdf"], "Images": ["png"]}
    organizer = FileOrganizer(categories=categories)

    # 1. Execute Organization
    succ, fail = organizer.execute_organization(workspace)
    assert len(succ) == 2

    # Verify moved state
    doc_path = workspace / "Documents" / "report.pdf"
    img_path = workspace / "Images" / "photo.png"
    assert doc_path.exists()
    assert img_path.exists()
    assert not f1.exists()

    # Record to DB history
    batch_id = repo.generate_batch_id()
    repo.record_batch_operations(batch_id, "ORGANIZE", succ, fail)

    # 2. Revert using UndoManager
    batch_info = undo_mgr.get_last_undoable_batch_info()
    assert batch_info is not None
    assert batch_info["batch_id"] == batch_id

    ok, summary, restored, failed_records = undo_mgr.undo_last_operation()

    assert ok
    assert len(restored) == 2
    assert len(failed_records) == 0

    # 3. Verify files restored to original locations
    assert f1.exists()
    assert f2.exists()
    assert not doc_path.exists()
    assert not img_path.exists()

    # 4. Verify batch cannot be undone twice
    next_info = undo_mgr.get_last_undoable_batch_info()
    assert next_info is None


def test_undo_batch_rename_operation(undo_env):
    workspace = undo_env["dir"]
    repo = undo_env["repo"]
    undo_mgr = undo_env["undo_mgr"]

    file1 = workspace / "data_01.csv"
    file1.write_text("col1,col2")

    files = [file1]
    plan = BatchRenamer.generate_preview(files, prefix="ARCHIVE_")
    succ, fail = BatchRenamer.execute_renaming(plan)

    renamed_file = workspace / "ARCHIVE_data_01.csv"
    assert renamed_file.exists()
    assert not file1.exists()

    batch_id = repo.generate_batch_id()
    repo.record_batch_operations(batch_id, "RENAME", succ, fail)

    # Execute undo
    ok, summary, restored, failed_records = undo_mgr.undo_last_operation()

    assert ok
    assert len(restored) == 1
    assert file1.exists()
    assert not renamed_file.exists()


def test_undo_prevents_overwrite_if_original_path_occupied(undo_env):
    workspace = undo_env["dir"]
    repo = undo_env["repo"]
    undo_mgr = undo_env["undo_mgr"]

    f1 = workspace / "document.pdf"
    f1.write_text("original pdf")

    organizer = FileOrganizer(categories={"Documents": ["pdf"]})
    succ, fail = organizer.execute_organization(workspace)

    doc_dest = workspace / "Documents" / "document.pdf"
    assert doc_dest.exists()

    batch_id = repo.generate_batch_id()
    repo.record_batch_operations(batch_id, "ORGANIZE", succ, fail)

    # Simulate an external file taking the original path location
    f1.write_text("new file at original path")

    # Attempt undo
    ok, summary, restored, failed_records = undo_mgr.undo_last_operation()

    # Undo should fail to prevent overwriting the new file
    assert len(failed_records) == 1
    assert "occupied by another file" in failed_records[0]["error"]
    assert doc_dest.exists()  # Destination file remains untouched