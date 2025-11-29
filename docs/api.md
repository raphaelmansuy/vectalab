# Vectalab API Reference

## High-Level API

### `vectorize_high_fidelity`

```python
from vectalab import vectorize_high_fidelity

svg_path, ssim = vectorize_high_fidelity(
    input_path: str,
    output_path: str,
    target_ssim: float = 0.998,
    quality: str = "ultra",
    max_iterations: int = 5,
    verbose: bool = True
) -> Tuple[str, float]
```

**Parameters:**
- `input_path`: Path to input image (PNG, JPG, etc.)
- `output_path`: Path for output SVG
- `target_ssim`: Target SSIM value (default 0.998 = 99.8%)
- `quality`: Base vectorization quality ("fast", "balanced", "ultra")
- `max_iterations`: Maximum refinement iterations
- `verbose`: Print progress messages

**Returns:**
- Tuple of (output_path, achieved_ssim)

**Example:**
```python
svg_path, ssim = vectorize_high_fidelity("logo.png", "logo.svg")
print(f"Achieved {ssim*100:.2f}% similarity")
```

---

### `render_svg_to_png`

```python
from vectalab import render_svg_to_png

png_path = render_svg_to_png(
    svg_path: str,
    png_path: str,
    scale: int = 1
) -> str
```

**Parameters:**
- `svg_path`: Path to input SVG
- `png_path`: Path for output PNG
- `scale`: Scale factor for rendering

**Returns:**
- Path to output PNG

---

## Vectalab Class

```python
from vectalab import Vectalab

vm = Vectalab(
    model_type: str = "vit_b",
    device: str = "cpu",
    method: str = "bayesian",
    **kwargs
)
```

**Parameters:**
- `model_type`: SAM model type ("vit_b", "vit_l", "vit_h")
- `device`: Computation device ("cpu", "cuda", "mps")
- `method`: Vectorization method ("sam", "bayesian")

### Methods

#### `vectorize`

```python
svg_content = vm.vectorize(
    image_path: str,
    output_path: str = None,
    **kwargs
) -> str
```

Vectorize an image to SVG.

**Parameters:**
- `image_path`: Path to input image
- `output_path`: Optional path to save SVG

**Returns:**
- SVG content as string

---

## Bayesian Vectorization

### `optimize_vectorization`

```python
from vectalab import optimize_vectorization

renderer = optimize_vectorization(
    image: np.ndarray,
    device: str = 'cpu',
    num_paths: int = 128,
    num_segments: int = 8,
    num_iterations: int = 500,
    learning_rate: float = 1.0,
    topology_interval: int = 50,
    target_psnr: float = 38.0,
    verbose: bool = True
) -> BayesianVectorRenderer
```

**Parameters:**
- `image`: Input RGB image [H, W, 3] with values 0-255
- `device`: Computation device
- `num_paths`: Number of vector paths
- `num_segments`: Bézier segments per path
- `num_iterations`: Optimization iterations
- `learning_rate`: Adam learning rate
- `topology_interval`: How often to propose topology changes
- `target_psnr`: Target PSNR (algorithm terminates if reached)
- `verbose`: Print progress

**Returns:**
- Optimized BayesianVectorRenderer

---

## Quality Presets

### Fast
```python
quality="fast"
```
- Quick vectorization for previews
- ~98% SSIM typical

### Balanced
```python
quality="balanced"
```
- Good quality/speed tradeoff
- ~99% SSIM typical

### Ultra
```python
quality="ultra"
```
- Maximum fidelity
- 99.4%+ SSIM typical (before corrections)
- 99.8%+ SSIM with corrections
