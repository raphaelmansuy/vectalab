#!/usr/bin/env python3
"""
Run a full SOTA vectorization session.
- Creates a timestamped session directory.
- Runs vectalab on selected test sets.
- Calculates comprehensive metrics.
- Generates a visual HTML report.
"""

import os
import sys
import argparse
import time
import shutil
import subprocess
import json
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2
from skimage.metrics import structural_similarity as ssim
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage import color
import cairosvg
import xml.etree.ElementTree as ET
from jinja2 import Environment, FileSystemLoader

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent.parent
TEST_DATA_DIR = BASE_DIR / "test_data"
TEST_RUNS_DIR = BASE_DIR / "test_runs"
TEMPLATE_DIR = BASE_DIR / "scripts" / "templates"

# --- Metrics Functions (Adapted from compare_results.py) ---

def render_svg_to_png(svg_path, png_output, size=512):
    """Render SVG to PNG using CairoSVG."""
    try:
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(png_output),
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
        return 0

def calculate_topology_score(img1, img2):
    """Calculate topology score based on connected components and holes."""
    g1 = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY)
    g2 = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY)
    
    _, b1 = cv2.threshold(g1, 127, 255, cv2.THRESH_BINARY)
    _, b2 = cv2.threshold(g2, 127, 255, cv2.THRESH_BINARY)
    
    n1, l1, s1, _ = cv2.connectedComponentsWithStats(b1)
    n2, l2, s2, _ = cv2.connectedComponentsWithStats(b2)
    
    count1 = sum(1 for i in range(1, n1) if s1[i, cv2.CC_STAT_AREA] >= 10)
    count2 = sum(1 for i in range(1, n2) if s2[i, cv2.CC_STAT_AREA] >= 10)
    
    _, bi1 = cv2.threshold(g1, 127, 255, cv2.THRESH_BINARY_INV)
    _, bi2 = cv2.threshold(g2, 127, 255, cv2.THRESH_BINARY_INV)
    
    nh1, lh1, sh1, _ = cv2.connectedComponentsWithStats(bi1)
    nh2, lh2, sh2, _ = cv2.connectedComponentsWithStats(bi2)
    
    hole1 = sum(1 for i in range(1, nh1) if sh1[i, cv2.CC_STAT_AREA] >= 10)
    hole2 = sum(1 for i in range(1, nh2) if sh2[i, cv2.CC_STAT_AREA] >= 10)
    
    max_comp = max(count1, count2, 1)
    max_hole = max(hole1, hole2, 1)
    
    comp_diff = abs(count1 - count2)
    hole_diff = abs(hole1 - hole2)
    
    comp_score = 1.0 - (comp_diff / max_comp)
    hole_score = 1.0 - (hole_diff / max_hole)
    
    total_score = (comp_score * 0.6 + hole_score * 0.4) * 100
    return max(0, min(100, total_score))

def calculate_edge_accuracy(img1, img2):
    """Calculate edge accuracy using Canny edge detection overlap."""
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
    """Calculate Delta E (CIEDE2000) color error."""
    lab1 = color.rgb2lab(img1)
    lab2 = color.rgb2lab(img2)
    delta_e = color.deltaE_ciede2000(lab1, lab2)
    return np.mean(delta_e)

def create_checkerboard(w, h, cell_size=20, color1=(255, 255, 255), color2=(220, 220, 220)):
    """Create a checkerboard pattern image."""
    img = Image.new('RGB', (w, h), color1)
    pixels = img.load()
    for y in range(h):
        for x in range(w):
            if ((x // cell_size) + (y // cell_size)) % 2 == 1:
                pixels[x, y] = color2
    return img

def create_composite_image(original_path, vectorized_path, output_path):
    """Create a side-by-side composite image with difference map, handling transparency."""
    try:
        size = (512, 512)
        
        # Helper to load and composite over checkerboard
        def load_and_process(path):
            img = Image.open(path).convert('RGBA')
            img = img.resize(size)
            
            bg = create_checkerboard(size[0], size[1])
            bg.paste(img, (0, 0), img)
            return bg
            
        comp1 = load_and_process(original_path)
        comp2 = load_and_process(vectorized_path)
        
        # Create difference map
        arr1 = np.array(comp1)
        arr2 = np.array(comp2)
        diff = np.abs(arr1.astype(int) - arr2.astype(int)).astype(np.uint8)
        # Amplify difference for visibility
        diff = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
        diff_img = Image.fromarray(diff)
        
        # Composite
        final_comp = Image.new('RGB', (size[0] * 3, size[1]))
        final_comp.paste(comp1, (0, 0))
        final_comp.paste(comp2, (size[0], 0))
        final_comp.paste(diff_img, (size[0] * 2, 0))
        
        # Add labels (optional, skipping for clean look)
        
        final_comp.save(output_path)
        return True
    except Exception as e:
        print(f"Error creating composite: {e}")
        return False

# --- Main Session Logic ---

def run_session(sets, quality="ultra", colors=None):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_dir = TEST_RUNS_DIR / timestamp
    
    dirs = {
        "input": session_dir / "input",
        "output": session_dir / "output",
        "ground_truth": session_dir / "ground_truth",
        "rendered": session_dir / "rendered",
        "composites": session_dir / "composites"
    }
    
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
        
    print(f"🚀 Starting SOTA Session: {timestamp}")
    print(f"📂 Session Directory: {session_dir}")
    print(f"⚙️  Settings: Quality={quality}, Colors={colors if colors else 'Auto'}")
    
    results = []
    
    for set_name in sets:
        png_dir = TEST_DATA_DIR / f"png_{set_name}"
        svg_dir = TEST_DATA_DIR / f"svg_{set_name}"
        
        if not png_dir.exists():
            print(f"⚠️  Warning: {png_dir} does not exist. Skipping.")
            continue
            
        print(f"\nProcessing set: {set_name}")
        
        files = sorted([f for f in os.listdir(png_dir) if f.endswith('.png')])
        
        for filename in files:
            name = Path(filename).stem
            input_png = png_dir / filename
            gt_svg = svg_dir / f"{name}.svg"
            
            # Copy input
            shutil.copy2(input_png, dirs["input"] / filename)
            if gt_svg.exists():
                shutil.copy2(gt_svg, dirs["ground_truth"] / f"{name}.svg")
            
            output_svg = dirs["output"] / f"{name}.svg"
            
            # Run Vectalab
            cmd = ["vectalab", "logo", str(input_png), str(output_svg), "--quality", quality]
            if colors:
                cmd.extend(["--colors", str(colors)])
            
            print(f"  • {name}...", end="", flush=True)
            start_time = time.time()
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                duration = time.time() - start_time
                print(f" Done ({duration:.2f}s)")
            except subprocess.CalledProcessError as e:
                print(f" Failed! {e.stderr.decode()}")
                continue
                
            # Render for comparison
            out_png = dirs["rendered"] / f"{name}_out.png"
            gt_png = dirs["rendered"] / f"{name}_gt.png"
            
            if not render_svg_to_png(output_svg, out_png):
                print("    Failed to render output SVG")
                continue
                
            # If GT exists, render it. If not, use input PNG as reference (less ideal for topology but ok for visual)
            # Actually, for SOTA metrics we usually compare against the original raster if we don't have a GT SVG,
            # but here we have GT SVGs for the test sets.
            # If GT SVG is missing, we can compare against the input PNG directly.
            
            ref_png = gt_png
            if gt_svg.exists():
                if not render_svg_to_png(gt_svg, gt_png):
                    print("    Failed to render GT SVG")
                    ref_png = input_png # Fallback
            else:
                ref_png = input_png
                
            # Calculate Metrics
            try:
                img_ref = Image.open(ref_png).convert('RGB')
                img_out = Image.open(out_png).convert('RGB')
                
                if img_ref.size != img_out.size:
                    img_out = img_out.resize(img_ref.size)
                
                arr_ref = np.array(img_ref)
                arr_out = np.array(img_out)
                
                s = ssim(arr_ref, arr_out, channel_axis=2, data_range=255) * 100
                topo = calculate_topology_score(arr_ref, arr_out)
                edge = calculate_edge_accuracy(arr_ref, arr_out)
                de = calculate_color_error(arr_ref, arr_out)
                paths = count_paths(output_svg)
                
                # Create Composite
                comp_filename = f"{name}_comp.jpg"
                comp_path = dirs["composites"] / comp_filename
                create_composite_image(ref_png, out_png, comp_path)
                
                results.append({
                    "icon": name,
                    "set": set_name,
                    "ssim": s,
                    "topology": topo,
                    "edge": edge,
                    "delta_e": de,
                    "paths": paths,
                    "time": duration,
                    "composite_path": f"composites/{comp_filename}",
                    "svg_path": f"output/{name}.svg"
                })
                
            except Exception as e:
                print(f"    Error calculating metrics: {e}")

    # Generate Report
    if results:
        avg_ssim = np.mean([r['ssim'] for r in results])
        avg_topo = np.mean([r['topology'] for r in results])
        avg_edge = np.mean([r['edge'] for r in results])
        avg_de = np.mean([r['delta_e'] for r in results])
        avg_time = np.mean([r['time'] for r in results])
        
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template("report_template.html")
        
        html_out = template.render(
            timestamp=timestamp,
            results=results,
            avg_ssim=avg_ssim,
            avg_topo=avg_topo,
            avg_edge=avg_edge,
            avg_de=avg_de,
            avg_time=avg_time
        )
        
        report_path = session_dir / "report.html"
        with open(report_path, "w") as f:
            f.write(html_out)
            
        print(f"\n✅ Session Complete!")
        print(f"📊 Summary:")
        print(f"  • Avg SSIM:     {avg_ssim:.2f}%")
        print(f"  • Avg Topology: {avg_topo:.1f}%")
        print(f"  • Avg Edge:     {avg_edge:.1f}%")
        print(f"  • Avg Delta E:  {avg_de:.2f}")
        print(f"  • Avg Time:     {avg_time:.2f}s")
        print(f"📄 Report: {report_path}")
        
        # Open report if on macOS
        if sys.platform == "darwin":
            subprocess.run(["open", str(report_path)])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SOTA Vectorization Session")
    parser.add_argument("--sets", nargs="+", default=["mono", "multi", "complex"], help="Test sets to run (mono, multi, complex)")
    parser.add_argument("--quality", default="ultra", help="Vectalab quality setting")
    parser.add_argument("--colors", type=int, help="Force number of colors")
    
    args = parser.parse_args()
    
    run_session(args.sets, args.quality, args.colors)
