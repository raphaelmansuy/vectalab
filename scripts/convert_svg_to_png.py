#!/usr/bin/env python3
"""
Convert SVG files to PNG for testing.
"""

import os
import cairosvg

def convert_svg_to_png(svg_path, png_path, size=256):
    """Convert SVG to PNG with specified size."""
    try:
        cairosvg.svg2png(
            url=svg_path,
            write_to=png_path,
            output_width=size,
            output_height=size
        )
        print(f"Converted: {svg_path} -> {png_path}")
    except Exception as e:
        print(f"Failed to convert {svg_path}: {e}")

def main():
    # Convert monochrome SVGs
    svg_mono_dir = "test_data/svg_mono"
    png_mono_dir = "test_data/png_mono"

    for filename in os.listdir(svg_mono_dir):
        if filename.endswith('.svg'):
            svg_path = os.path.join(svg_mono_dir, filename)
            png_filename = filename.replace('.svg', '.png')
            png_path = os.path.join(png_mono_dir, png_filename)
            convert_svg_to_png(svg_path, png_path)

    # Convert multi-color SVGs
    svg_multi_dir = "test_data/svg_multi"
    png_multi_dir = "test_data/png_multi"

    for filename in os.listdir(svg_multi_dir):
        if filename.endswith('.svg'):
            svg_path = os.path.join(svg_multi_dir, filename)
            png_filename = filename.replace('.svg', '.png')
            png_path = os.path.join(png_multi_dir, png_filename)
            convert_svg_to_png(svg_path, png_path)

    # Convert complex SVGs
    svg_complex_dir = "test_data/svg_complex"
    png_complex_dir = "test_data/png_complex"

    if os.path.exists(svg_complex_dir):
        for filename in os.listdir(svg_complex_dir):
            if filename.endswith('.svg'):
                svg_path = os.path.join(svg_complex_dir, filename)
                png_filename = filename.replace('.svg', '.png')
                png_path = os.path.join(png_complex_dir, png_filename)
                # Use larger size for complex images to preserve detail
                convert_svg_to_png(svg_path, png_path, size=512)

if __name__ == "__main__":
    main()