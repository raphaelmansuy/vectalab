# CLI Reference

## Commands Overview

| Command | Purpose | Best For |
|---------|---------|----------|
| `premium` | SOTA vectorization + SVGO | **Recommended default** |
| `optimize` | Compress existing SVG | Already have SVG |
| `convert` | Basic vectorization | Quick conversion |
| `logo` | Logo-optimized | Flat logos, icons |
| `smart` | Auto size-quality balance | Batch processing |
| `svgo-info` | Check SVGO status | Troubleshooting |

---

## `vectalab premium` ⭐ Recommended

State-of-the-art vectorization with 80/20 optimizations.

```bash
vectalab premium <input> [output] [options]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--target-ssim, -t` | 0.98 | Target SSIM (0.90-1.0) |
| `--precision, -p` | 2 | Coordinate decimals (1=smallest, 8=precise) |
| `--svgo/--no-svgo` | enabled | Apply SVGO optimization |
| `--shapes/--no-shapes` | disabled | Detect shape primitives |
| `--lab/--no-lab` | enabled | Use LAB color metrics |
| `--mode, -m` | auto | Force mode: `logo`, `photo`, `auto` |
| `--colors, -c` | auto | Force palette size (4-64) |

### Examples

```bash
# Basic (auto-detect everything)
vectalab premium logo.png

# Maximum compression
vectalab premium icon.png -p 1 --mode logo

# Photo with more colors
vectalab premium photo.jpg --mode photo -c 32

# Skip SVGO (if not installed)
vectalab premium image.png --no-svgo
```

### Output Metrics

```
Quality (SSIM RGB):  97.65% ✅
Quality (SSIM LAB):  97.86%
Color Accuracy (ΔE): 0.93 (Imperceptible)
File Size:           2.5 KB
Size Reduction:      77.6%
```

**Delta E interpretation:**
- < 1: Imperceptible (excellent)
- 1-2: Barely perceptible (good)
- 2-5: Noticeable on close inspection
- > 5: Clearly different

---

## `vectalab optimize`

Compress existing SVG files with SVGO.

```bash
vectalab optimize <input.svg> [output.svg] [options]
```

### When to Use

```
❌ WRONG: PNG → convert to SVG → vectorize again
   (Produces larger, lower quality files)

✅ RIGHT: PNG → premium → SVG
   OR
✅ RIGHT: existing SVG → optimize → smaller SVG
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--precision, -p` | 2 | Coordinate decimals |
| `--force, -f` | false | Skip confirmation |

### Example

```bash
# Optimize in-place
vectalab optimize icon.svg

# Save to new file
vectalab optimize icon.svg icon_min.svg -p 1
```

---

## `vectalab convert`

Basic high-fidelity vectorization.

```bash
vectalab convert <input> [output] [options]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--method, -m` | hifi | Method: `hifi`, `bayesian`, `sam` |
| `--quality, -q` | ultra | Preset: `figma`, `balanced`, `quality`, `ultra` |
| `--target, -t` | 0.998 | Target SSIM |
| `--device, -d` | auto | Device: `cpu`, `cuda`, `mps` |

### Quality Presets

| Preset | File Size | Quality | Use Case |
|--------|-----------|---------|----------|
| `figma` | Smallest | Good | Design tools |
| `balanced` | Medium | Better | General use |
| `quality` | Larger | High | Print-ready |
| `ultra` | Largest | Highest | Archival |

---

## `vectalab logo`

Optimized for flat logos and icons.

```bash
vectalab logo <input> [output] [options]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--colors, -c` | 8 | Palette size (2-64) |
| `--quality, -q` | 0.95 | Target SSIM |
| `--snap/--no-snap` | enabled | Snap to pure colors |

---

## `vectalab smart`

Auto-balance between file size and quality.

```bash
vectalab smart <input> [output] [options]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--size, -s` | 100 | Target size in KB |
| `--quality, -q` | 0.92 | Minimum SSIM |
| `--iterations, -i` | 5 | Max attempts |

---

## `vectalab info`

Analyze an image file.

```bash
vectalab info <file>
```

### Output

```
📊 Image Analysis
├── Dimensions: 400×200
├── Colors: 3 unique
├── Type: Logo/Icon (flat colors)
├── Recommended: vectalab premium --mode logo
└── Expected size: ~2-5 KB
```

---

## `vectalab compare`

Compare two images.

```bash
vectalab compare <image1> <image2>
```

---

## `vectalab render`

Render SVG to PNG.

```bash
vectalab render <input.svg> [output.png] [--scale N]
```

---

## `vectalab svgo-info`

Check SVGO installation status.

```bash
vectalab svgo-info
```

### Output (when installed)

```
╭─────────┬─────────────┬──────────╮
│ Node.js │ ✓ Installed │ v20.18.1 │
│ SVGO    │ ✓ Installed │ v4.0.0   │
╰─────────┴─────────────┴──────────╯
```

### Installing SVGO

```bash
# macOS
brew install node
npm install -g svgo

# Ubuntu
sudo apt install nodejs npm
npm install -g svgo

# Verify
svgo --version
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VECTALAB_DEVICE` | Default device (cpu/cuda/mps) |
| `VECTALAB_VERBOSE` | Enable verbose output |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (file not found, conversion failed) |
| 2 | Invalid arguments |
| 130 | Interrupted (Ctrl+C) |
