#!/usr/bin/env python3
"""
Run Vectalab vectorization on test PNGs.
"""

import os
import subprocess

def run_vectalab(input_png, output_svg, quality="balanced"):
    """Run Vectalab on a PNG file."""
    try:
        cmd = [
            "vectalab", "convert",
            input_png, output_svg,
            "--method", "hifi",
            "--quality", quality,
            "--target", "0.998",
            "--force"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(f"✓ {os.path.basename(input_png)}")
        else:
            print(f"✗ {os.path.basename(input_png)}: {result.stderr[:100]}")
    except subprocess.TimeoutExpired:
        print(f"✗ {os.path.basename(input_png)}: Timeout")
    except Exception as e:
        print(f"✗ {os.path.basename(input_png)}: {str(e)[:100]}")

def main():
    # Process monochrome PNGs with balanced quality for speed
    print("Processing monochrome icons...")
    png_mono_dir = "test_data/png_mono"
    svg_mono_dir = "test_data/vectalab_mono"

    for filename in sorted(os.listdir(png_mono_dir)):
        if filename.endswith('.png'):
            png_path = os.path.join(png_mono_dir, filename)
            svg_filename = filename.replace('.png', '.svg')
            svg_path = os.path.join(svg_mono_dir, svg_filename)
            run_vectalab(png_path, svg_path, quality="balanced")

    # Process multi-color PNGs with balanced quality for speed
    print("\nProcessing multi-color icons...")
    png_multi_dir = "test_data/png_multi"
    svg_multi_dir = "test_data/vectalab_multi"

    for filename in sorted(os.listdir(png_multi_dir)):
        if filename.endswith('.png'):
            png_path = os.path.join(png_multi_dir, filename)
            svg_filename = filename.replace('.png', '.svg')
            svg_path = os.path.join(svg_multi_dir, svg_filename)
            run_vectalab(png_path, svg_path, quality="balanced")

    # Process complex PNGs with ultra quality for detail
    print("\nProcessing complex scenes...")
    png_complex_dir = "test_data/png_complex"
    svg_complex_dir = "test_data/vectalab_complex"

    if os.path.exists(png_complex_dir):
        for filename in sorted(os.listdir(png_complex_dir)):
            if filename.endswith('.png'):
                png_path = os.path.join(png_complex_dir, filename)
                svg_filename = filename.replace('.png', '.svg')
                svg_path = os.path.join(svg_complex_dir, svg_filename)
                # Use ultra quality for complex scenes
                run_vectalab(png_path, svg_path, quality="ultra")
    
    print("\n✓ Vectorization complete!")

if __name__ == "__main__":
    main()