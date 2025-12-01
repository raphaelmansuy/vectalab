import os
from pathlib import Path


from scripts import publish_to_pypi


def make_dummy_dist(tmp_path: Path) -> Path:
    root = Path(publish_to_pypi.ROOT)
    dist_dir = root / "dist"
    if not dist_dir.exists():
        dist_dir.mkdir()
    dummy = dist_dir / "dummy-0.0.0.tar.gz"
    dummy.write_text("fake content")
    return dummy


def test_skip_build_dry_run_success(tmp_path: Path):
    # Create a dummy distribution file so the script will attempt upload
    dummy = make_dummy_dist(tmp_path)

    # Use skip-build and dry-run so nothing external runs
    rv = publish_to_pypi.main(["--skip-build", "--dry-run"])
    assert rv == 0
    assert dummy.exists()


def test_custom_repository_url_dry_run(tmp_path: Path):
    # Ensure a custom repository URL can be passed and is accepted (dry-run)
    _ = tmp_path  # not used; keep signature
    rv = publish_to_pypi.main(["--skip-build", "--dry-run", "--repository-url", "https://upload.vectalab.example/legacy/"])
    assert rv == 0
