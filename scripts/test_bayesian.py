#!/usr/bin/env python3
"""
Test the Bayesian vectorization method on complex scenes.
"""

import os
import subprocess
import time
from pathlib import Path
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim
from skimage.metrics import peak_signal_noise_ratio as psnr
import cairosvg
import tempfile

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
        print(f"Error rendering {svg_path}: {e}")
        return False

def calculate_metrics(img1_path, img2_path):
    """Calculate SSIM and PSNR between two images."""
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
        print(f"Error calculating metrics: {e}")
        return 0, 0

def run_bayesian_test(input_png, output_svg):
    """Run Vectalab with bayesian method."""
    print(f"Running Bayesian vectorization on {input_png}...")
    start_time = time.time()
    
    cmd = [
        "vectalab", "convert",
        input_png, output_svg,
        "--method", "bayesian",
        "--quality", "ultra",
        "--force"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300) # 5 min timeout
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✓ Success ({duration:.2f}s)")
            return True
        else:
            print(f"✗ Failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ Timeout")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

import argparse

def main():
    parser = argparse.ArgumentParser(description="Test Bayesian vectorization")
    parser.add_argument("--target", type=str, help="Specific target icon name (e.g., 'tiger')")
    args = parser.parse_args()

    # Test on a few complex images
    if args.target:
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
    
    output_dir = "test_data/vectalab_bayesian"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Testing Bayesian Method...")
    print("-" * 50)
    
    for png_path in test_images:
        if not os.path.exists(png_path):
            print(f"Skipping {png_path} (not found)")
            continue
            
        filename = os.path.basename(png_path)
        svg_filename = filename.replace('.png', '.svg')
        svg_path = os.path.join(output_dir, svg_filename)
        
        if run_bayesian_test(png_path, svg_path):
            # Compare results
            with tempfile.TemporaryDirectory() as tmpdir:
                rendered_png = os.path.join(tmpdir, "rendered.png")
                if render_svg_to_png(svg_path, rendered_png):
                    s, p = calculate_metrics(png_path, rendered_png)
                    print(f"  SSIM: {s*100:.2f}%")
                    print(f"  PSNR: {p:.2f} dB")
        print("-" * 50)

if __name__ == "__main__":
    main()
