# Vectalab

> **Professional High-Fidelity Image Vectorization**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Convert raster images (PNG, JPG) to optimized SVG with **97%+ quality** and **70-80% file size reduction**.

## Installation

```bash
pip install vectalab

# Optional: Install SVGO for best compression
npm install -g svgo
```

## Quick Start

```bash
# Vectorize an image (recommended)
vectalab premium logo.png

# Optimize existing SVG
vectalab optimize icon.svg

# Check SVGO status
vectalab svgo-info
```

## Results

| Metric | Value |
|--------|-------|
| Quality (SSIM) | 97-99% |
| File reduction | 70-80% |
| Color accuracy (ΔE) | < 1 (imperceptible) |
| Processing time | 0.2-2s |

## Commands

| Command | Description |
|---------|-------------|
| `premium` | ⭐ SOTA vectorization (recommended) |
| `optimize` | Compress existing SVG with SVGO |
| `convert` | Basic vectorization |
| `logo` | Logo-optimized conversion |
| `info` | Analyze image |
| `svgo-info` | Check SVGO status |
| `benchmark` | 📊 Run performance benchmarks |

## Usage

### CLI

```bash
# Best quality + smallest file
vectalab premium image.png

# Maximum compression
vectalab premium logo.png --precision 1 --mode logo

# Photo vectorization
vectalab premium photo.jpg --mode photo --colors 32

# Compress existing SVG
vectalab optimize icon.svg
```

### Benchmarking

Run comprehensive benchmarks on your own images to evaluate quality and performance.

```bash
# Benchmark a directory of images
vectalab-benchmark --input-dir ./my_images --mode premium

# Run standard test sets
vectalab-benchmark --sets mono multi

# Run the Golden Dataset benchmark (Protocol v2)
vectalab-benchmark --sets golden
```

### Python

```python
from vectalab import vectorize_premium

svg_path, metrics = vectorize_premium("input.png", "output.svg")

print(f"Quality: {metrics['ssim']*100:.1f}%")
print(f"Size: {metrics['file_size']/1024:.1f} KB")
print(f"Color accuracy: ΔE={metrics['delta_e']:.2f}")
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--precision, -p` | 2 | Coordinate decimals (1=smallest) |
| `--mode, -m` | auto | `logo`, `photo`, or `auto` |
| `--colors, -c` | auto | Palette size (4-64) |
| `--svgo/--no-svgo` | on | SVGO optimization |

## Cloud Acceleration (Modal)

Vectalab supports offloading heavy segmentation tasks (SAM) to the cloud using [Modal.com](https://modal.com). This enables using the largest models (`vit_h`) on any machine.

1.  **Setup**: `modal setup`
2.  **Run**: `vectalab convert input.png --method sam --use-modal`

See [Modal Setup Guide](docs/modal_setup.md) for details.

## Documentation

- [CLI Reference](docs/cli.md) - Complete command guide
- [Python API](docs/api.md) - Programmatic usage
- [Examples](docs/examples.md) - Common workflows
- [Algorithm](docs/algorithm.md) - Technical details
- [Benchmark Protocol v2](docs/protocol_v2.md) - Testing methodology
- [Cloud Setup](docs/modal_setup.md) - Modal integration guide

## Architecture

```
PNG/JPG → Analysis → Preprocessing → vtracer → SVGO → SVG
                ↓           ↓            ↓        ↓
          Type detect   Color quant   Tracing   Compress
          (logo/photo)  Edge-aware    (Rust)    (30-50%)
```

## Requirements

- Python 3.10+
- Node.js (for SVGO, optional but recommended)

### Core Dependencies

```
vtracer      # Rust vectorization engine
opencv       # Image processing
scikit-image # Quality metrics
cairosvg     # SVG rendering
```

## License

MIT License - see [LICENSE](LICENSE)

## Credits

- [vtracer](https://github.com/visioncortex/vtracer) - Rust vectorization
- [SVGO](https://github.com/svg/svgo) - SVG optimization
