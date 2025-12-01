#!/usr/bin/env python3
"""
Vectalab Benchmark & SOTA Session Runner.

This module provides a comprehensive benchmarking tool for the Vectalab vectorization engine.
It allows running vectorization sessions on standard test sets or custom image directories,
calculating detailed metrics (SSIM, Topology, Edge Accuracy, Delta E), and generating
visual HTML reports.

Usage:
    vectalab-benchmark [OPTIONS]

Examples:
    # Run on standard test sets
    vectalab-benchmark --sets mono multi

    # Run on a custom directory of images
    vectalab-benchmark --input-dir ./my_images --mode premium

    # Run with specific quality settings
    vectalab-benchmark --quality balanced --colors 16
"""

import os
import sys
import argparse
import time
import shutil
import subprocess
import json
import re
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
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
from vectalab.quality import (
    analyze_image, 
    calculate_topology_score, 
    calculate_edge_accuracy, 
    calculate_color_error, 
    analyze_path_types
)
try:
    from vectalab.perceptual import calculate_lpips, calculate_dists, calculate_gmsd
    LPIPS_AVAILABLE = True
except ImportError:
    LPIPS_AVAILABLE = False

from vectalab.icon import is_monochrome_icon, process_geometric_icon
from vectalab.auto import determine_auto_mode

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
    effective_quality = quality
    mono_color = None
    
    if mode == "auto":
        # Use centralized auto logic
        effective_mode, effective_quality, mono_color = determine_auto_mode(str(input_png), set_name)
            
    if effective_mode == "geometric_icon":
        # Special handling for geometric icons using shared implementation
        try:
            success, result = process_geometric_icon(str(input_png), str(output_svg), mono_color)
            if not success:
                raise Exception(result.get("error", "Unknown error"))
            duration = 0 # process_geometric_icon doesn't return duration, could measure here
        except Exception as e:
            # Fallback to standard logo mode if anything fails
            cmd = ["vectalab", "logo", str(input_png), str(output_svg), "--quality", "ultra"]
            start_time = time.time()
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            duration = time.time() - start_time
            
    elif effective_mode == "premium":
        # Use premium photo mode
        cmd = ["vectalab", "premium", str(input_png), str(output_svg), "--mode", "photo", "--target-ssim", "0.95"]
        start_time = time.time()
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        duration = time.time() - start_time
    else:
        # Use logo mode
        cmd = ["vectalab", "logo", str(input_png), str(output_svg), "--quality", effective_quality]
        if colors:
            cmd.extend(["--colors", str(colors)])
        start_time = time.time()
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        duration = time.time() - start_time
        
    # Render for comparison
        
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
        
        lpips_val = 0.0
        dists_val = 0.0
        gmsd_val = 0.0
        
        if LPIPS_AVAILABLE:
            # LPIPS expects 0-1 range if passed as array? No, my wrapper handles it.
            # But wait, calculate_lpips wrapper handles numpy arrays.
            # Let's pass the PIL images directly to be safe/efficient.
            lpips_res = calculate_lpips(img_ref, img_out)
            if lpips_res is not None:
                lpips_val = lpips_res
            
            dists_res = calculate_dists(img_ref, img_out)
            if dists_res is not None:
                dists_val = dists_res
                
            gmsd_res = calculate_gmsd(img_ref, img_out)
            if gmsd_res is not None:
                gmsd_val = gmsd_res

        # FEEDBACK LOOP (Auto Mode Only)
        # If LPIPS is high (> 0.15) and we used 'logo' mode, it might be a complex image.
        # Retry with 'premium' mode.
        if mode == "auto" and effective_mode == "logo" and lpips_val > 0.15:
            effective_mode = "premium (retry)"
            
            # Run Premium
            cmd = ["vectalab", "premium", str(input_png), str(output_svg), "--mode", "photo", "--target-ssim", "0.95"]
            start_time = time.time()
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            duration += (time.time() - start_time)
            
            # Re-render
            if not render_svg_to_png(output_svg, out_png):
                return {"error": "Failed to render output SVG (Retry)", "name": name}
                
            # Re-calculate metrics
            img_out = Image.open(out_png).convert('RGB')
            if img_ref.size != img_out.size:
                img_out = img_out.resize(img_ref.size)
            arr_out = np.array(img_out)
            
            s = ssim(arr_ref, arr_out, channel_axis=2, data_range=255) * 100
            topo = calculate_topology_score(arr_ref, arr_out)
            edge = calculate_edge_accuracy(arr_ref, arr_out)
            de = calculate_color_error(arr_ref, arr_out)
            
            if LPIPS_AVAILABLE:
                lpips_res = calculate_lpips(img_ref, img_out)
                if lpips_res is not None:
                    lpips_val = lpips_res
                
                dists_res = calculate_dists(img_ref, img_out)
                if dists_res is not None:
                    dists_val = dists_res
                    
                gmsd_res = calculate_gmsd(img_ref, img_out)
                if gmsd_res is not None:
                    gmsd_val = gmsd_res

        paths = count_paths(output_svg)
        path_analysis = analyze_path_types(output_svg)
        
        # Create Composite
        comp_filename = f"{name}_comp.jpg"
        comp_path = dirs["composites"] / comp_filename
        create_composite_image(ref_png, out_png, comp_path)
        
        return {
            "icon": name,
            "set": set_name,
            "mode": effective_mode,
            "quality": effective_quality if effective_mode == "logo" else "N/A",
            "ssim": s,
            "topology": topo,
            "edge": edge,
            "delta_e": de,
            "lpips": lpips_val,
            "dists": dists_val,
            "gmsd": gmsd_val,
            "paths": paths,
            "complexity": path_analysis['total'],
            "curve_fraction": path_analysis['curve_fraction'],
            "time": duration,
            "composite_path": f"composites/{comp_filename}",
            "svg_path": f"output/{name}.svg"
        }
        
    except Exception as e:
        return {"error": f"Error calculating metrics: {e}", "name": name}

# --- Main Session Logic ---

def run_session(sets, quality="ultra", colors=None, max_workers=None, input_dir=None, mode="auto", limit=None, filter_str=None):
    """
    Run a vectorization session.
    
    Args:
        sets: List of test sets to run (if input_dir is None).
        quality: Vectalab quality preset.
        colors: Force number of colors (optional).
        max_workers: Number of parallel workers.
        input_dir: Custom input directory (overrides sets).
        mode: Vectorization mode (auto, logo, premium).
        limit: Limit the number of images to process.
        filter_str: Filter images by name.
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
        
    # Intelligent Worker Management
    if max_workers is None:
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        # Conservative default: 4 or CPU/2, whichever is lower, to prevent OOM with SAM
        max_workers = min(4, max(1, cpu_count // 2))
        console.print(f"[dim]Auto-setting workers to {max_workers} to prevent resource exhaustion.[/]")
    elif max_workers > 4:
        console.print(f"[bold yellow]⚠️  Warning:[/] Running with {max_workers} workers may cause memory exhaustion or instability with heavy ML models. Recommended: 2-4.[/]")

    console.print(Panel(f"[bold cyan]SOTA Vectorization Session[/]\n[dim]{timestamp}[/]", border_style="cyan"))
    console.print(f"[bold]📂 Session Directory:[/] {session_dir}")
    console.print(f"[bold]⚙️  Settings:[/] Quality=[cyan]{quality}[/], Colors=[cyan]{colors if colors else 'Auto'}[/], Workers=[cyan]{max_workers}[/], Mode=[cyan]{mode}[/]")
    
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
            
    if filter_str:
        console.print(f"[dim]Filtering images by '{filter_str}'[/]")
        filters = [f.strip().lower() for f in filter_str.split(',')]
        tasks = [t for t in tasks if any(f in t[0].lower() for f in filters)]

    if limit:
        console.print(f"[dim]Limiting to first {limit} images.[/]")
        tasks = tasks[:limit]

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
        avg_lpips = np.mean([r.get('lpips', 0.0) for r in results])
        avg_dists = np.mean([r.get('dists', 0.0) for r in results])
        avg_gmsd = np.mean([r.get('gmsd', 0.0) for r in results])
        avg_time = np.mean([r['time'] for r in results])
        avg_complexity = np.mean([r.get('complexity', 0) for r in results])
        avg_curve_fraction = np.mean([r.get('curve_fraction', 0) for r in results])
        
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template("report_template.html")
        
        html_out = template.render(
            timestamp=timestamp,
            results=results,
            avg_ssim=avg_ssim,
            avg_topo=avg_topo,
            avg_edge=avg_edge,
            avg_de=avg_de,
            avg_lpips=avg_lpips,
            avg_dists=avg_dists,
            avg_gmsd=avg_gmsd,
            avg_time=avg_time,
            avg_complexity=avg_complexity,
            avg_curve_fraction=avg_curve_fraction
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
        table.add_column("Description", style="dim")
        
        table.add_row("SSIM", f"{avg_ssim:.2f}%", "Visual similarity (100% is perfect)")
        table.add_row("LPIPS", f"{avg_lpips:.4f}", "Perceptual distance (0 is perfect)")
        table.add_row("DISTS", f"{avg_dists:.4f}", "Texture/Structure distance (0 is perfect)")
        table.add_row("GMSD", f"{avg_gmsd:.4f}", "Gradient magnitude deviation (0 is perfect)")
        table.add_row("Topology Score", f"{avg_topo:.1f}%", "Preservation of holes and shapes")
        table.add_row("Edge Accuracy", f"{avg_edge:.1f}%", "Geometric boundary alignment")
        table.add_row("Delta E", f"{avg_de:.2f}", "Color error (0 is perfect)")
        table.add_row("Path Complexity", f"{avg_complexity:.1f} segments", "Average curve segments per image")
        table.add_row("Curve Fraction", f"{avg_curve_fraction:.1f}%", "Percentage of curved paths")
        table.add_row("Time per Image", f"{avg_time:.2f}s", "Average processing duration")
        
        console.print(table)
        console.print(f"[bold]📄 Report:[/] [link=file://{report_path}]{report_path}[/link]")
        
        # Open report if on macOS
        if sys.platform == "darwin":
            subprocess.run(["open", str(report_path)])

def main():
    parser = argparse.ArgumentParser(
        description="Run a SOTA Vectorization Session using Vectalab.",
        epilog="Example:\n  vectalab-benchmark --input-dir ./my_images --mode premium",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--sets", nargs="+", default=["mono", "multi", "complex"], help="Test sets to run (default: mono multi complex). Use 'golden' for the Golden Dataset.")
    parser.add_argument("--quality", default="ultra", help="Vectalab quality setting (default: ultra)")
    parser.add_argument("--colors", type=int, help="Force number of colors (optional)")
    parser.add_argument("--workers", type=int, default=None, help="Max number of parallel workers (default: auto)")
    parser.add_argument("--input-dir", help="Custom input directory of images to process (overrides --sets)")
    parser.add_argument("--mode", default="auto", choices=["auto", "logo", "premium"], help="Vectorization mode (default: auto)")
    parser.add_argument("--limit", type=int, help="Limit the number of images to process (for testing)")
    parser.add_argument("--filter", help="Filter images by name (substring match)")
    
    args = parser.parse_args()
    
    run_session(args.sets, args.quality, args.colors, args.workers, args.input_dir, args.mode, args.limit, args.filter)

if __name__ == "__main__":
    main()
