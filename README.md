# Vectalab - Professional High-Fidelity Image Vectorization

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Website](https://img.shields.io/badge/website-vectalab.com-blue)](https://vectalab.com)

**Vectalab** is a professional high-fidelity image vectorization library that converts raster images (PNG, JPG) to scalable vector graphics (SVG) with **99.8%+ structural similarity**.

## Features

- 🎯 **High Fidelity**: Achieves 99.8%+ SSIM in PNG → SVG → PNG roundtrip
- 🚀 **Fast**: Leverages vtracer (Rust) for efficient base vectorization
- 🎨 **Pure SVG Output**: No embedded raster images - true vector graphics
- 🔧 **Multiple Methods**: SAM-based segmentation, Bayesian optimization, or hybrid approach

## Installation

```bash
pip install -r requirements.txt
```

### Dependencies

- Python 3.10+
- PyTorch
- OpenCV
- vtracer
- cairosvg
- scikit-image

## Quick Start

### High-Fidelity Vectorization (Recommended)

```python
from vectalab import vectorize_high_fidelity

# Convert image to SVG with 99.8%+ fidelity
svg_path, ssim = vectorize_high_fidelity(
    "input.png",
    "output.svg",
    target_ssim=0.998
)
print(f"Achieved {ssim*100:.2f}% similarity")
```

### Basic Usage

```python
from vectalab import Vectalab

# Initialize vectorizer
vm = Vectalab(method="bayesian")

# Vectorize image
svg_content = vm.vectorize("input.png")

# Save SVG
with open("output.svg", "w") as f:
    f.write(svg_content)
```

### Command Line

Vectalab provides a beautiful, user-friendly command-line interface with rich help and progress indicators.

```bash
# Show help
vectalab --help

# Convert an image to SVG (auto-detects best settings)
vectalab convert logo.png

# Specify output path
vectalab convert photo.jpg output.svg

# Fast conversion for previews
vectalab convert image.png -q fast

# Maximum quality with custom target SSIM
vectalab convert icon.png -m hifi -t 0.999

# Get image information and recommendations
vectalab info image.png

# Compare original and rendered images
vectalab compare original.png rendered.png

# Render SVG back to PNG for verification
vectalab render output.svg output.png
```

#### Available Commands

| Command | Description |
|---------|-------------|
| `convert` | 🎨 Convert an image to high-fidelity SVG |
| `info` | 📊 Display image information and recommendations |
| `compare` | 📏 Compare two images with similarity metrics |
| `render` | 🖼️ Render SVG to PNG for verification |

#### Convert Options

| Option | Short | Description |
|--------|-------|-------------|
| `--method` | `-m` | Vectorization method: `hifi`, `bayesian`, `sam` |
| `--quality` | `-q` | Quality preset: `fast`, `balanced`, `ultra` |
| `--target` | `-t` | Target SSIM (0.0-1.0, default: 0.998) |
| `--device` | `-d` | Compute device: `auto`, `cpu`, `cuda`, `mps` |
| `--verbose` | `-v` | Show detailed progress |
| `--quiet` | | Suppress output |
| `--force` | `-f` | Overwrite existing output |

## Methods

### 1. High-Fidelity (`hifi`)
Best for logos, icons, and graphics requiring pixel-perfect reproduction.
- Uses vtracer for base vectorization
- Adds micro-rectangle corrections for edge antialiasing
- Achieves 99.8%+ SSIM

### 2. Bayesian (`bayesian`)
Best for general-purpose vectorization with smooth curves.
- Differentiable rendering with SDF-based rasterization
- Optimizes path positions using gradient descent
- Good balance of quality and file size

### 3. SAM-Based (`sam`)
Best for complex images with distinct regions.
- Uses Segment Anything Model for region detection
- Traces contours with Bezier curves
- Requires SAM model weights

## Project Structure

```
vectalab/
├── vectalab/            # Main package
│   ├── __init__.py
│   ├── core.py          # Vectalab main class
│   ├── hifi.py          # High-fidelity vectorization
│   ├── bayesian.py      # Bayesian optimization
│   ├── segmentation.py  # SAM-based segmentation
│   ├── tracing.py       # Contour tracing
│   ├── output.py        # SVG output generation
│   └── cli.py           # Command-line interface
├── tests/               # Test suite
├── docs/                # Documentation
├── examples/            # Example images
├── models/              # Model weights (SAM)
└── requirements.txt
```

## Performance

| Metric | Achieved | Target |
|--------|----------|--------|
| SSIM | 99.81% | ≥99.8% ✅ |
| PSNR | 46.33 dB | ≥38 dB ✅ |
| ΔE (Color) | 0.99 | <1.2 ✅ |

## Algorithm

The high-fidelity approach combines:

1. **Base Vectorization**: vtracer with ultra-quality settings (~99.4% SSIM)
2. **Error Detection**: Identify pixels with error > threshold
3. **Edge Correction**: Add micro-rectangles for high-error pixels (~1-2% of image)
4. **Result**: Pure SVG achieving 99.8%+ fidelity

See [docs/algorithm.md](docs/algorithm.md) for detailed algorithm description.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits

- [vtracer](https://github.com/visioncortex/vtracer) - Rust vectorization library
- [Segment Anything](https://github.com/facebookresearch/segment-anything) - Meta's SAM model
- Algorithm based on James Diebel's PhD thesis on Bayesian image vectorization
