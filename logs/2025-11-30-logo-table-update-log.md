# Logo Results Table Update

## Changes
- Updated `_show_logo_results` in `vectalab/cli.py` to include a third column "Meaning".
- Added clear, concise explanations for each metric in the results table.
- Enabled table header to show column names (Metric, Value, Meaning).

## Verification
- Tested with `google.png`.
- Table now displays a clear explanation for each metric, helping the user interpret the results (e.g., understanding why SSIM might be lower than Visual Fidelity).

## Example Output
| Metric | Value | Meaning |
| :--- | :--- | :--- |
| Quality (SSIM) | 96.26% | Pixel-perfect similarity (includes noise) |
| Visual Fidelity | 98.67% | Structural similarity (ignores noise) |
| Edge Accuracy | 77.41% | Geometric alignment of boundaries |
