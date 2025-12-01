Task: README update for accurate Python / dependencies

Actions:
- Inspected `pyproject.toml` and `requirements.txt` to determine canonical Python requirement and significant dependencies.
- Cleaned and updated `/README.md` to show correct Python compatibility (3.10–3.12), clarified Node/SVGO note, and improved dependency list formatting.

Decisions:
- Use a concise Python compatibility string (3.10-3.12) to match classifiers and target versions in `pyproject.toml`.
- Keep README changes minimal and backwards compatible: still uses `pip install vectalab` and notes optional features.

Next steps / Recommendations:
- If you want the README to require a minimum Node.js version explicitly (for SVGO), we can add that.
- Consider bumping `requires-python` in `pyproject.toml` if the package no longer supports older micro-versions.

Notes:
- No code changes were required; only documentation edits.
- Verified the README badge and cleaned up stray characters.
