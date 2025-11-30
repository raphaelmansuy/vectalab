# Logo Quality Metrics Update

## Changes
- Implemented `analyze_svg_content` in `vectalab/quality.py` to count paths and segments.
- Implemented `ssim_perceptual` (Blurred SSIM) in `compute_pixel_metrics` to better reflect human perception of shape vs noise.
- Updated `vectorize_logo_clean` to return these new metrics.
- Updated `vectalab/cli.py` to display "Visual Fidelity" and "Complexity" (segments).

## Verification
- Tested with `google.png`:
  - Raw SSIM: 96.26%
  - Visual Fidelity (Blurred SSIM): 98.67%
  - Complexity: 149 segments

## Insight
The "Visual Fidelity" score (Blurred SSIM) is significantly higher than Raw SSIM, confirming that much of the "error" in Raw SSIM comes from high-frequency differences (pixelation vs smooth curves) that humans ignore or prefer to be smoothed out. This metric should better align with the user's preference for "Clean" results.
