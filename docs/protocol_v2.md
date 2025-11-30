# Vectalab Benchmark Protocol v2

## 1. Objective
The goal of this protocol is to establish a rigorous, reproducible, and diverse standard for evaluating the performance of the Vectalab vectorization engine. This v2 protocol expands upon the initial testing strategy by introducing a larger, more "Golden Dataset" covering a wider range of vector graphics types.

## 2. The Golden Dataset
The dataset is curated to represent real-world use cases, categorized into three distinct complexity levels:

### 2.1. Icons (Simple)
*   **Source**: Feather Icons.
*   **Characteristics**: Monochromatic, simple geometric shapes, few paths, no gradients.
*   **Challenge**: Preserving exact corner radii, stroke widths, and alignment.
*   **Size**: ~100 samples.

### 2.2. Logos (Medium)
*   **Source**: Gilbarbara Logos, Simple Icons.
*   **Characteristics**: Multi-colored, specific fonts, precise curves, negative space.
*   **Challenge**: Color separation, text preservation (as shapes), sharp edges.
*   **Size**: ~200 samples.

### 2.3. Illustrations (Complex)
*   **Source**: W3C SVG Test Suite, Twemoji (Twitter Emoji).
*   **Characteristics**: Complex scenes, gradients, many overlapping shapes, fine details.
*   **Challenge**: Handling complexity without exploding file size, topology preservation.
*   **Size**: ~60 samples.

## 3. Methodology

### 3.1. Preparation
1.  **Source**: Start with high-quality SVGs from the Golden Dataset.
2.  **Rasterization**: Convert each SVG to a high-resolution PNG (e.g., 1024x1024 or native size if larger). This ensures we have a "perfect" raster input.
    *   *Tool*: `cairosvg` or `rsvg-convert`.

### 3.2. Vectorization
Run Vectalab on the generated PNGs using various modes:
*   `--mode logo`: For Icons and Logos.
*   `--mode premium`: For Illustrations.
*   `--mode auto`: To test automatic detection.

### 3.3. Evaluation Metrics

#### Quality Metrics
*   **SSIM (Structural Similarity Index)**: Measures visual similarity between the vectorized output (rasterized back to PNG) and the input PNG. Target: > 0.97.
*   **Delta E (Color Difference)**: Measures color accuracy. Target: < 2.0.
*   **Edge Accuracy**: Measures how well the vector paths align with the raster edges (using Canny edge detection comparison).

#### Efficiency Metrics
*   **File Size Reduction**: Comparison of Output SVG size vs. Input PNG size (and vs. Original SVG size).
*   **Path Count**: Number of paths in the output. Lower is generally better for the same visual quality.
*   **Processing Time**: Time taken to vectorize.

#### Topology Metrics
*   **Topology Score**: Measures the preservation of connected components and holes. Important for logos to ensure letters like 'O' or 'A' are not filled in.

## 4. Execution
The benchmark is executed via the `vectalab-benchmark` CLI tool.

```bash
# Run the full Golden Dataset benchmark
vectalab-benchmark --sets golden
```

## 5. Success Criteria
*   **Icons**: SSIM > 0.99, Topology Score = 100%.
*   **Logos**: SSIM > 0.98, Delta E < 1.0.
*   **Illustrations**: SSIM > 0.95, File Size < 50% of PNG.
