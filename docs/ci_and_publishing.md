# CI & Publishing

This page explains how the repository handles CI-based publishing to PyPI and Trusted Publishing (OIDC), how to trigger the publish workflow and recommended safe practices.

## Workflow: CI publish

We use a GitHub Actions workflow at `.github/workflows/publish.yml` that runs on tag pushes that match `v*` (for example `v0.1.2`). The workflow:

- Builds distributions using `python -m build --sdist --wheel`.
- Uploads to PyPI using the official PyPA action `pypa/gh-action-pypi-publish@release/v1`.

Trigger via tag (recommended):

```bash
# create an annotated tag and push it
git tag -a v0.1.2 -m "Release v0.1.2"
git push origin v0.1.2
```

The action will use authentication via either:

- `PYPI_API_TOKEN` repository secret (recommended): a project-scoped API token stored in GitHub Secrets. When present, the workflow uses it to authenticate safely.
- OIDC Trusted Publishing: if `PYPI_API_TOKEN` is absent and your PyPI project is configured to trust this repository, the workflow will attempt an OIDC exchange to authenticate. For this the job needs `permissions.id-token: write`.

### Checks & logs

If a publish fails, inspect the workflow run logs in GitHub Actions — they show whether the issue is missing credentials, OIDC issues, duplicate packages, or metadata failures.

## Trusted Publishing (OIDC)

Trusted Publishing allows the workflow to authenticate to PyPI via OIDC (no long-lived secrets required). Requirements:

1. The workflow job must request an id-token. Example (job-level):

```yaml
jobs:
  publish:
    permissions:
      id-token: write
      contents: read
    runs-on: ubuntu-latest
    # ...
```

2. Configure a Trusted Publisher on PyPI and link your GitHub identity (repo or organization) following PyPI docs.

3. Confirm the workflow runs on GitHub-hosted runners (recommended) so tokens are properly available.

If OIDC exchange fails, the logs will usually show a message like:

```
OpenID Connect token retrieval failed: GitHub: missing or insufficient OIDC token permissions
```

This means your workflow needs `id-token: write` at the job level (or top-level permissions) and/or PyPI trust configuration.

## Local helper and alternatives

We also provide `scripts/publish_to_pypi.py` for local or CI-driven manual uploads. The script supports:

- Building sdist + wheel
- Uploading to TestPyPI or PyPI
- `--dry-run`, `--no-upload`, `--skip-build`, `--repository-url`, and `--tag`

Examples

```bash
# dry-run (no network)
python scripts/publish_to_pypi.py --dry-run

# publish to TestPyPI (safe rehearsal)
export TWINE_USERNAME='__token__'
export TWINE_PASSWORD='<TEST_PYPI_TOKEN>'
python scripts/publish_to_pypi.py --repository testpypi

# publish to PyPI using a token
export TWINE_USERNAME='__token__'
export TWINE_PASSWORD='<PROD_PYPI_TOKEN>'
python scripts/publish_to_pypi.py --repository pypi
```

## Troubleshooting tips

- If you see `Unable to find image 'ghcr.io/pypa/gh-action-pypi-publish:release-v1'` the action pulled the container image; wait or re-run.
- If `Trusted publishing exchange failure` appears, check `id-token: write` permission and PyPI trusted publishers configuration.
- If uploads fail with duplicates, consider `skip-existing: true` or bump the version.

---

If you want, I can add a separate TestPyPI workflow or a workflow_dispatch manual trigger — say which you'd prefer.
