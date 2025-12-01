# scripts/ directory

This folder contains runnable tooling used across the project — benchmarking harnesses, test drivers, comparison and analysis helpers, small utilities, and some older ad-hoc scripts kept in `archived/`.

Organization
- Benchmarking & reporting: session runners and report generators used for SOTA runs and systematic benchmarks.
- Download helpers: utilities and shell helpers for fetching golden datasets and model checkpoints.
- Tests / QA: smoke and integration tests used by contributors and CI.
- Optimization & tuning: utilities to sweep, profile and optimize pipeline parameters.
- Analysis & comparison: scripts used to compare outputs, analyze results, and run diagnostics.
- Examples & runners: small example scripts showing different ways to invoke the library.
- Templates: Jinja templates used for generating benchmark reports and HTML outputs.

If you depend on a removed or moved script, check `scripts/archived/` — that folder contains older or one-off helpers preserved for history.

Files (grouped by category)
---------------------------

Benchmarking & reporting
- `benchmark_runner.py` — Repeatable benchmark & SOTA session runner that computes metrics and generates HTML reports.
- `benchmark_80_20.py` — Focused benchmark demonstrating impact of common 80/20 optimizations (SVGO, shape detection, precision).

Downloads & models
- `download_golden_dataset.py` — Populate `golden_data/` with curated icons/logos/illustrations used for benchmarking.
- `download_test_svgs.py` — Fetch a canonical set of test SVGs (Feather icons, gilbarbara logos, W3C samples) into a local test folder.
- `download_models.sh` — Shell helper for downloading model checkpoints into `models/` using curl/wget.
- `download_sam_model.py` — Python helper for downloading the SAM ViT‑B checkpoint and reporting progress.

Tests / QA
- `check_imports.py` — Smoke-test ensuring core Python imports succeed in the runtime environment.
- `check_alpha.py` — Quick inspector to detect whether PNG test files include an alpha channel.
- `check_sam_quality.py` — Render a SAM-generated SVG and compare it to an original PNG using SSIM/PSNR.
- `test_bayesian.py` — Tests the Bayesian vectorization method on complex scenes.
- `test_combinations.py` — Systematically search preprocessing + vtracer settings to find good combinations.
- `test_modal_real.py` — Integration test for cloud-backed Modal SAM segmentation flows.
- `test_palette.py` — Tests palette reduction before logo vectorization.
- `test_ultra.py` — Runs ultra-quality vtracer settings for diagnostics.

Optimization & tuning
- `optimize_logo.py` — Grid-search logo conversion parameters (quality/colors) and persist best candidate.
- `optimize_hifi_params.py` — Sweep and benchmark HIFI presets across complex scenes.
- `profile_pipeline.py` — Profile pipeline stages (denoise, vtracer, render) to locate bottlenecks.

Analysis & comparison
- `analyze_cartman.py`, `analyze_others.py`, `analyze_problems.py`, `analyze_results.py` — assorted analysis helpers for benchmarking outputs and failure modes.
- `compare_full.py` — Full comparison across multiple configurations / outputs.
- `compare_methods.py` — Compare different vectorization methods on a target sample.
- `compare_results.py` — Compute and summarize SOTA metrics (SSIM, topology, edge, delta‑E) and produce side-by-side comparisons.
- `compare_versions.py` — Helpers for comparing outputs between versions/commits.

Vectorize / runner examples
- `run_sota_session.py` — Orchestrates timestamped parallel SOTA sessions, computes metrics, and generates reports.
- `vectorize_direct.py` — Example showing direct use of the `vectalab` core API (no CLI required).
- `vectorize_with_sam.py` — SAM-based segmentation → polygon → SVG pipeline implementation.
- `convert_svg_to_png.py` — Helper to render SVG files to PNG (useful for tests & comparisons).

Utilities & diagnostics
- `visualize_components.py` — Visualize connected components in PNGs and save color-coded masks.
- assorted helpers: `analyze_*`, `compare_*` and `check_*` scripts described above provide additional diagnostics.

Archived / ad-hoc (preserved for history)
- `archived/` — Older, one-off or previously used helpers retained for reference.
- In the top level of `scripts/` there are a few historically preserved runner/test helpers such as `minimal_test.py`, `quick_baseline.py`, `run_vectalab_test.py`, `run_full_sota_test.py`, `run_sam_modal_test.py`, `run_optimization_modal.py` — these may be retained for reproduction or archived.

Templates
- `templates/` — Jinja2 templates used by `benchmark_runner.py` and report generation.

If you'd like any of the archived items restored into active use, or if you'd prefer the README to highlight different scripts more prominently (e.g., recommended entry points or CI smoke tests), tell me which focus you want and I can tune this file accordingly.
