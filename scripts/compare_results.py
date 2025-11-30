#!/usr/bin/env python3
"""
Compare original and vectorized SVGs using SOTA metrics:
- SSIM (Structural Similarity)
- Visual Fidelity (Perceptual SSIM)
- Topology Score (Connected components and holes)
- Edge Accuracy (Canny edge detection overlap)
- Color Error (Delta E)
- Path Count (Efficiency)
- Time (Performance)
"""

import os
import sys
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image
import cv2
from skimage.metrics import structural_similarity as ssim
from skimage.metrics import mean_squared_error as mse
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage import color
import cairosvg
import tempfile
import xml.etree.ElementTree as ET
import json
import time

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

def count_paths(svg_path):
    """Count the number of path elements in an SVG."""
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        count = 0
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] # Strip namespace
            if tag in ['path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon']:
                count += 1
        return count
    except Exception as e:
        print(f"Error counting paths in {svg_path}: {e}")
        return 0

def calculate_topology_score(img1, img2):
    """
    Calculate topology score based on connected components and holes.
    Ignores small components (noise).
    Returns a score between 0 and 100.
    """
    # Convert to grayscale and binary
    g1 = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY)
    g2 = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY)
    
    _, b1 = cv2.threshold(g1, 127, 255, cv2.THRESH_BINARY)
    _, b2 = cv2.threshold(g2, 127, 255, cv2.THRESH_BINARY)
    
    # Connected components with stats
    n1, l1, s1, _ = cv2.connectedComponentsWithStats(b1)
    n2, l2, s2, _ = cv2.connectedComponentsWithStats(b2)
    
    # Filter small components (area < 10)
    # Note: Index 0 is background, usually large.
    count1 = 0
    for i in range(1, n1):
        if s1[i, cv2.CC_STAT_AREA] >= 10:
            count1 += 1
            
    count2 = 0
    for i in range(1, n2):
        if s2[i, cv2.CC_STAT_AREA] >= 10:
            count2 += 1
    
    # Invert for holes (background components)
    _, bi1 = cv2.threshold(g1, 127, 255, cv2.THRESH_BINARY_INV)
    _, bi2 = cv2.threshold(g2, 127, 255, cv2.THRESH_BINARY_INV)
    
    nh1, lh1, sh1, _ = cv2.connectedComponentsWithStats(bi1)
    nh2, lh2, sh2, _ = cv2.connectedComponentsWithStats(bi2)
    
    # Filter small holes
    hole1 = 0
    for i in range(1, nh1):
        if sh1[i, cv2.CC_STAT_AREA] >= 10:
            hole1 += 1
            
    hole2 = 0
    for i in range(1, nh2):
        if sh2[i, cv2.CC_STAT_AREA] >= 10:
            hole2 += 1
    
    # Calculate score
    max_comp = max(count1, count2, 1)
    max_hole = max(hole1, hole2, 1)
    
    comp_diff = abs(count1 - count2)
    hole_diff = abs(hole1 - hole2)
    
    comp_score = 1.0 - (comp_diff / max_comp)
    hole_score = 1.0 - (hole_diff / max_hole)
    
    total_score = (comp_score * 0.6 + hole_score * 0.4) * 100
    return max(0, min(100, total_score)), count1, count2, hole1, hole2

def calculate_edge_accuracy(img1, img2):
    """
    Calculate edge accuracy using Canny edge detection overlap.
    Returns a score between 0 and 100.
    """
    g1 = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY)
    g2 = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY)
    
    e1 = cv2.Canny(g1, 100, 200)
    e2 = cv2.Canny(g2, 100, 200)
    
    kernel = np.ones((3,3), np.uint8)
    e1_d = cv2.dilate(e1, kernel, iterations=1)
    e2_d = cv2.dilate(e2, kernel, iterations=1)
    
    intersection = np.logical_and(e1_d > 0, e2_d > 0)
    union = np.logical_or(e1_d > 0, e2_d > 0)
    
    if np.sum(union) == 0:
        return 100.0
        
    iou = np.sum(intersection) / np.sum(union)
    return iou * 100

def calculate_color_error(img1, img2):
    """
    Calculate Delta E (CIEDE2000) color error.
    Returns the average Delta E.
    """
    lab1 = color.rgb2lab(img1)
    lab2 = color.rgb2lab(img2)
    delta_e = color.deltaE_ciede2000(lab1, lab2)
    return np.mean(delta_e)

def calculate_metrics(img1_path, img2_path):
    """Calculate all SOTA metrics."""
    try:
        img1_pil = Image.open(img1_path).convert('RGB')
        img2_pil = Image.open(img2_path).convert('RGB')
        
        if img1_pil.size != img2_pil.size:
            img2_pil = img2_pil.resize(img1_pil.size)
            
        arr1 = np.array(img1_pil)
        arr2 = np.array(img2_pil)
        
        s = ssim(arr1, arr2, channel_axis=2, data_range=255)
        p = psnr(arr1, arr2, data_range=255)
        topo, n1, n2, h1, h2 = calculate_topology_score(arr1, arr2)
        edge = calculate_edge_accuracy(arr1, arr2)
        delta_e = calculate_color_error(arr1, arr2)
        
        return {
            "ssim": s,
            "psnr": p,
            "topology": topo,
            "edge": edge,
            "delta_e": delta_e,
            "topo_stats": (n1, n2, h1, h2)
        }
    except Exception as e:
        print(f"Error calculating metrics: {e}")
        return None

def compare_vectorization(original_svg, vectorized_svg, icon_name, output_dir="test_data/comparisons"):
    """Compare original and vectorized SVGs."""
    os.makedirs(output_dir, exist_ok=True)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_png = os.path.join(tmpdir, "original.png")
        vectorized_png = os.path.join(tmpdir, "vectorized.png")
        
        if not render_svg_to_png(original_svg, original_png):
            return None
        if not render_svg_to_png(vectorized_svg, vectorized_png):
            return None
        
        metrics = calculate_metrics(original_png, vectorized_png)
        path_count = count_paths(vectorized_svg)
        
        if metrics:
            return {
                "icon": icon_name,
                "ssim": metrics["ssim"] * 100,
                "psnr": metrics["psnr"],
                "topology": metrics["topology"],
                "edge": metrics["edge"],
                "delta_e": metrics["delta_e"],
                "paths": path_count
            }
        return None

def print_row(name, ssim, topo, edge, de, paths, time_val):
    """Print a formatted row."""
    time_str = f"{time_val:.2f}s" if time_val is not None else "-"
    print(f"{name[:30]:<30} | {ssim:>6.2f}% | {topo:>6.1f}% | {edge:>6.1f}% | {de:>6.2f} | {paths:>5} | {time_str:>7}")

def main():
    results = []
    execution_times = {}
    
    # Load execution times
    try:
        with open("test_data/execution_times.json", "r") as f:
            execution_times = json.load(f)
    except FileNotFoundError:
        print("Warning: test_data/execution_times.json not found. Run run_vectalab_test.py first.")
    
    print("\n" + "="*100)
    print(f"{'Icon':<30} | {'SSIM':>7} | {'Topo':>7} | {'Edge':>7} | {'ΔE':>6} | {'Paths':>5} | {'Time':>7}")
    print("-" * 100)
    
    dirs = [
        ("test_data/svg_mono", "test_data/vectalab_mono", "mono_"),
        ("test_data/svg_multi", "test_data/vectalab_multi", "multi_"),
        ("test_data/svg_complex", "test_data/vectalab_complex", "complex_")
    ]
    
    for svg_dir, vectalab_dir, prefix in dirs:
        if os.path.exists(svg_dir):
            for filename in sorted(os.listdir(svg_dir)):
                if filename.endswith('.svg'):
                    original_svg = os.path.join(svg_dir, filename)
                    vectorized_svg = os.path.join(vectalab_dir, filename)
                    
                    if os.path.exists(vectorized_svg):
                        icon_key = f"{prefix}{filename[:-4]}"
                        result = compare_vectorization(original_svg, vectorized_svg, icon_key)
                        if result:
                            result['time'] = execution_times.get(icon_key)
                            results.append(result)
                            print_row(
                                result['icon'], 
                                result['ssim'], 
                                result['topology'], 
                                result['edge'], 
                                result['delta_e'], 
                                result['paths'],
                                result['time']
                            )
    
    if results:
        print("-" * 100)
        
        avg_ssim = np.mean([r['ssim'] for r in results])
        avg_topo = np.mean([r['topology'] for r in results])
        avg_edge = np.mean([r['edge'] for r in results])
        avg_de = np.mean([r['delta_e'] for r in results])
        times = [r['time'] for r in results if r['time'] is not None]
        avg_time = np.mean(times) if times else 0
        
        print(f"{'AVERAGE':<30} | {avg_ssim:>6.2f}% | {avg_topo:>6.1f}% | {avg_edge:>6.1f}% | {avg_de:>6.2f} | {'-':>5} | {avg_time:>6.2f}s")
        print("=" * 100)
        
        report_path = "test_data/baseline_report.txt"
        with open(report_path, 'w') as f:
            f.write("VECTALAB SOTA METRICS REPORT\n")
            f.write("="*100 + "\n")
            f.write(f"{'Icon':<30} | {'SSIM':>7} | {'Topo':>7} | {'Edge':>7} | {'ΔE':>6} | {'Paths':>5} | {'Time':>7}\n")
            f.write("-" * 100 + "\n")
            for r in results:
                time_str = f"{r['time']:.2f}s" if r['time'] is not None else "-"
                f.write(f"{r['icon']:<30} | {r['ssim']:>6.2f}% | {r['topology']:>6.1f}% | {r['edge']:>6.1f}% | {r['delta_e']:>6.2f} | {r['paths']:>5} | {time_str:>7}\n")
            f.write("-" * 100 + "\n")
            f.write(f"{'AVERAGE':<30} | {avg_ssim:>6.2f}% | {avg_topo:>6.1f}% | {avg_edge:>6.1f}% | {avg_de:>6.2f} | {'-':>5} | {avg_time:>6.2f}s\n")
            
        print(f"\n✓ Detailed report saved to: {report_path}")

if __name__ == "__main__":
    main()
