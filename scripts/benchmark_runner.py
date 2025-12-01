#!/usr/bin/env python3
"""
Vectalab Benchmark & SOTA Session Runner.

This module provides a comprehensive benchmarking tool for the Vectalab vectorization engine.
It allows running vectorization sessions on standard test sets or custom image directories,
calculating detailed metrics (SSIM, Topology, Edge Accuracy, Delta E), and generating
visual HTML reports.

Usage:
    python scripts/benchmark_runner.py [OPTIONS]

Examples:
    # Run on standard test sets
    python scripts/benchmark_runner.py --sets mono multi

    # Run on a custom directory of images
    python scripts/benchmark_runner.py --input-dir ./my_images --mode premium

    # Run with specific quality settings
    python scripts/benchmark_runner.py --quality balanced --colors 16
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
import concurrent.futures
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
from rich import box

# Initialize Rich Console
console = Console()

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent.parent
TEST_DATA_DIR = BASE_DIR / "test_data"
GOLDEN_DATA_DIR = BASE_DIR / "golden_data"
TEST_RUNS_DIR = BASE_DIR / "test_runs"
TEMPLATE_DIR = BASE_DIR / "scripts" / "templates"

# --- Metrics Functions ---

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
        
        final_comp.save(output_path)
        return True
    except Exception as e:
        print(f"Error creating composite: {e}")
        return False

# --- Worker Function ---

def process_image(args):
    """
    Worker function to process a single image.
    args: (filename, set_name, png_dir, svg_dir, dirs, quality, colors, mode)
    """
    filename, set_name, png_dir, svg_dir, dirs, quality, colors, mode = args
    
    name = Path(filename).stem
    input_png = png_dir / filename
    gt_svg = svg_dir / f"{name}.svg" if svg_dir else None
    
    # Copy input
    shutil.copy2(input_png, dirs["input"] / filename)
    if gt_svg and gt_svg.exists():
        shutil.copy2(gt_svg, dirs["ground_truth"] / f"{name}.svg")
    
    output_svg = dirs["output"] / f"{name}.svg"
    
    # Run Vectalab
    effective_mode = mode
    if mode == "auto":
        if set_name == "complex":
            effective_mode = "premium"
        else:
            effective_mode = "logo"
            
    if effective_mode == "premium":
        # Use premium photo mode
        cmd = ["vectalab", "premium", str(input_png), str(output_svg), "--mode", "photo", "--target-ssim", "0.95"]
    else:
        # Use logo mode
        cmd = ["vectalab", "logo", str(input_png), str(output_svg), "--quality", quality]
        
    if colors:
        cmd.extend(["--colors", str(colors)])
    
    start_time = time.time()
    try:
        # Add timeout to prevent hanging on complex images
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        duration = time.time() - start_time
    except subprocess.TimeoutExpired:
        return {"error": "Vectalab timed out (120s)", "name": name}
    except subprocess.CalledProcessError as e:
        return {"error": f"Vectalab failed: {e.stderr.decode()}", "name": name}
        
    # Render for comparison
    out_png = dirs["rendered"] / f"{name}_out.png"
    gt_png = dirs["rendered"] / f"{name}_gt.png"
    
    if not render_svg_to_png(output_svg, out_png):
        return {"error": "Failed to render output SVG", "name": name}
        
    # Reference handling
    ref_png = gt_png
    if gt_svg and gt_svg.exists():
        if not render_svg_to_png(gt_svg, gt_png):
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
        
        return {
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
        }
        
    except Exception as e:
        return {"error": f"Error calculating metrics: {e}", "name": name}

# --- Main Session Logic ---

def run_session(sets, quality="ultra", colors=None, max_workers=None, input_dir=None, mode="auto"):
    """
    Run a vectorization session.
    
    Args:
        sets: List of test sets to run (if input_dir is None).
        quality: Vectalab quality preset.
        colors: Force number of colors (optional).
        max_workers: Number of parallel workers.
        input_dir: Custom input directory (overrides sets).
        mode: Vectorization mode (auto, logo, premium).
    """
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
        
    console.print(Panel(f"[bold cyan]SOTA Vectorization Session[/]\n[dim]{timestamp}[/]", border_style="cyan"))
    console.print(f"[bold]📂 Session Directory:[/] {session_dir}")
    console.print(f"[bold]⚙️  Settings:[/] Quality=[cyan]{quality}[/], Colors=[cyan]{colors if colors else 'Auto'}[/], Workers=[cyan]{max_workers if max_workers else 'Auto'}[/], Mode=[cyan]{mode}[/]")
    
    tasks = []
    
    if input_dir:
        input_path = Path(input_dir)
        if not input_path.exists():
            console.print(f"[bold red]❌ Error:[/] Input directory {input_dir} does not exist.")
            return
            
        console.print(f"[bold]📂 Input Directory:[/] {input_dir}")
        png_dir = input_path
        svg_dir = None
        set_name = input_path.name
        
        files = sorted([f for f in os.listdir(png_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp'))])
        
        if not files:
            console.print(f"[bold yellow]⚠️  Warning:[/] No images found in {png_dir}.")
            return
            
        for filename in files:
            tasks.append((filename, set_name, png_dir, svg_dir, dirs, quality, colors, mode))
            
    else:
        for set_name in sets:
            if set_name == "golden":
                # Handle Golden Dataset
                categories = ["icons", "logos", "illustrations"]
                cache_dir = TEST_DATA_DIR / "cache_golden"
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                for category in categories:
                    cat_svg_dir = GOLDEN_DATA_DIR / category
                    cat_png_dir = cache_dir / category
                    cat_png_dir.mkdir(exist_ok=True)
                    
                    if not cat_svg_dir.exists():
                        console.print(f"[bold yellow]⚠️  Warning:[/] {cat_svg_dir} does not exist. Skipping.")
                        continue
                        
                    svg_files = sorted([f for f in os.listdir(cat_svg_dir) if f.endswith('.svg')])
                    console.print(f"[cyan]Preparing {len(svg_files)} images for golden/{category}...[/]")
                    
                    for filename in svg_files:
                        name = Path(filename).stem
                        svg_path = cat_svg_dir / filename
                        png_path = cat_png_dir / f"{name}.png"
                        
                        # Rasterize if needed
                        if not png_path.exists():
                            try:
                                cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=1024, output_height=1024)
                            except Exception as e:
                                console.print(f"[red]Failed to rasterize {filename}: {e}[/]")
                                continue
                        
                        tasks.append((f"{name}.png", f"golden_{category}", cat_png_dir, cat_svg_dir, dirs, quality, colors, mode))
            else:
                png_dir = TEST_DATA_DIR / f"png_{set_name}"
                svg_dir = TEST_DATA_DIR / f"svg_{set_name}"
                
                if not png_dir.exists():
                    console.print(f"[bold yellow]⚠️  Warning:[/] {png_dir} does not exist. Skipping.")
                    continue
                    
                files = sorted([f for f in os.listdir(png_dir) if f.endswith('.png')])
                for filename in files:
                    tasks.append((filename, set_name, png_dir, svg_dir, dirs, quality, colors, mode))
            
    console.print(f"[bold]📋 Found {len(tasks)} images to process.[/]")
    
    results = []
    jsonl_path = session_dir / "results.jsonl"
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task_id = progress.add_task("[cyan]Processing images...", total=len(tasks))
            
            with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
                future_to_task = {executor.submit(process_image, task): task for task in tasks}
                
                with open(jsonl_path, "w") as f_jsonl:
                    for future in concurrent.futures.as_completed(future_to_task):
                        task = future_to_task[future]
                        name = Path(task[0]).stem
                        
                        try:
                            res = future.result()
                            if "error" in res:
                                console.print(f"[red]❌ {name}: {res['error']}[/]")
                            else:
                                results.append(res)
                                # Incremental save
                                f_jsonl.write(json.dumps(res) + "\n")
                                f_jsonl.flush()
                        except Exception as exc:
                            console.print(f"[bold red]❌ {name} generated an exception: {exc}[/]")
                        
                        progress.advance(task_id)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠️  Interrupted! Generating partial report...[/]")
    
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

        # Save raw results to JSON
        json_path = session_dir / "results.json"
        with open(json_path, "w") as f:
            json.dump(results, f, indent=2)
            
        console.print(f"\n[bold green]✅ Session Complete![/]")
        
        table = Table(title="Session Summary", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Average Value", style="magenta")
        
        table.add_row("SSIM", f"{avg_ssim:.2f}%")
        table.add_row("Topology Score", f"{avg_topo:.1f}%")
        table.add_row("Edge Accuracy", f"{avg_edge:.1f}%")
        table.add_row("Delta E", f"{avg_de:.2f}")
        table.add_row("Time per Image", f"{avg_time:.2f}s")
        
        console.print(table)
        console.print(f"[bold]📄 Report:[/] [link=file://{report_path}]{report_path}[/link]")
        
        # Open report if on macOS
        if sys.platform == "darwin":
            subprocess.run(["open", str(report_path)])

def main():
    parser = argparse.ArgumentParser(
        description="Run a SOTA Vectorization Session using Vectalab.",
        epilog="Example:\n  python scripts/benchmark_runner.py --input-dir ./my_images --mode premium",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--sets", nargs="+", default=["mono", "multi", "complex"], help="Test sets to run (default: mono multi complex). Use 'golden' for the Golden Dataset.")
    parser.add_argument("--quality", default="ultra", help="Vectalab quality setting (default: ultra)")
    parser.add_argument("--colors", type=int, help="Force number of colors (optional)")
    parser.add_argument("--workers", type=int, default=None, help="Max number of parallel workers (default: auto)")
    parser.add_argument("--input-dir", help="Custom input directory of images to process (overrides --sets)")
    parser.add_argument("--mode", default="auto", choices=["auto", "logo", "premium"], help="Vectorization mode (default: auto)")
    
    args = parser.parse_args()
    
    run_session(args.sets, args.quality, args.colors, args.workers, args.input_dir, args.mode)

if __name__ == "__main__":
    main()
