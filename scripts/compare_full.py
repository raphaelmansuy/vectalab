#!/usr/bin/env python3
"""
Compare subset of results.
"""

import os
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim
from skimage.metrics import mean_squared_error as mse
from skimage.metrics import peak_signal_noise_ratio as psnr
import cairosvg
import tempfile

def render_svg_to_png(svg_path, png_output, size=256):
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
    """Calculate SSIM, MSE, and PSNR between two images."""
    try:
        # Open images and convert to RGBA to handle transparency
        img1 = Image.open(img1_path).convert('RGBA')
        img2 = Image.open(img2_path).convert('RGBA')
        
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)
            
        # Create white background
        bg1 = Image.new('RGBA', img1.size, (255, 255, 255, 255))
        bg2 = Image.new('RGBA', img2.size, (255, 255, 255, 255))
        
        # Composite images over white background
        comp1 = Image.alpha_composite(bg1, img1).convert('RGB')
        comp2 = Image.alpha_composite(bg2, img2).convert('RGB')
        
        arr1 = np.array(comp1)
        arr2 = np.array(comp2)
        
        s = ssim(arr1, arr2, channel_axis=2, data_range=255)
        m = mse(arr1, arr2)
        p = psnr(arr1, arr2, data_range=255)
        
        return {"ssim": s, "mse": m, "psnr": p}
    except Exception as e:
        print(f"Error calculating metrics: {e}")
        return None

def main():
    test_set_mono = ['circle.png', 'star.png', 'camera.png']
    test_set_multi = ['google.png', 'github.png', 'apple.png']
    
    print("Comparing results...")
    
    for filename in test_set_mono:
        png_path = f"test_data/png_mono/{filename}"
        svg_path = f"test_data/vectalab_mono/{filename.replace('.png', '.svg')}"
        
        if not os.path.exists(svg_path):
            print(f"Skipping {filename} (SVG not found)")
            continue
            
        with tempfile.NamedTemporaryFile(suffix='.png') as tmp:
            if render_svg_to_png(svg_path, tmp.name):
                metrics = calculate_metrics(png_path, tmp.name)
                if metrics:
                    print(f"{filename}: SSIM={metrics['ssim']:.4f}, PSNR={metrics['psnr']:.2f}")

    for filename in test_set_multi:
        png_path = f"test_data/png_multi/{filename}"
        svg_path = f"test_data/vectalab_multi/{filename.replace('.png', '.svg')}"
        
        if not os.path.exists(svg_path):
            print(f"Skipping {filename} (SVG not found)")
            continue
            
        with tempfile.NamedTemporaryFile(suffix='.png') as tmp:
            if render_svg_to_png(svg_path, tmp.name):
                metrics = calculate_metrics(png_path, tmp.name)
                if metrics:
                    print(f"{filename}: SSIM={metrics['ssim']:.4f}, PSNR={metrics['psnr']:.2f}")

if __name__ == "__main__":
    main()
