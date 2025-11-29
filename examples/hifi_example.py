#!/usr/bin/env python3
"""
Example: High-fidelity vectorization with Vectalab.

This example demonstrates how to convert a raster image to SVG
with 99.8%+ similarity (SSIM).
"""

import sys
import os
from pathlib import Path

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from vectalab.hifi import vectorize_high_fidelity


def main():
    """Run high-fidelity vectorization example."""
    # Input image (in examples directory)
    input_path = Path(__file__).parent / "ELITIZON_LOGO.jpg"
    
    if not input_path.exists():
        print(f"Error: Image not found at {input_path}")
        return 1
    
    # Output path
    output_svg = Path(__file__).parent / "output_hifi.svg"
    
    print(f"Input: {input_path}")
    print(f"Output SVG: {output_svg}")
    print("=" * 50)
    
    # Run high-fidelity vectorization
    svg_path, achieved_ssim = vectorize_high_fidelity(
        str(input_path),
        str(output_svg),
        target_ssim=0.998,  # Target 99.8% similarity
        verbose=True
    )
    
    # Display results
    svg_size_kb = os.path.getsize(svg_path) / 1024
    
    print("\n" + "=" * 50)
    print("RESULTS:")
    print(f"  SSIM: {achieved_ssim:.4f} ({achieved_ssim*100:.2f}%)")
    print(f"  SVG Size: {svg_size_kb:.1f} KB")
    print(f"  Output: {svg_path}")
    
    if achieved_ssim >= 0.998:
        print("\n✅ Target 99.8% SSIM achieved!")
    else:
        print(f"\n⚠️ SSIM is {achieved_ssim*100:.2f}%, below 99.8% target")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
