import pytest
from pathlib import Path
from core.batch_renamer import BatchRenamer


@pytest.fixture
def rename_dir(tmp_path):
    """Fixture creating a temporary directory with test files for batch renaming."""
    d = tmp_path / "rename_test"
    d.mkdir()

    (d / "vacation_01.jpg").write_text("photo 1")
    (d / "vacation_02.jpg").write_text("photo 2")
    (d / "notes draft.txt").write_text("notes")

    return d


def test_generate_new_name_prefix_suffix(rename_dir):
    p = rename_dir / "vacation_01.jpg"
    new_name = BatchRenamer.generate_new_name(
        source_path=p,
        index=1,
        prefix="2026_",
        suffix="_raw",
        counter_padding=0
    )
    assert new_name == "2026_vacation_01_raw.jpg"


def test_generate_new_name_template(rename_dir):
    p = rename_dir / "notes draft.txt"
    new_name = BatchRenamer.generate_new_name(
        source_path=p,
        index=3,
        custom_template="Doc_{counter}",
        counter_start=10,
        counter_padding=3
    )
    assert new_name == "Doc_012.txt"


def test_preview_rename_detects_conflicts(rename_dir):
    files = [
        rename_dir / "vacation_01.jpg",
        rename_dir / "vacation_02.jpg"
    ]

    # Rule forcing both files to be renamed to the exact same static filename
    plan = BatchRenamer.generate_preview(
        files=files,
        custom_template="fixed_name"
    )

    assert len(plan) == 2
    assert not plan[0]["has_conflict"]
    assert plan[1]["has_conflict"]
    assert "Duplicate destination" in plan[1]["conflict_reason"]


def test_execute_renaming(rename_dir):
    files = sorted(list(rename_dir.glob("*.jpg")))
    plan = BatchRenamer.generate_preview(
        files=files,
        prefix="Summer_",
        counter_padding=0
    )

    successful, failed = BatchRenamer.execute_renaming(plan)

    assert len(failed) == 0
    assert len(successful) == 2
    assert (rename_dir / "Summer_vacation_01.jpg").exists()
    assert (rename_dir / "Summer_vacation_02.jpg").exists()
    assert not (rename_dir / "vacation_01.jpg").exists()