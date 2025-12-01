Actions:
- Added scripts/publish_to_pypi.py — build + upload helper (dry-run, skip-build, tag support).
- Updated README.md with instructions and examples for publishing to TestPyPI/PyPI.
- Added tests/test_publish_script.py to validate --skip-build + --dry-run behavior.

Decisions:
- Default repository set to TestPyPI to avoid accidental uploads in local runs.
- Script uses python -m build and python -m twine to rely on well-known packaging tools.

Next steps:
- Consider adding CI pipeline step that runs this script using repository secrets for automated releases.
- Optional: add version bumping automation (e.g., automatic changelog & bump tool) if desired.

Lessons/insights:
- Dry-run mode is critical to preview steps before real upload; tests ensure dry-run reliability.
