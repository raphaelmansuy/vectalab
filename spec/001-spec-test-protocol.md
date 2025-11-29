# Test and Improvement Protocol for Vectalab

## Overview
This protocol establishes a systematic test and improvement process for Vectalab, focusing on improving the vectorization algorithm to produce SVGs that closely match the original vector graphics when rendered.

## Quick Start

### Prerequisites
- Vectalab installed with dependencies: `pip install -e .`
- Test infrastructure ready: `mkdir -p test_data/{svg_mono,svg_multi,png_mono,png_multi,vectalab_mono,vectalab_multi}`

### One-Command Baseline Setup
```bash
# Step 1: Download test icons
python scripts/download_test_svgs.py

# Step 2: Convert to PNG
python scripts/convert_svg_to_png.py

# Step 3: Quick 6-icon baseline (fast)
python scripts/quick_baseline.py

# Step 4: Generate comparison report
python scripts/compare_results.py
```

This will produce: `test_data/baseline_report.txt` with SSIM metrics.

## Test Case Setup

### 1. SVG Icon Selection
- **Monochrome Library**: Feather Icons (https://feathericons.com/)
  - 20 icons: circle, square, triangle, star, heart, user, home, search, settings, camera, cloud, sun, moon, wind, rain, coffee, code, terminal, cpu, database
  - Open-source, simple, stroke-based designs
  - Ideal for testing clean vectorization

- **Multi-Color Library**: Font Awesome Brands (https://fontawesome.com/icons)
  - 20 icons: github, twitter, facebook, instagram, youtube, linkedin, google, apple, microsoft, amazon, slack, spotify, netflix, airbnb, dropbox, trello, atlassian, jira, bitbucket, gitlab
  - Complex color palettes and fills
  - Tests ability to handle multi-color assets

- **Complex Scenes**: W3C SVG Test Suite & Samples
  - 10 scenes: tiger, car, gallardo, tommek_Car, compuserver_msn_Ford_Focus, juanmontoya_lingerie, scimitar, rg1024_green_grapes, rg1024_Presentation_with_girl, rg1024_metal_effect
  - High complexity, gradients, many paths, realistic illustrations
  - Tests performance and detail preservation

### 2. Download Process
```bash
python scripts/download_test_svgs.py
```
- Downloads from official GitHub repositories
- Stores in: `test_data/svg_mono/` and `test_data/svg_multi/`

### 3. PNG Conversion
```bash
python scripts/convert_svg_to_png.py
```
- Converts each SVG to PNG using CairoSVG
- Resolution: 256x256 pixels (balance of detail and speed)
- Outputs to: `test_data/png_mono/` and `test_data/png_multi/`
- These serve as reference/baseline images

## Vectorization Testing

### 4. Vectalab Processing

**Full Test Suite** (all 20 icons):
```bash
python scripts/run_vectalab_test.py
```
Settings: HIFI method, balanced quality

**Quick Baseline** (6 icons, fast):
```bash
python scripts/quick_baseline.py
```
Settings: HIFI method, figma quality (fastest)

**Direct Library** (alternative, no CLI):
```bash
python scripts/vectorize_direct.py
```
Settings: SAM segmentation, auto device

Outputs to: `test_data/vectalab_mono/` and `test_data/vectalab_multi/`

### 5. Quality Assessment
```bash
python scripts/compare_results.py
```

Analysis:
- Renders original and vectorized SVGs to PNG (same resolution)
- Calculates SSIM (Structural Similarity Index) for each icon
- Computes statistics: mean, min, max, std dev
- Generates detailed report: `test_data/baseline_report.txt`

## OODA Loop Improvement Process

This protocol follows the OODA Loop (Observe, Orient, Decide, Act) for continuous improvement.

### 6. Observe (Baseline Establishment)
1. Run vectorization on the full test set (20 mono + 20 multi icons).
2. Execute comparison script to generate metrics.
3. Review `test_data/baseline_report.txt` to identify:
   - Average SSIM, PSNR, MSE for mono and multi-color.
   - Icons with lowest scores (problematic cases).
   - Processing time patterns.

### 7. Orient (Analysis)
1. Analyze failure cases (low SSIM/PSNR icons).
2. Visually inspect the difference between original and vectorized images.
3. Identify common issues (e.g., stroke width, corner handling, color reduction, gradient loss).
4. Hypothesize the root cause in the algorithm (e.g., segmentation parameters, tracing thresholds).

### 8. Decide (Planning)
1. Select a specific issue to address.
2. Formulate a plan for algorithm refinement.
3. Decide on the scope of changes (parameter tuning vs. code refactoring).
4. Create a hypothesis for the expected improvement.

### 9. Act (Implementation & Testing)
1. Implement the targeted fix in the core algorithm.
2. Test on problematic icons first using `quick_baseline.py`.
3. Verify no regressions on known good icons.
4. Run the full test suite `run_vectalab_test.py`.
5. Compare results with the previous baseline.
6. Commit changes if metrics improve.
7. Repeat the loop.

### 10. Iterative Testing Commands
```bash
# After each algorithm change:
python scripts/quick_baseline.py       # Quick validation
python scripts/compare_results.py      # Check metrics
# Review test_data/baseline_report.txt
# Track improvements in log files
```

### 9. Performance Monitoring
- Record processing time per icon (output by scripts)
- Monitor memory usage for large batches
- Balance quality vs speed trade-offs
- Target: < 30 seconds per icon on standard hardware

## Test Metrics

### SSIM (Structural Similarity Index)
- Measures perceived similarity: 0% (completely different) to 100% (identical)
- Formula: SSIM = (2μ₁μ₂ + c₁)(2σ₁₂ + c₂) / ((μ₁² + μ₂²+ c₁)(σ₁² + σ₂² + c₂))
- Accounts for: luminance, contrast, structure

### PSNR (Peak Signal-to-Noise Ratio)
- Measures the ratio between the maximum possible power of a signal and the power of corrupting noise.
- Expressed in decibels (dB). Higher is better.
- Typical values for good quality images are between 30 and 50 dB.

### MSE (Mean Squared Error)
- Measures the average of the squares of the errors.
- Lower is better. 0 means identical images.

### Success Criteria
- **Monochrome**: Average SSIM ≥ 99.8%
- **Multi-Color**: Average SSIM ≥ 99.5% (more challenging)
- **Complex Scenes**: Average SSIM ≥ 90.0% (very challenging)
- **Worst Case**: No icon should drop below 95% (80% for complex)
- **Processing**: < 30 seconds per icon (< 120s for complex)

## Files and Scripts

### Data Download
- `scripts/download_test_svgs.py` - Fetch from GitHub

### Preparation
- `scripts/convert_svg_to_png.py` - SVG → PNG conversion

### Vectorization
- `scripts/run_vectalab_test.py` - Full suite (all 20 icons)
- `scripts/quick_baseline.py` - Fast 6-icon baseline
- `scripts/vectorize_direct.py` - Direct core library call

### Analysis
- `scripts/compare_results.py` - SSIM calculation and reporting
- `test_data/baseline_report.txt` - Generated metrics report

### Documentation
- `TEST_PROTOCOL_README.md` - Extended reference guide
- `spec/001-spec-test-protocol.md` - This file

## Troubleshooting

### CLI Hangs
If `vectalab convert` command hangs:
```bash
# Use direct core library instead
python scripts/vectorize_direct.py
```

### Memory Issues
- Reduce batch size
- Use figma quality preset instead of ultra
- Process icons sequentially instead of batch

### Import Errors
```bash
# Reinstall development mode
pip install -e .
```

## Next Steps

1. Run quick baseline to establish current metrics
2. Identify 2-3 icons with lowest SSIM
3. Analyze what makes them difficult
4. Implement first improvement
5. Track improvement with re-runs
6. Document changes in git commits

## Future Extensions

- Expand test set to 50+ icons
- Add LPIPS (perceptual similarity) metric
- Test with different resolutions (128x128, 512x512)
- Include edge cases (thick strokes, thin lines, complex gradients)
- Automated CI/CD regression testing
- Visual diff reports highlighting differences</content>
<parameter name="filePath">/Users/raphaelmansuy/Github/03-working/vmagic/spec/001-spec-test-protocol.md
