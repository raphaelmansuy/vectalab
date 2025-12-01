Actions:
- Updated scripts/publish_to_pypi.py to allow --repository-url (custom URL override) and improved help text.
- Added test test_custom_repository_url_dry_run in tests/test_publish_script.py and verified tests passing.
- Updated README.md to document --repository-url.

Decisions:
- Opted to add explicit --repository-url flag rather than accepting arbitrary --repository values to keep the CLI clear.

Next steps:
- If preferred, we can add alias support (e.g. mapping 'vectalab' to a known URL) or a GitHub Actions release workflow.

Lessons/insights:
- Custom repository endpoints are common for private package indexes; adding a dedicated flag makes the script clearer and safer.
