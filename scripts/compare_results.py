#!/usr/bin/env python3
"""
Compare original and vectorized SVGs using SSIM and other metrics.
"""

import os
import subprocess
from pathlib import Path
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
        img1 = Image.open(img1_path).convert('RGB')
        img2 = Image.open(img2_path).convert('RGB')
        
        # Convert to same size if needed
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)
        
        arr1 = np.array(img1)
        arr2 = np.array(img2)
        
        # Calculate metrics
        s = ssim(arr1, arr2, channel_axis=2, data_range=255)
        m = mse(arr1, arr2)
        p = psnr(arr1, arr2, data_range=255)
        
        return {
            "ssim": s,
            "mse": m,
            "psnr": p
        }
    except Exception as e:
        print(f"Error calculating metrics: {e}")
        return None

def compare_vectorization(original_svg, vectorized_svg, icon_name, output_dir="test_data/comparisons"):
    """Compare original and vectorized SVGs."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Create temporary PNG files
    with tempfile.TemporaryDirectory() as tmpdir:
        original_png = os.path.join(tmpdir, "original.png")
        vectorized_png = os.path.join(tmpdir, "vectorized.png")
        
        # Render SVGs
        if not render_svg_to_png(original_svg, original_png):
            return None
        if not render_svg_to_png(vectorized_svg, vectorized_png):
            return None
        
        # Calculate metrics
        metrics = calculate_metrics(original_png, vectorized_png)
        
        if metrics:
            return {
                "icon": icon_name,
                "original_svg": original_svg,
                "vectorized_svg": vectorized_svg,
                "ssim": metrics["ssim"],
                "ssim_percent": metrics["ssim"] * 100,
                "mse": metrics["mse"],
                "psnr": metrics["psnr"]
            }
        return None

def main():
    results = []
    
    # Compare monochrome icons
    print("Comparing monochrome icons...")
    svg_mono_dir = "test_data/svg_mono"
    vectalab_mono_dir = "test_data/vectalab_mono"
    
    if os.path.exists(svg_mono_dir):
        for filename in sorted(os.listdir(svg_mono_dir)):
            if filename.endswith('.svg'):
                original_svg = os.path.join(svg_mono_dir, filename)
                vectorized_svg = os.path.join(vectalab_mono_dir, filename)
                
                if os.path.exists(vectorized_svg):
                    result = compare_vectorization(original_svg, vectorized_svg, f"mono_{filename[:-4]}")
                    if result:
                        results.append(result)
                        print(f"  {result['icon']}: SSIM={result['ssim_percent']:.2f}%, PSNR={result['psnr']:.2f}dB")
    
    # Compare multi-color icons
    print("\nComparing multi-color icons...")
    svg_multi_dir = "test_data/svg_multi"
    vectalab_multi_dir = "test_data/vectalab_multi"
    
    if os.path.exists(svg_multi_dir):
        for filename in sorted(os.listdir(svg_multi_dir)):
            if filename.endswith('.svg'):
                original_svg = os.path.join(svg_multi_dir, filename)
                vectorized_svg = os.path.join(vectalab_multi_dir, filename)
                
                if os.path.exists(vectorized_svg):
                    result = compare_vectorization(original_svg, vectorized_svg, f"multi_{filename[:-4]}")
                    if result:
                        results.append(result)
                        print(f"  {result['icon']}: SSIM={result['ssim_percent']:.2f}%, PSNR={result['psnr']:.2f}dB")

    # Compare complex scenes
    print("\nComparing complex scenes...")
    svg_complex_dir = "test_data/svg_complex"
    vectalab_complex_dir = "test_data/vectalab_complex"
    
    if os.path.exists(svg_complex_dir):
        for filename in sorted(os.listdir(svg_complex_dir)):
            if filename.endswith('.svg'):
                original_svg = os.path.join(svg_complex_dir, filename)
                vectorized_svg = os.path.join(vectalab_complex_dir, filename)
                
                if os.path.exists(vectorized_svg):
                    result = compare_vectorization(original_svg, vectorized_svg, f"complex_{filename[:-4]}")
                    if result:
                        results.append(result)
                        print(f"  {result['icon']}: SSIM={result['ssim_percent']:.2f}%, PSNR={result['psnr']:.2f}dB")
    
    # Generate report
    if results:
        print("\n" + "="*70)
        print("BASELINE VECTORIZATION QUALITY REPORT")
        print("="*70)
        
        mono_results = [r for r in results if r['icon'].startswith('mono_')]
        multi_results = [r for r in results if r['icon'].startswith('multi_')]
        complex_results = [r for r in results if r['icon'].startswith('complex_')]
        
        if mono_results:
            mono_ssim = [r['ssim_percent'] for r in mono_results if r['ssim'] is not None]
            mono_psnr = [r['psnr'] for r in mono_results if r['psnr'] is not None]
            # Cap PSNR at 100 for averaging to avoid inf
            mono_psnr_capped = [min(p, 100.0) if not np.isinf(p) else 100.0 for p in mono_psnr]
            
            print(f"\nMonochrome Icons ({len(mono_results)} tested):")
            print(f"  Average SSIM: {np.mean(mono_ssim):.2f}%")
            print(f"  Average PSNR: {np.mean(mono_psnr_capped):.2f} dB")
            print(f"  Min SSIM:     {np.min(mono_ssim):.2f}%")
            print(f"  Max SSIM:     {np.max(mono_ssim):.2f}%")
        
        if complex_results:
            complex_ssim = [r['ssim_percent'] for r in complex_results if r['ssim'] is not None]
            complex_psnr = [r['psnr'] for r in complex_results if r['psnr'] is not None]
            # Cap PSNR at 100 for averaging to avoid inf
            complex_psnr_capped = [min(p, 100.0) if not np.isinf(p) else 100.0 for p in complex_psnr]
            
            print(f"\nComplex Scenes ({len(complex_results)} tested):")
            print(f"  Average SSIM: {np.mean(complex_ssim):.2f}%")
            print(f"  Average PSNR: {np.mean(complex_psnr_capped):.2f} dB")
            print(f"  Min SSIM:     {np.min(complex_ssim):.2f}%")
            print(f"  Max SSIM:     {np.max(complex_ssim):.2f}%")
        
        # Save detailed results
        report_path = "test_data/baseline_report.txt"
        with open(report_path, 'w') as f:
            f.write("VECTALAB VECTORIZATION BASELINE REPORT\n")
            f.write("="*70 + "\n\n")
            f.write("Individual Results:\n")
            f.write("-"*90 + "\n")
            f.write(f"{'Icon':30} {'SSIM':>10} {'PSNR':>10} {'MSE':>10}\n")
            f.write("-"*90 + "\n")
            for r in results:
                psnr_str = "inf" if np.isinf(r['psnr']) else f"{r['psnr']:.2f}"
                f.write(f"{r['icon']:30} {r['ssim_percent']:9.2f}% {psnr_str:>9}dB {r['mse']:9.2f}\n")
            
            f.write("\n" + "="*70 + "\n")
            if mono_results:
                mono_ssim = [r['ssim_percent'] for r in mono_results if r['ssim'] is not None]
                mono_psnr = [r['psnr'] for r in mono_results if r['psnr'] is not None]
                mono_psnr_capped = [min(p, 100.0) if not np.isinf(p) else 100.0 for p in mono_psnr]
                
                f.write(f"\nMonochrome Summary ({len(mono_results)} tested):\n")
                f.write(f"  Average SSIM: {np.mean(mono_ssim):.2f}%\n")
                f.write(f"  Average PSNR: {np.mean(mono_psnr_capped):.2f} dB (capped at 100)\n")
                f.write(f"  Min SSIM:     {np.min(mono_ssim):.2f}%\n")
                f.write(f"  Max SSIM:     {np.max(mono_ssim):.2f}%\n")
            
            if multi_results:
                multi_ssim = [r['ssim_percent'] for r in multi_results if r['ssim'] is not None]
                multi_psnr = [r['psnr'] for r in multi_results if r['psnr'] is not None]
                multi_psnr_capped = [min(p, 100.0) if not np.isinf(p) else 100.0 for p in multi_psnr]
                
                f.write(f"\nMulti-Color Summary ({len(multi_results)} tested):\n")
                f.write(f"  Average SSIM: {np.mean(multi_ssim):.2f}%\n")
                f.write(f"  Average PSNR: {np.mean(multi_psnr_capped):.2f} dB (capped at 100)\n")
                f.write(f"  Min SSIM:     {np.min(multi_ssim):.2f}%\n")
                f.write(f"  Max SSIM:     {np.max(multi_ssim):.2f}%\n")

            if complex_results:
                complex_ssim = [r['ssim_percent'] for r in complex_results if r['ssim'] is not None]
                complex_psnr = [r['psnr'] for r in complex_results if r['psnr'] is not None]
                complex_psnr_capped = [min(p, 100.0) if not np.isinf(p) else 100.0 for p in complex_psnr]
                
                f.write(f"\nComplex Scenes Summary ({len(complex_results)} tested):\n")
                f.write(f"  Average SSIM: {np.mean(complex_ssim):.2f}%\n")
                f.write(f"  Average PSNR: {np.mean(complex_psnr_capped):.2f} dB (capped at 100)\n")
                f.write(f"  Min SSIM:     {np.min(complex_ssim):.2f}%\n")
                f.write(f"  Max SSIM:     {np.max(complex_ssim):.2f}%\n")
            
            if multi_results:
                multi_ssim = [r['ssim_percent'] for r in multi_results if r['ssim'] is not None]
                f.write(f"\nMulti-Color Summary ({len(multi_results)} tested):\n")
                f.write(f"  Average: {np.mean(multi_ssim):.2f}%\n")
                f.write(f"  Min:     {np.min(multi_ssim):.2f}%\n")
                f.write(f"  Max:     {np.max(multi_ssim):.2f}%\n")
        
        print(f"\n✓ Report saved to: {report_path}")
    else:
        print("No results to report. Make sure vectorization has been completed.")

if __name__ == "__main__":
    main()