## CI & Publishing

Publishing instructions, CI workflows, and Trusted Publishing (OIDC) details have moved to a dedicated document: docs/ci_and_publishing.md — see that file for complete instructions, troubleshooting, and examples for both token-based and OIDC publishing.

### Benchmarking

Run comprehensive benchmarks on your own images to evaluate quality and performance.

```bash
# Run the Python benchmark runner (reproducible & auditable)
python scripts/benchmark_runner.py --input-dir ./my_images --mode premium

# Run targeted 80/20 optimization checks
python scripts/benchmark_80_20.py examples/test_logo.png

# Run the Golden Dataset using the runner
python scripts/benchmark_runner.py --input-dir golden_data --mode premium
```

### Python

```python
from vectalab import vectorize_premium

svg_path, metrics = vectorize_premium("input.png", "output.svg")

print(f"Quality: {metrics['ssim']*100:.1f}%")
print(f"Size: {metrics['file_size']/1024:.1f} KB")
print(f"Color accuracy: ΔE={metrics['delta_e']:.2f}")
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--precision, -p` | 2 | Coordinate decimals (1=smallest) |
| `--mode, -m` | auto | `logo`, `photo`, or `auto` |
| `--colors, -c` | auto | Palette size (4-64) |
| `--svgo/--no-svgo` | on | SVGO optimization |

## Cloud Acceleration (Modal)

Vectalab supports offloading heavy segmentation tasks (SAM) to the cloud using [Modal.com](https://modal.com). This enables using the largest models (`vit_h`) on any machine.

1. **Setup**: `modal setup`
2. **Run**: `vectalab convert input.png --method sam --use-modal`

See [Modal Setup Guide](docs/modal_setup.md) for details.

## Documentation

- [CLI Reference](docs/cli.md) - Complete command guide
- [Python API](docs/api.md) - Programmatic usage
- [Examples](docs/examples.md) - Common workflows
- [Algorithm](docs/algorithm.md) - Technical details
- [Benchmarks & Protocol](docs/benchmarks.md) - Reproducible benchmarking and scripts
- [Cloud Setup](docs/modal_setup.md) - Modal integration guide
 - [Model Weights & Download Instructions](docs/MODELS.md) - where to get large model files and how to place them in the repo

<!-- housekeeping note -->
## Scripts cleanup

Some older, ad-hoc testing/analysis scripts were moved into `scripts/archived/` to keep the main `scripts/` directory concise. See `scripts/README.md` for details on which tools live in `scripts/` vs. `scripts/archived/`.


## Architecture

```text
PNG/JPG → Analysis → Preprocessing → vtracer → SVGO → SVG
                ↓           ↓            ↓        ↓
          Type detect   Color quant   Tracing   Compress
          (logo/photo)  Edge-aware    (Rust)    (30-50%)
```

## Requirements

- Python 3.10–3.12 (see pyproject.toml; the package requires >=3.10)
- Node.js (for SVGO, optional but recommended; use an LTS release)

### Core Dependencies

```text
vtracer      # Rust vectorization engine (primary tracing backend)
opencv-python # Image processing
scikit-image # Quality & image metrics
cairosvg     # SVG rendering (used in tests and helpers)
```

Optional/advanced features (SAM segmentation, Modal cloud acceleration):

```text
segment-anything  # SAM-based segmentation (optional)
modal             # cloud acceleration (optional — see docs/modal_setup.md)
torch/torchvision # hardware-accelerated segmentation models
```

## License

MIT License - see [LICENSE](LICENSE)

## Credits

- [vtracer](https://github.com/visioncortex/vtracer) - Rust vectorization
- [SVGO](https://github.com/svg/svgo) - SVG optimization

## Publishing / Releases 🔧

We include a tiny helper script to build and upload releases to PyPI or TestPyPI: `scripts/publish_to_pypi.py`.

Quick usage:

```bash
# Install the tools used by the script
python -m pip install --upgrade build twine

# Dry-run to TestPyPI (default is testpypi)
python scripts/publish_to_pypi.py --dry-run

# Upload to TestPyPI (use env TWINE_USERNAME/TWINE_PASSWORD or ~/.pypirc)
python scripts/publish_to_pypi.py --repository testpypi

# Upload to production PyPI
python scripts/publish_to_pypi.py --repository pypi

# Build, upload to PyPI and tag the current version (reads pyproject.toml)
python scripts/publish_to_pypi.py --repository pypi --tag

# If you want to inspect only the build artifacts and skip upload
python scripts/publish_to_pypi.py --no-upload
```

Notes & recommendations:
- The script expects build artifacts in `dist/` and will run `python -m build` by default.
- Use `--dry-run` to preview commands to be executed before actually uploading.
- For CI, set `TWINE_USERNAME` and `TWINE_PASSWORD` as environment secrets, or configure `~/.pypirc` so `twine` can use that.
- The script supports both TestPyPI (`--repository testpypi`) and production PyPI (`--repository pypi`).
- You can also target a custom PyPI-compatible endpoint using `--repository-url` (e.g. a private index or an internal upload endpoint). This overrides `--repository`.

CI publishing (recommended)
--------------------------

To safely publish to PyPI on releases, add a GitHub Actions secret named `PYPI_API_TOKEN` containing a PyPI API token (create one at https://pypi.org/manage/account/token/). A workflow is included that will run on push tags named like `v*` and publish built distributions automatically.

Typical workflow:

1. Create a PyPI API token (project or account token) on https://pypi.org/account/.
2. Add the token to your repository under Settings → Secrets → Actions → `PYPI_API_TOKEN`.
3. Push a git tag (example: `git tag v0.1.0 && git push origin v0.1.0`). The CI workflow will build & publish.

Workflow note: older versions of the `pypa/gh-action-pypi-publish` action required using `@release/v1` or a specific `@vX.Y.Z` tag instead of `@release`; the workflow in this repo now uses `pypa/gh-action-pypi-publish@release/v1` to avoid the "unable to find version 'release'" error.

Trusted Publishing (OIDC) support
--------------------------------

This workflow now supports GitHub's OpenID Connect (OIDC) / Trusted Publishing flow in case you prefer not to store a PyPI API token in repository secrets.

What changed: the publishing job has job-level permissions so it can request an OIDC id token from GitHub:

```yaml
jobs:
      publish:
            permissions:
                  id-token: write
                  contents: read
            runs-on: ubuntu-latest
            # ...
```

How to use Trusted Publishing (summary):
- Configure a Trusted Publisher on PyPI and link it to your GitHub repo / org. See PyPI's Trusted Publisher docs (https://pypi.org/help/#trusted-publishers) for setup details.
- Once PyPI trusts your repository/organization, the publishing job will request an OIDC id token and exchange it with PyPI to authenticate — no token stored in GitHub secrets required.

Notes:
- Trusted Publishing is more secure but requires extra PyPI-side steps and verification; if you prefer a simpler setup, create a project-scoped PyPI API token and set it as the `PYPI_API_TOKEN` secret for CI.
- If you want I can help configure the PyPI side (e.g., add a trusted publisher) or update the workflow to support both modes depending on whether the secret is present.

Repository protections
---------------------

This repository now has a conservative branch protection policy applied to `main` to reduce accidental direct pushes and require code review for changes. The policy applied includes:

- Require at least 1 approving PR review.
- Disallow force-pushes and branch deletions on `main`.
- Do not enforce admin exemptions (admins are not required to follow the rules in this conservative setup).
- No required CI contexts (you can add these later once GitHub Actions workflows exist).

If you prefer to manage branch protection manually, these are the gh commands used (run locally as a repository admin):

```bash
# Example: conservative (require 1 review, strict status checks w/ no contexts, disallow force pushes)
cat > /tmp/prot.json <<'JSON'
{
      "required_status_checks": { "strict": true, "contexts": [] },
      "enforce_admins": false,
      "required_pull_request_reviews": {
            "dismiss_stale_reviews": true,
            "require_code_owner_reviews": false,
            "required_approving_review_count": 1
      },
      "restrictions": null,
      "allow_force_pushes": false,
      "allow_deletions": false
}
JSON

gh api --method PUT /repos/<ORG_OR_USER>/<REPO>/branches/main/protection --input /tmp/prot.json | cat
```

If you'd like stricter rules (enforce admin rules, require CI contexts, or restrict push access to certain teams), I can update the policy accordingly — tell me what you want and I'll apply it.



