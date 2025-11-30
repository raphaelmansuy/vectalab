#!/usr/bin/env python3
"""
Minimal vectorization test - just 2 icons with ultra-fast settings.
"""

import os
import subprocess
import argparse
import glob

def run_vectalab_simple(input_png, output_svg):
    """Run with minimal settings for fast testing."""
    try:
        cmd = [
            "vectalab", "convert",
            input_png, output_svg,
            "--method", "hifi",
            "--quality", "figma",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True
        return False
    except:
        return False

def main():
    parser = argparse.ArgumentParser(description="Minimal vectorization test")
    parser.add_argument("--icon", type=str, help="Specific icon name to test (e.g., 'tiger' or 'circle')")
    args = parser.parse_args()

    # Default icons if no argument provided
    if args.icon:
        # Search for the icon in png folders
        found = False
        search_paths = [
            f"test_data/png_mono/{args.icon}.png",
            f"test_data/png_multi/{args.icon}.png",
            f"test_data/png_complex/{args.icon}.png"
        ]
        
        icons_to_test = []
        for path in search_paths:
            if os.path.exists(path):
                # Determine output path based on input folder
                if "png_mono" in path:
                    out_dir = "test_data/vectalab_mono"
                elif "png_multi" in path:
                    out_dir = "test_data/vectalab_multi"
                else:
                    out_dir = "test_data/vectalab_complex"
                
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, f"{args.icon}.svg")
                icons_to_test.append((path, out_path))
                found = True
        
        if not found:
            print(f"Error: Icon '{args.icon}' not found in test_data/png_*/")
            return
    else:
        # Default minimal set
        icons_to_test = [
            ("test_data/png_mono/circle.png", "test_data/vectalab_mono/circle.svg"),
            ("test_data/png_multi/github.png", "test_data/vectalab_multi/github.svg"),
        ]

    print(f"Minimal vectorization test ({len(icons_to_test)} icons)...")
    for png_path, svg_path in icons_to_test:
        if not os.path.exists(png_path):
            print(f"Skipping {png_path} (not found)")
            continue
            
        name = os.path.basename(png_path)
        if run_vectalab_simple(png_path, svg_path):
            print(f"✓ {name}")
        else:
            print(f"✗ {name}")

    print("\n✓ Test complete!")

if __name__ == "__main__":
    main()
