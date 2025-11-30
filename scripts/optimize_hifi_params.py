#!/usr/bin/env python3
"""
Optimize HIFI parameters for complex scenes.
"""

import os
import subprocess
import time
import json
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim
from skimage.metrics import peak_signal_noise_ratio as psnr
import cairosvg
import tempfile

# Define parameter sets to test
PARAM_SETS = {
    "ultra_baseline": {
        "mode": "polygon",
        "layer_difference": "1",
        "color_precision": "8",
        "filter_speckle": "0"
    },
    "ultra_spline": {
        "mode": "spline",
        "layer_difference": "1",
        "color_precision": "8",
        "filter_speckle": "0"
    },
    "sota_candidate": {
        "mode": "spline",
        "layer_difference": "0", # Try 0 for max detail
        "color_precision": "8",
        "filter_speckle": "0",
        "path_precision": "10"
    }
}

def render_svg_to_png(svg_path, png_output, size=512):
    """Render SVG to PNG using CairoSVG."""
    try:
        cairosvg.svg2png(
            url=svg_path,
            write_to=png_output,
            output_width=size,
            output_height=size
        )
        return True
    except Exception as e:
        # print(f"Error rendering {svg_path}: {e}")
        return False

def calculate_metrics(img1_path, img2_path):
    """Calculate SSIM and PSNR."""
    try:
        img1 = Image.open(img1_path).convert('RGB')
        img2 = Image.open(img2_path).convert('RGB')
        
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)
        
        arr1 = np.array(img1)
        arr2 = np.array(img2)
        
        s = ssim(arr1, arr2, channel_axis=2, data_range=255)
        p = psnr(arr1, arr2, data_range=255)
        
        return s, p
    except Exception as e:
        return 0, 0

def run_test(input_png, output_svg, preset):
    """Run vectalab with specific preset."""
    cmd = [
        "vectalab", "convert",
        input_png, output_svg,
        "--method", "hifi",
        "--quality", preset,
        "--force"
    ]
    try:
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        duration = time.time() - start_time
        if result.returncode == 0:
            return duration
        else:
            print(f"Error: {result.stderr}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

import argparse

def main():
    parser = argparse.ArgumentParser(description="Optimize HIFI parameters")
    parser.add_argument("--target", type=str, help="Specific target icon name (e.g., 'tiger')")
    args = parser.parse_args()

    # Test images (subset of complex)
    if args.target:
        # Try to find the target in various folders
        candidates = [
            f"test_data/png_complex/{args.target}.png",
            f"test_data/png_mono/{args.target}.png",
            f"test_data/png_multi/{args.target}.png"
        ]
        test_images = [c for c in candidates if os.path.exists(c)]
        if not test_images:
            print(f"Error: Target '{args.target}' not found in test_data/png_*/")
            return
    else:
        test_images = [
            "test_data/png_complex/tiger.png",
            "test_data/png_complex/rg1024_green_grapes.png",
            "test_data/png_complex/rg1024_metal_effect.png"
        ]
    
    presets = ["ultra", "sota_candidate", "ultra_max"]
    
    results = {}
    
    print(f"{'Image':<30} {'Preset':<15} {'SSIM':<8} {'PSNR':<8} {'Time':<8}")
    print("-" * 75)
    
    for png_path in test_images:
        if not os.path.exists(png_path):
            continue
            
        filename = os.path.basename(png_path)
        
        for preset in presets:
            output_dir = f"test_data/vectalab_{preset}"
            os.makedirs(output_dir, exist_ok=True)
            svg_path = os.path.join(output_dir, filename.replace('.png', '.svg'))
            
            duration = run_test(png_path, svg_path, preset)
            
            if duration is not None:
                # Render and compare
                with tempfile.TemporaryDirectory() as tmpdir:
                    rendered_png = os.path.join(tmpdir, "rendered.png")
                    if render_svg_to_png(svg_path, rendered_png):
                        s, p = calculate_metrics(png_path, rendered_png)
                        print(f"{filename[:30]:<30} {preset:<15} {s*100:.2f}%   {p:.2f} dB   {duration:.2f}s")
                        
                        if preset not in results:
                            results[preset] = {"ssim": [], "psnr": [], "time": []}
                        results[preset]["ssim"].append(s)
                        results[preset]["psnr"].append(p)
                        results[preset]["time"].append(duration)
    
    print("-" * 75)
    print("Summary:")
    for preset in presets:
        if preset in results and results[preset]["ssim"]:
            avg_ssim = np.mean(results[preset]["ssim"]) * 100
            avg_psnr = np.mean(results[preset]["psnr"])
            avg_time = np.mean(results[preset]["time"])
            print(f"{preset:<15}: SSIM={avg_ssim:.2f}%, PSNR={avg_psnr:.2f} dB, Time={avg_time:.2f}s")

if __name__ == "__main__":
    main()
