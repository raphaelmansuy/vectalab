# Geometric Icon Fix Log
Date: 2025-11-30
Time: 19:05

## Issue
User reported "wobbly lines" on `alert-octagon`.
Investigation revealed that `vectalab logo` mode (used for icons) produces excessive curves (high curve fraction) for geometric shapes, likely due to tracing anti-aliased edges.
`vectalab premium` mode produces straighter lines but fails on transparent images (produces black square) or produces complex background paths if flattened to white.

## Solution: "Geometric Icon" Strategy
Implemented a new detection and processing pipeline in `vectalab/benchmark.py`:

1.  **Detection**: `is_monochrome_icon(img)`
    - Checks if image is mostly transparent (>95% alpha).
    - Checks if visible pixels have low color variance (Monochrome).
    - Validated on `alert-octagon` (True), `alert-circle` (True), `adobe-after-effects` (False).

2.  **Processing**:
    - Create a temporary **Inverted Image**: White shape on Black background.
    - Run `vectalab premium --mode logo --shapes`.
        - `premium` mode uses SOTA optimization and shape detection (circles, lines).
        - Inverted image forces it to trace the White shape as a foreground object.
    - **Post-processing**:
        - Parse the output SVG.
        - Identify "foreground" paths (White fill).
        - Identify "background" paths (Black fill).
        - Remove background paths.
        - Change foreground paths to the original icon color.
        - Save the clean SVG.

## Results
Verified on `alert-octagon`, `alert-circle`, and `adobe-after-effects`.

| Image | Mode | SSIM | Complexity | Curve Fraction | Notes |
|-------|------|------|------------|----------------|-------|
| `alert-octagon` | Geometric Icon | 100.0% | 133 (was 198) | 45.1% (was 98%) | Straight lines achieved! |
| `alert-circle` | Geometric Icon | 100.0% | 146 | 66.4% | Circles preserved. |
| `adobe-after-effects` | Logo | 99.1% | 332 | 98.5% | Unchanged (correctly identified as complex). |

## Conclusion
The new strategy successfully fixes the "wobbly lines" issue for geometric icons while maintaining 100% SSIM and transparency.
