import pytest
from pathlib import Path
from core.organizer import FileOrganizer


@pytest.fixture
def test_dir(tmp_path):
    """Fixture creating a temporary directory with test files."""
    d = tmp_path / "organize_test"
    d.mkdir()

    # Create dummy files across various extensions
    (d / "photo.jpg").write_text("fake image data")
    (d / "document.pdf").write_text("fake pdf content")
    (d / "sheet.xlsx").write_text("fake excel content")
    (d / "script.py").write_text("print('hello')")
    (d / "unknown_file.xyz").write_text("unknown extension data")

    return d


def test_get_category_for_extension():
    categories = {
        "Images": ["jpg", "png"],
        "Documents": ["pdf", "txt"],
    }
    organizer = FileOrganizer(categories=categories, organize_others=True, others_folder="Others")

    assert organizer.get_category_for_extension(".jpg") == "Images"
    assert organizer.get_category_for_extension("PNG") == "Images"
    assert organizer.get_category_for_extension("pdf") == "Documents"
    assert organizer.get_category_for_extension("xyz") == "Others"


def test_dry_run_preview(test_dir):
    categories = {
        "Images": ["jpg"],
        "Documents": ["pdf"],
        "Spreadsheets": ["xlsx"],
        "Code": ["py"],
    }
    organizer = FileOrganizer(categories=categories, organize_others=True, others_folder="Others")

    preview = organizer.generate_preview(test_dir)
    assert len(preview) == 5

    categories_found = {item["category"] for item in preview}
    assert "Images" in categories_found
    assert "Documents" in categories_found
    assert "Spreadsheets" in categories_found
    assert "Code" in categories_found
    assert "Others" in categories_found

    # Ensure no files were actually moved during preview
    assert (test_dir / "photo.jpg").exists()
    assert not (test_dir / "Images" / "photo.jpg").exists()


def test_execute_organization(test_dir):
    categories = {
        "Images": ["jpg"],
        "Documents": ["pdf"],
    }
    organizer = FileOrganizer(categories=categories, organize_others=True, others_folder="Others")

    successful, failed = organizer.execute_organization(test_dir)

    assert len(failed) == 0
    assert (test_dir / "Images" / "photo.jpg").exists()
    assert (test_dir / "Documents" / "document.pdf").exists()
    assert (test_dir / "Others" / "unknown_file.xyz").exists()
    assert not (test_dir / "photo.jpg").exists()


def test_avoid_overwriting_existing_file(test_dir):
    categories = {"Images": ["jpg"]}
    organizer = FileOrganizer(categories=categories)

    # Pre-create conflicting file in target destination
    target_folder = test_dir / "Images"
    target_folder.mkdir()
    (target_folder / "photo.jpg").write_text("existing target content")

    successful, failed = organizer.execute_organization(test_dir)

    assert len(failed) == 0
    # Original target file preserved
    assert (target_folder / "photo.jpg").read_text() == "existing target content"
    # Moved file auto-renamed safely
    assert (target_folder / "photo_1.jpg").exists()