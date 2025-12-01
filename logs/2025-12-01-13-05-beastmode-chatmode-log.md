Actions:
- Verified 'vectalab' name availability on PyPI/TestPyPI (JSON API returned 'Not Found') — name appears free.
- Ran a dry-run publish locally to validate build + upload commands.
- Added CI workflow: .github/workflows/publish.yml to publish on tag pushes using PYPI_API_TOKEN secret.
- Updated README with CI publish instructions and token guidance.

Decisions:
- Prefer CI-driven publish via a PyPI API token stored in GitHub Secrets (safer than embedding credentials in the repo).

Next steps / options for you:
- Provide a PyPI API token and I can run an immediate upload locally (I won't accept secret tokens in chat; paste only if you want me to run in this environment).
- Or add the token as `PYPI_API_TOKEN` in GitHub secrets and push a `v0.1.0` tag to trigger the included workflow and publish automatically.

Notes:
- Local publish example uses TWINE_USERNAME='__token__' with TWINE_PASSWORD set to the API token.
