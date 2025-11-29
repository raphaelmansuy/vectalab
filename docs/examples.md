# Usage Examples

## Basic High-Fidelity Vectorization

```python
from vectalab import vectorize_high_fidelity

# Simple usage - convert logo to SVG
svg_path, ssim = vectorize_high_fidelity("logo.png", "logo.svg")
print(f"Created {svg_path} with {ssim*100:.2f}% similarity")
```

## Batch Processing

```python
from vectalab import vectorize_high_fidelity
from pathlib import Path

input_dir = Path("images")
output_dir = Path("vectors")
output_dir.mkdir(exist_ok=True)

for img_path in input_dir.glob("*.png"):
    svg_path = output_dir / f"{img_path.stem}.svg"
    _, ssim = vectorize_high_fidelity(str(img_path), str(svg_path))
    print(f"{img_path.name}: {ssim*100:.2f}%")
```

## Custom Quality Settings

```python
from vectalab import vectorize_high_fidelity

# Fast mode for quick previews
svg_path, ssim = vectorize_high_fidelity(
    "input.png", 
    "output.svg",
    quality="fast",
    target_ssim=0.95
)

# Ultra mode for maximum fidelity
svg_path, ssim = vectorize_high_fidelity(
    "input.png",
    "output.svg", 
    quality="ultra",
    target_ssim=0.998,
    max_iterations=10
)
```

## Render SVG Back to PNG

```python
from vectalab import vectorize_high_fidelity, render_svg_to_png

# Vectorize
svg_path, _ = vectorize_high_fidelity("input.png", "output.svg")

# Render at 2x scale
render_svg_to_png(svg_path, "output_2x.png", scale=2)
```

## Using Vectalab Class Directly

```python
from vectalab import Vectalab

# Initialize with Bayesian method
vm = Vectalab(method="bayesian", device="cpu")

# Vectorize
svg_content = vm.vectorize("input.png")

# Save
with open("output.svg", "w") as f:
    f.write(svg_content)
```

## Comparing Input and Output

```python
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from vectalab import vectorize_high_fidelity, render_svg_to_png

# Vectorize
svg_path, _ = vectorize_high_fidelity("input.png", "output.svg")

# Render back
render_svg_to_png(svg_path, "output.png")

# Compare
original = cv2.imread("input.png")
rendered = cv2.imread("output.png")

# Calculate SSIM
similarity = ssim(original, rendered, channel_axis=2)
print(f"SSIM: {similarity*100:.2f}%")
```
