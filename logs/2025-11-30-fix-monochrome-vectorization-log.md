# Task Log - Fix Monochrome Icon Vectorization

## Actions
- Investigated "Black Output" issue in SOTA report.
- Identified that `vtracer` with `colormode='color'` was failing on Monochrome images with Alpha (tracing background as black).
- Implemented detection for "Monochrome with Alpha" images in `vectalab/quality.py`.
- Implemented special handling using `vtracer` binary mode with inverted mask (Shape=Black, Background=White).
- Added post-processing to restore the original icon color in the SVG.
- Verified fix on `home.png` and `camera.png`.

## Decisions
- Used `vtracer` binary mode for monochrome icons as it is more robust for 2-color shapes.
- Inverted the binary mask (Shape=Black) because `vtracer` traces Black in binary mode.
- Preserved the original color by replacing `#000000` in the output SVG.

## Next Steps
- Run the full benchmark to generate a clean report.
- Consider improving SSIM metric to handle transparency better (currently compares Black vs Black for transparent areas).

## Lessons
- `vtracer` behavior with `colormode='color'` on simple alpha images can be unpredictable (tracing background).
- Binary mode is reliable for shapes but requires careful mask preparation (Black=Shape).
