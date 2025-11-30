#!/usr/bin/env python3
"""
Optimize vectorization parameters for a specific logo.
"""

import os
import sys
import subprocess
import json
import itertools
from compare_results import calculate_metrics, render_svg_to_png, count_paths
import tempfile
import shutil

def run_vectalab(input_png, output_svg, params):
    """Run Vectalab with specific parameters."""
    cmd = [
        "vectalab", "logo",
        input_png, output_svg,
        "--force"
    ]
    
    if "quality" in params:
        cmd.extend(["--quality", params["quality"]])
    
    if "colors" in params and params["colors"] != "auto":
        cmd.extend(["--colors", str(params["colors"])])
        
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            # print(f"Vectalab failed for {params}: {result.stderr}")
            pass
        return result.returncode == 0
    except Exception as e:
        print(f"Error running vectalab: {e}")
        return False

def optimize_logo(input_png, output_dir="test_data/optimization"):
    """Run optimization loop for a logo."""
    os.makedirs(output_dir, exist_ok=True)
    
    filename = os.path.basename(input_png)
    name = os.path.splitext(filename)[0]
    
    # Define parameter grid
    qualities = ["clean", "balanced", "high", "ultra"]
    colors = ["auto", 2, 4, 8, 16]
    
    best_score = -1
    best_params = None
    best_metrics = None
    
    print(f"Optimizing {filename}...")
    print(f"{'Quality':<10} | {'Colors':<6} | {'SSIM':>7} | {'Topo':>7} | {'Edge':>7} | {'ΔE':>6} | {'Paths':>5} | {'Topo Stats':<15}")
    print("-" * 90)
    
    for q, c in itertools.product(qualities, colors):
        params = {"quality": q, "colors": c}
        
        svg_output = os.path.join(output_dir, f"{name}_{q}_{c}.svg")
        
        if run_vectalab(input_png, svg_output, params):
            # Calculate metrics
            with tempfile.TemporaryDirectory() as tmpdir:
                png_output = os.path.join(tmpdir, "rendered.png")
                if render_svg_to_png(svg_output, png_output):
                    metrics = calculate_metrics(input_png, png_output)
                    paths = count_paths(svg_output)
                    
                    if metrics:
                        # Define a composite score for optimization
                        # We want high SSIM, high Topo, high Edge, low Delta E
                        # Score = SSIM * 0.4 + Topo * 0.3 + Edge * 0.2 + (100 - DeltaE*10) * 0.1
                        # This is heuristic.
                        
                        ssim_val = metrics["ssim"] * 100
                        topo_val = metrics["topology"]
                        edge_val = metrics["edge"]
                        de_val = metrics["delta_e"]
                        n1, n2, h1, h2 = metrics.get("topo_stats", (0,0,0,0))
                        
                        # Penalize high path count? Maybe not for SOTA quality, but for efficiency yes.
                        # For now focus on quality.
                        
                        score = (ssim_val * 0.4) + (topo_val * 0.3) + (edge_val * 0.2) + (max(0, 100 - de_val * 5) * 0.1)
                        
                        print(f"{q:<10} | {c:<6} | {ssim_val:>6.2f}% | {topo_val:>6.1f}% | {edge_val:>6.1f}% | {de_val:>6.2f} | {paths:>5} | C:{n1}->{n2} H:{h1}->{h2}")
                        
                        if score > best_score:
                            best_score = score
                            best_params = params
                            best_metrics = metrics
                            # Save as best
                            best_svg = os.path.join(output_dir, f"{name}_best.svg")
                            shutil.copy(svg_output, best_svg)
    
    print("-" * 70)
    if best_params:
        print(f"Best parameters: {best_params}")
        print(f"Best Score: {best_score:.2f}")
        print(f"Best Metrics: SSIM={best_metrics['ssim']*100:.2f}%, Topo={best_metrics['topology']:.1f}%, Edge={best_metrics['edge']:.1f}%, ΔE={best_metrics['delta_e']:.2f}")
    else:
        print("Optimization failed.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/optimize_logo.py <input_png>")
        sys.exit(1)
    
    optimize_logo(sys.argv[1])
