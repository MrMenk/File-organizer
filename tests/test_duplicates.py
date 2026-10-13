import pytest
from pathlib import Path
from core.duplicate_detector import DuplicateDetector


@pytest.fixture
def dup_dir(tmp_path):
    """Fixture creating a temporary directory with distinct and identical files."""
    d = tmp_path / "dup_test"
    d.mkdir()

    content_a = b"Exact duplicate content block A"
    content_b = b"Exact duplicate content block B"
    content_unique = b"Unique file content block"

    # Group 1: 3 identical files
    (d / "original_a.txt").write_bytes(content_a)
    (d / "copy1_a.txt").write_bytes(content_a)
    (d / "copy2_a.txt").write_bytes(content_a)

    # Group 2: 2 identical files
    (d / "photo1.jpg").write_bytes(content_b)
    (d / "photo1_copy.jpg").write_bytes(content_b)

    # Unique file
    (d / "unique.txt").write_bytes(content_unique)

    return d


def test_calculate_file_hash(dup_dir):
    detector = DuplicateDetector()
    hash1 = detector.calculate_file_hash(dup_dir / "original_a.txt")
    hash2 = detector.calculate_file_hash(dup_dir / "copy1_a.txt")
    hash_unique = detector.calculate_file_hash(dup_dir / "unique.txt")

    assert hash1 is not None
    assert hash1 == hash2
    assert hash1 != hash_unique


def test_scan_duplicates(dup_dir):
    detector = DuplicateDetector()
    results = detector.scan_directory(dup_dir)

    # Should detect 2 duplicate groups (Group A and Group B)
    assert len(results) == 2

    counts = {len(group["files"]) for group in results}
    assert 3 in counts  # Group A has 3 copies
    assert 2 in counts  # Group B has 2 copies


def test_no_false_duplicates_by_filename(tmp_path):
    d = tmp_path / "filename_test"
    d.mkdir()

    # Same filename, different content
    (d / "data.txt").write_text("Content version 1")
    sub = d / "sub"
    sub.mkdir()
    (sub / "data.txt").write_text("Content version 2")

    detector = DuplicateDetector()
    results = detector.scan_directory(d, recursive=True)

    # Content differs, so no duplicates should be reported
    assert len(results) == 0