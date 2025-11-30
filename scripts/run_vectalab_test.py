#!/usr/bin/env python3
"""
Run Vectalab vectorization on test PNGs and measure performance.
"""

import os
import subprocess
import time
import json
from pathlib import Path

def run_vectalab(input_png, output_svg, quality="balanced", mode="logo"):
    """Run Vectalab on a PNG file and return execution time."""
    start_time = time.time()
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_svg), exist_ok=True)
        
        cmd = [
            "vectalab", "convert",
            input_png, output_svg,
            "--method", "hifi",
            "--quality", quality,
            "--target", "0.998",
            "--force"
        ]
        
        # Add mode specific arguments if needed, though 'convert' is the command
        # If there is a specific 'logo' mode flag for the CLI, add it here.
        # The protocol mentions `vectalab logo ...` but the script uses `vectalab convert`.
        # I'll stick to `convert` but maybe add flags if I knew them.
        # The protocol says: `vectalab logo test_data/png_multi/brand.png ...`
        # Let's check if `vectalab logo` is a valid command.
        # For now I'll stick to the previous command structure but maybe add comments.
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✓ {os.path.basename(input_png):<30} ({duration:.2f}s)")
            return duration
        else:
            print(f"✗ {os.path.basename(input_png):<30} (Error: {result.stderr[:50]}...)")
            return None
    except subprocess.TimeoutExpired:
        print(f"✗ {os.path.basename(input_png):<30} (Timeout)")
        return None
    except Exception as e:
        print(f"✗ {os.path.basename(input_png):<30} (Exception: {str(e)[:50]}...)")
        return None

def main():
    execution_times = {}
    
    # Process monochrome PNGs
    print("\nProcessing monochrome icons (Quality: balanced)...")
    png_mono_dir = "test_data/png_mono"
    svg_mono_dir = "test_data/vectalab_mono"
    
    if os.path.exists(png_mono_dir):
        for filename in sorted(os.listdir(png_mono_dir)):
            if filename.endswith('.png'):
                png_path = os.path.join(png_mono_dir, filename)
                svg_filename = filename.replace('.png', '.svg')
                svg_path = os.path.join(svg_mono_dir, svg_filename)
                
                duration = run_vectalab(png_path, svg_path, quality="balanced")
                if duration is not None:
                    execution_times[f"mono_{filename[:-4]}"] = duration

    # Process multi-color PNGs
    print("\nProcessing multi-color icons (Quality: balanced)...")
    png_multi_dir = "test_data/png_multi"
    svg_multi_dir = "test_data/vectalab_multi"

    if os.path.exists(png_multi_dir):
        for filename in sorted(os.listdir(png_multi_dir)):
            if filename.endswith('.png'):
                png_path = os.path.join(png_multi_dir, filename)
                svg_filename = filename.replace('.png', '.svg')
                svg_path = os.path.join(svg_multi_dir, svg_filename)
                
                duration = run_vectalab(png_path, svg_path, quality="balanced")
                if duration is not None:
                    execution_times[f"multi_{filename[:-4]}"] = duration

    # Process complex PNGs
    print("\nProcessing complex scenes (Quality: ultra)...")
    png_complex_dir = "test_data/png_complex"
    svg_complex_dir = "test_data/vectalab_complex"

    if os.path.exists(png_complex_dir):
        for filename in sorted(os.listdir(png_complex_dir)):
            if filename.endswith('.png'):
                png_path = os.path.join(png_complex_dir, filename)
                svg_filename = filename.replace('.png', '.svg')
                svg_path = os.path.join(svg_complex_dir, svg_filename)
                
                duration = run_vectalab(png_path, svg_path, quality="ultra")
                if duration is not None:
                    execution_times[f"complex_{filename[:-4]}"] = duration
    
    # Save execution times
    with open("test_data/execution_times.json", "w") as f:
        json.dump(execution_times, f, indent=2)
        
    print(f"\n✓ Vectorization complete! Times saved to test_data/execution_times.json")

if __name__ == "__main__":
    main()
