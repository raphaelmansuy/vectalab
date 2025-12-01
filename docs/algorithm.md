# Architecture — concise, actionable overview

This short page explains the main Vectalab pipeline in practical terms: how inputs flow through analysis, vectorization, and optimizations — and where to intervene when integrating or tuning.

Core stages (one line each):

- Input analysis — classify image as logo, photo, artwork; measure color count, edge density, and size.
- Preprocessing — edge-preserving denoise, color quantization, and optional color snapping.
- Vectorization — path generation (vtracer / hifi / SAM-based segmentation), smoothing and merge passes.
- Optimizations — coordinate precision reduction, SVGO, shape detection and path merging for size & readability.

Practical rules of thumb:

- Use `premium` for production — it runs iterative refinement and optional SVGO to achieve the best size/quality trade-offs.
- Use `logo` for clean, limited-palette icons where path simplicity matters.
- Use `optimize` for shrinking already-existing SVGs; some filters and embedded assets may be negatively impacted — test before deploying.

Where to tune (developer-focused)

- Controls and low-level knobs live in `vectalab/premium.py`, `vectalab/hifi.py`, and `vectalab/optimizations.py`.
- If you need fewer paths: increase path precision (lower decimals) and enable more aggressive path-merge/simplify.
- If perceptual color accuracy matters: enable LAB metrics and tune palette size rather than only decimal precision.

If you want a deeper dive or reproducible experiments, see the Benchmarks & Protocols page which documents the exact scripts and datasets we use.
