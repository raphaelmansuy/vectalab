# Logo Quality Metrics Update (v2)

## Changes
- Implemented `compute_edge_similarity` in `vectalab/quality.py` using dilated Canny edge detection (IoU).
- Implemented `compute_color_accuracy` in `vectalab/quality.py` using CIELAB Delta E (CIE76).
- Updated `vectalab/cli.py` to display "Edge Accuracy" and "Color Error (ΔE)".

## Verification
- Tested with `google.png`:
  - **Edge Accuracy**: 77.41% (This seems low, but edge IoU is a very strict metric. Even a 1px shift drops it significantly. It's useful for relative comparison).
  - **Color Error (ΔE)**: 1.34 (Green/Good). This confirms the color palette reduction is accurate.

## Insight
These new metrics provide a multi-dimensional view of quality:
1.  **SSIM**: Pixel-perfect match (includes noise).
2.  **Visual Fidelity**: Structural match (ignores noise).
3.  **Edge Accuracy**: Sharpness and alignment of boundaries.
4.  **Color Error**: Accuracy of the palette.
5.  **Complexity**: Cleanliness of the vector paths.
