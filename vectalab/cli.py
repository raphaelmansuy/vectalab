"""
Vectalab CLI - Professional High-Fidelity Image Vectorization

A beautiful command-line interface for converting raster images to SVG.
"""

import sys
from enum import Enum
from pathlib import Path
from typing import Optional, Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich import box
from dataclasses import dataclass
from typing import Dict, Any, Optional, Annotated

# Import icon processing
try:
    from vectalab.icon import is_monochrome_icon, process_geometric_icon
    ICON_MODULE_AVAILABLE = True
except ImportError:
    ICON_MODULE_AVAILABLE = False

from vectalab.quality import calculate_full_metrics

@dataclass
class VectorizationResult:
    input_path: Path
    output_path: Path
    method: str
    metrics: Dict[str, Any]
    error: Optional[str] = None

# Initialize Typer app and Rich console
app = typer.Typer(
    name="vectalab",
    help="🎨 [bold cyan]Vectalab[/] - Professional High-Fidelity Image Vectorization\n\n"
         "Convert raster images (PNG, JPG) to scalable vector graphics (SVG) "
         "with [bold green]99.8%+ structural similarity[/].",
    rich_markup_mode="rich",
    add_completion=True,
    no_args_is_help=True,
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
)

console = Console()
error_console = Console(stderr=True, style="bold red")


class Method(str, Enum):
    """Vectorization method."""
    auto = "auto"
    hifi = "hifi"
    bayesian = "bayesian"
    sam = "sam"


class Quality(str, Enum):
    """Quality preset for vectorization."""
    figma = "figma"
    balanced = "balanced"
    quality = "quality"
    ultra = "ultra"


class LogoQuality(str, Enum):
    """Quality preset for logo vectorization."""
    clean = "clean"
    balanced = "balanced"
    high = "high"
    ultra = "ultra"


class Device(str, Enum):
    """Compute device."""
    auto = "auto"
    cpu = "cpu"
    cuda = "cuda"
    mps = "mps"


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        from vectalab import __version__
        console.print(Panel(
            f"[bold cyan]Vectalab[/] version [bold green]{__version__}[/]\n\n"
            "🌐 https://vectalab.com",
            title="Version Info",
            border_style="cyan",
        ))
        raise typer.Exit()


def show_banner():
    """Display a beautiful banner."""
    banner = """
[bold cyan]╦  ╦╔═╗╔═╗╔╦╗╔═╗╦  ╔═╗╔╗ [/]
[bold cyan]╚╗╔╝║╣ ║   ║ ╠═╣║  ╠═╣╠╩╗[/]
[bold cyan] ╚╝ ╚═╝╚═╝ ╩ ╩ ╩╩═╝╩ ╩╚═╝[/]
    """
    console.print(banner)
    console.print("[dim]Professional High-Fidelity Image Vectorization[/]\n")


def validate_input_file(path: Path) -> Path:
    """Validate that input file exists and is a supported image format."""
    if not path.exists():
        error_console.print(f"❌ Input file not found: [yellow]{path}[/]")
        raise typer.Exit(1)
    
    supported = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
    if path.suffix.lower() not in supported:
        error_console.print(
            f"❌ Unsupported format: [yellow]{path.suffix}[/]\n"
            f"   Supported formats: {', '.join(sorted(supported))}"
        )
        raise typer.Exit(1)
    
    return path


def validate_output_file(path: Path) -> Path:
    """Validate output path."""
    if path.suffix.lower() != '.svg':
        # Auto-add .svg extension
        path = path.with_suffix('.svg')
    
    # Create parent directory if needed
    path.parent.mkdir(parents=True, exist_ok=True)
    
    return path


def get_device(device: Device) -> str:
    """Resolve device selection."""
    if device == Device.auto:
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"
    return device.value


def format_ssim(ssim: float) -> Text:
    """Format SSIM value with color based on quality."""
    percentage = ssim * 100
    if percentage >= 99.8:
        color = "bold green"
        emoji = "✅"
    elif percentage >= 99.0:
        color = "green"
        emoji = "👍"
    elif percentage >= 95.0:
        color = "yellow"
        emoji = "⚠️"
    else:
        color = "red"
        emoji = "❌"
    
    return Text(f"{emoji} {percentage:.2f}%", style=color)


@app.command("convert", rich_help_panel="Commands")
def convert(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to input image (PNG, JPG, etc.)",
            show_default=False,
        )
    ],
    output_file: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path for output SVG [dim](default: input_name.svg)[/]",
            show_default=False,
        )
    ] = None,
    method: Annotated[
        Method,
        typer.Option(
            "--method", "-m",
            help="Vectorization method to use",
            rich_help_panel="Vectorization Options",
        )
    ] = Method.hifi,
    quality: Annotated[
        Quality,
        typer.Option(
            "--quality", "-q",
            help="Quality preset [dim](affects speed vs fidelity)[/]",
            rich_help_panel="Vectorization Options",
        )
    ] = Quality.ultra,
    target_ssim: Annotated[
        float,
        typer.Option(
            "--target", "-t",
            help="Target SSIM similarity (0.0-1.0)",
            min=0.0,
            max=1.0,
            rich_help_panel="Vectorization Options",
        )
    ] = 0.998,
    device: Annotated[
        Device,
        typer.Option(
            "--device", "-d",
            help="Compute device for processing",
            rich_help_panel="Performance Options",
        )
    ] = Device.auto,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
            help="Show detailed progress information",
        )
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            help="Suppress all output except errors",
        )
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f",
            help="Overwrite output file if it exists",
        )
    ] = False,
    use_modal: Annotated[
        bool,
        typer.Option(
            "--use-modal",
            help="Use Modal.com for remote SAM execution",
            rich_help_panel="Performance Options",
        )
    ] = False,
):
    """
    🎨 Convert an image to high-fidelity SVG.
    
    [bold]Examples:[/]
    
      [dim]# Basic conversion (auto-detects best settings)[/]
      $ vectalab convert logo.png
      
      [dim]# Specify output path[/]
      $ vectalab convert photo.jpg output.svg
      
      [dim]# Fast conversion for previews[/]
      $ vectalab convert image.png -q figma
      
      [dim]# Maximum quality with custom target[/]
      $ vectalab convert icon.png -m hifi -t 0.999
    """
    # Validate input
    input_path = validate_input_file(input_file)
    
    # Generate output path if not specified
    if output_file is None:
        output_file = input_path.with_suffix('.svg')
    output_path = validate_output_file(output_file)
    
    # Check if output exists
    if output_path.exists() and not force:
        if not quiet:
            overwrite = typer.confirm(
                f"Output file {output_path} already exists. Overwrite?",
                default=False
            )
            if not overwrite:
                console.print("[yellow]Operation cancelled.[/]")
                raise typer.Exit(0)
    
    if not quiet:
        show_banner()
        
        # Show conversion info
        info_table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value")
        info_table.add_row("📁 Input", str(input_path))
        info_table.add_row("📄 Output", str(output_path))
        info_table.add_row("🔧 Method", method.value.upper())
        info_table.add_row("⚡ Quality", quality.value)
        info_table.add_row("🎯 Target SSIM", f"{target_ssim * 100:.1f}%")
        info_table.add_row("💻 Device", get_device(device))
        console.print(info_table)
        console.print()
    
    try:
        if method == Method.auto:
            _run_auto_conversion(
                input_path, output_path, target_ssim, quality, device, verbose, quiet, use_modal
            )
        elif method == Method.hifi:
            _run_hifi_conversion(
                input_path, output_path, target_ssim, quality, verbose, quiet
            )
        else:
            _run_standard_conversion(
                input_path, output_path, method, quality, device, verbose, quiet, use_modal
            )
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Operation cancelled by user.[/]")
        raise typer.Exit(130)
    except Exception as e:
        error_console.print(f"❌ Conversion failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


from vectalab.auto import determine_auto_mode

def _run_auto_conversion(
    input_path: Path,
    output_path: Path,
    target_ssim: float,
    quality: Quality,
    device: Device,
    verbose: bool,
    quiet: bool,
    use_modal: bool,
):
    """Run auto-detected vectorization."""
    
    # Use centralized auto logic
    effective_mode, effective_quality, mono_color = determine_auto_mode(str(input_path))
    
    if effective_mode == "geometric_icon" and ICON_MODULE_AVAILABLE:
        if not quiet:
            console.print("[cyan]ℹ️  Detected monochrome geometric icon.[/]")
            console.print("[cyan]🚀 Using specialized geometric icon strategy...[/]")
        
        with console.status("[cyan]Processing geometric icon...[/]"):
            success, result = process_geometric_icon(
                str(input_path), 
                str(output_path), 
                mono_color, 
                verbose=verbose
            )
            
        if success:
            if not quiet:
                # Calculate and show full metrics
                metrics = calculate_full_metrics(str(input_path), str(output_path))
                result = VectorizationResult(
                    input_path=input_path,
                    output_path=output_path,
                    method='Geometric Icon',
                    metrics=metrics
                )
                display_session_summary(result)
            return
        else:
            if not quiet:
                console.print("[yellow]⚠️ Geometric icon processing failed, falling back to standard method.[/]")
    
    # Fallback or other modes
    try:
        from vectalab.premium import vectorize_premium, vectorize_logo_premium
        
        if effective_mode == "logo":
            if not quiet:
                console.print("[cyan]ℹ️  Detected logo.[/]")
                console.print("[cyan]🚀 Using Logo Premium method...[/]")
            
            with console.status("[cyan]Vectorizing...[/]"):
                vectorize_logo_premium(str(input_path), str(output_path), verbose=verbose)
            
            # FEEDBACK LOOP: Check LPIPS
            metrics = calculate_full_metrics(str(input_path), str(output_path))
            lpips_val = metrics.get('lpips')
            
            # If LPIPS is high (> 0.15), it might be a complex illustration misclassified as a logo
            # or a logo with gradients that 'logo' mode handled poorly.
            if lpips_val is not None and lpips_val > 0.15:
                if not quiet:
                    console.print(f"[yellow]⚠️  Quality check warning (LPIPS {lpips_val:.3f} > 0.15).[/]")
                    console.print("[cyan]🔄 Retrying with Premium Photo method for better detail...[/]")
                
                with console.status("[cyan]Re-vectorizing (Attempt 2)...[/]"):
                    vectorize_premium(str(input_path), str(output_path), verbose=verbose)
                
                # Recalculate metrics for new result
                metrics = calculate_full_metrics(str(input_path), str(output_path))
                result = VectorizationResult(
                    input_path=input_path,
                    output_path=output_path,
                    method='Premium (Auto-Retry)',
                    metrics=metrics
                )
            else:
                result = VectorizationResult(
                    input_path=input_path,
                    output_path=output_path,
                    method='Logo Premium',
                    metrics=metrics
                )

            if not quiet:
                display_session_summary(result)
            return
            
        elif effective_mode == "premium":
            if not quiet:
                console.print("[cyan]ℹ️  Detected photograph/complex image.[/]")
                console.print("[cyan]🚀 Using Premium method...[/]")
            
            with console.status("[cyan]Vectorizing...[/]"):
                vectorize_premium(str(input_path), str(output_path), verbose=verbose)
            if not quiet:
                metrics = calculate_full_metrics(str(input_path), str(output_path))
                result = VectorizationResult(
                    input_path=input_path,
                    output_path=output_path,
                    method='Premium',
                    metrics=metrics
                )
                display_session_summary(result)
            return

    except ImportError:
        pass # Missing dependencies
    except Exception as e:
        if verbose:
            console.print(f"[yellow]Analysis failed: {e}[/]")

    # 3. Fallback to HiFi
    if not quiet:
        console.print("[cyan]ℹ️  Using HiFi method.[/]")
        
    _run_hifi_conversion(
        input_path, output_path, target_ssim, quality, verbose, quiet
    )





def display_session_summary(result: VectorizationResult):
    """Display conversion results with full metrics."""
    metrics = result.metrics
    output_path = result.output_path
    
    if result.error:
        console.print(f"[bold red]❌ Error:[/ {result.error}")
        return

    size_bytes = metrics.get('file_size', output_path.stat().st_size)
    
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
    
    # Create results table
    result_table = Table(box=box.ROUNDED, show_header=True, border_style="green", header_style="bold cyan")
    result_table.add_column("Metric", style="bold")
    result_table.add_column("Value")
    result_table.add_column("Meaning", style="dim")
    
    # Method
    result_table.add_row("Strategy", result.method, "Selected vectorization strategy")
    
    # SSIM
    ssim_val = metrics.get('ssim', 0)
    ssim_text = format_ssim(ssim_val / 100.0) # format_ssim expects 0-1
    result_table.add_row("Quality (SSIM)", ssim_text, "Pixel-perfect similarity")
    
    # LPIPS
    lpips_val = metrics.get('lpips')
    if lpips_val is not None:
        lpips_style = "bold green" if lpips_val < 0.1 else "yellow" if lpips_val < 0.3 else "red"
        result_table.add_row("Perceptual (LPIPS)", Text(f"{lpips_val:.4f}", style=lpips_style), "Human perceptual distance (lower is better)")
        
    # DISTS
    dists_val = metrics.get('dists')
    if dists_val is not None:
        dists_style = "bold green" if dists_val < 0.1 else "yellow" if dists_val < 0.2 else "red"
        result_table.add_row("Texture (DISTS)", Text(f"{dists_val:.4f}", style=dists_style), "Structure/Texture distance (lower is better)")

    # GMSD
    gmsd_val = metrics.get('gmsd')
    if gmsd_val is not None:
        gmsd_style = "bold green" if gmsd_val < 0.1 else "yellow" if gmsd_val < 0.2 else "red"
        result_table.add_row("Gradient (GMSD)", Text(f"{gmsd_val:.4f}", style=gmsd_style), "Gradient magnitude deviation (lower is better)")
    
    # Topology
    topo = metrics.get('topology', 0)
    result_table.add_row("Topology", f"{topo:.1f}%", "Preservation of holes and islands")
    
    # Edge Accuracy
    edge = metrics.get('edge', 0)
    result_table.add_row("Edge Accuracy", f"{edge:.1f}%", "Geometric alignment of boundaries")
    
    # Curve Fraction
    curve = metrics.get('curve_fraction', 0)
    result_table.add_row("Curve Fraction", f"{curve:.1f}%", "Percentage of curved segments")
    
    # Delta E
    de = metrics.get('delta_e', 0)
    de_style = "green" if de < 2.3 else "yellow" if de < 10 else "red"
    result_table.add_row("Color Error (ΔE)", Text(f"{de:.2f}", style=de_style), "Color deviation (lower is better)")
    
    # File size
    result_table.add_row("File Size", size_str, "Output SVG file size")
    
    result_table.add_row("Output", str(output_path), "Path to generated file")
    
    title = "🚀 Vectorization Complete"
    border_style = "green"
    
    console.print()
    console.print(Panel(result_table, title=title, border_style=border_style))


def _run_hifi_conversion(
    input_path: Path,
    output_path: Path,
    target_ssim: float,
    quality: Quality,
    verbose: bool,
    quiet: bool,
):
    """Run high-fidelity vectorization with optimization."""
    from vectalab.hifi import vectorize_high_fidelity
    
    # Map quality enum to preset name
    preset = quality.value
    
    if not quiet:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Vectorizing...", total=None)
            
            svg_path, stats = vectorize_high_fidelity(
                str(input_path),
                str(output_path),
                preset=preset,
                optimize=True,
                verbose=verbose,
            )
            
            progress.update(task, completed=100, total=100)
        
        # Calculate and show full metrics
        metrics = calculate_full_metrics(str(input_path), str(output_path))
        result = VectorizationResult(
            input_path=input_path,
            output_path=output_path,
            method=f'HiFi ({preset})',
            metrics=metrics
        )
        display_session_summary(result)
    else:
        svg_path, stats = vectorize_high_fidelity(
            str(input_path),
            str(output_path),
            preset=preset,
            optimize=True,
            verbose=False,
        )


def _run_standard_conversion(
    input_path: Path,
    output_path: Path,
    method: Method,
    quality: Quality,
    device: Device,
    verbose: bool,
    quiet: bool,
    use_modal: bool = False,
):
    """Run standard vectorization (SAM or Bayesian)."""
    from vectalab.core import Vectalab
    
    resolved_device = get_device(device)
    
    if not quiet:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Initializing...", total=4)
            
            vm = Vectalab(
                method=method.value,
                device=resolved_device,
                use_modal=use_modal,
            )
            progress.update(task, advance=1, description="[cyan]Segmenting...")
            
            vm.vectorize(str(input_path), str(output_path))
            progress.update(task, completed=4)
        
        # Calculate and show full metrics
        metrics = calculate_full_metrics(str(input_path), str(output_path))
        result = VectorizationResult(
            input_path=input_path,
            output_path=output_path,
            method=f'Standard ({method.value})',
            metrics=metrics
        )
        display_session_summary(result)
    else:
        vm = Vectalab(method=method.value, device=resolved_device, use_modal=use_modal)
        vm.vectorize(str(input_path), str(output_path))





@app.command("info", rich_help_panel="Commands")
def info(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to image file to analyze",
        )
    ],
):
    """
    📊 Display information about an image file.
    
    Shows dimensions, format, color mode, and recommended vectorization settings.
    """
    import cv2
    
    path = validate_input_file(input_file)
    
    # Load image info
    img = cv2.imread(str(path))
    if img is None:
        error_console.print(f"❌ Could not read image: {path}")
        raise typer.Exit(1)
    
    h, w = img.shape[:2]
    channels = img.shape[2] if len(img.shape) > 2 else 1
    size_bytes = path.stat().st_size
    
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
    
    # Analyze image
    is_small = max(w, h) <= 512
    
    # Build info table
    table = Table(title=f"📁 {path.name}", box=box.ROUNDED, border_style="cyan")
    table.add_column("Property", style="cyan bold")
    table.add_column("Value", style="white")
    
    table.add_row("Dimensions", f"{w} × {h} pixels")
    table.add_row("File Size", size_str)
    table.add_row("Format", path.suffix.upper().lstrip('.'))
    table.add_row("Channels", str(channels))
    table.add_row("Color Mode", "RGB" if channels == 3 else "RGBA" if channels == 4 else "Grayscale")
    
    console.print()
    console.print(table)
    
    # Recommendations
    rec_table = Table(title="💡 Recommendations", box=box.ROUNDED, border_style="yellow")
    rec_table.add_column("Setting", style="yellow bold")
    rec_table.add_column("Recommendation", style="white")
    
    if is_small:
        rec_table.add_row("Method", "[green]hifi[/] - Best for small images/icons")
        rec_table.add_row("Quality", "[green]ultra[/] - Maximum fidelity")
    else:
        rec_table.add_row("Method", "[yellow]hifi[/] or [yellow]bayesian[/]")
        rec_table.add_row("Quality", "[yellow]balanced[/] - Good speed/quality ratio")
    
    rec_table.add_row("Target SSIM", "[green]0.998[/] (99.8%)" if is_small else "[yellow]0.995[/] (99.5%)")
    
    console.print()
    console.print(rec_table)
    
    # Suggested command
    suggested_method = "hifi" if is_small else "bayesian"
    suggested_quality = "ultra" if is_small else "balanced"
    
    console.print()
    console.print(Panel(
        f"[dim]$[/] [bold]vectalab convert[/] {path} [cyan]-m {suggested_method} -q {suggested_quality}[/]",
        title="🚀 Suggested Command",
        border_style="dim",
    ))


@app.command("render", rich_help_panel="Commands")
def render(
    svg_file: Annotated[
        Path,
        typer.Argument(
            help="Path to SVG file to render",
        )
    ],
    output_file: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path for output PNG [dim](default: svg_name.png)[/]",
            show_default=False,
        )
    ] = None,
    scale: Annotated[
        int,
        typer.Option(
            "--scale", "-s",
            help="Scale factor for rendering",
            min=1,
            max=10,
        )
    ] = 1,
):
    """
    🖼️ Render an SVG file to PNG.
    
    Useful for verifying vectorization quality.
    """
    from vectalab.hifi import render_svg_to_png
    
    if not svg_file.exists():
        error_console.print(f"❌ SVG file not found: {svg_file}")
        raise typer.Exit(1)
    
    if output_file is None:
        output_file = svg_file.with_suffix('.png')
    
    with console.status("[cyan]Rendering SVG...[/]"):
        try:
            render_svg_to_png(str(svg_file), str(output_file), scale=scale)
            console.print(f"✅ Rendered to [cyan]{output_file}[/]")
        except Exception as e:
            error_console.print(f"❌ Render failed: {e}")
            raise typer.Exit(1)


@app.command("compare", rich_help_panel="Commands")
def compare(
    original: Annotated[
        Path,
        typer.Argument(
            help="Path to original image",
        )
    ],
    rendered: Annotated[
        Path,
        typer.Argument(
            help="Path to rendered/converted image",
        )
    ],
):
    """
    📏 Compare two images and show similarity metrics.
    
    Calculates SSIM, PSNR, and other quality metrics between two images.
    """
    import cv2
    import numpy as np
    
    for f in [original, rendered]:
        if not f.exists():
            error_console.print(f"❌ File not found: {f}")
            raise typer.Exit(1)
    
    # Load images
    img1 = cv2.imread(str(original))
    img2 = cv2.imread(str(rendered))
    
    if img1 is None or img2 is None:
        error_console.print("❌ Could not load one or both images")
        raise typer.Exit(1)
    
    # Resize if needed
    if img1.shape != img2.shape:
        console.print("[yellow]⚠️ Images have different sizes, resizing for comparison...[/]")
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    
    # Calculate metrics
    try:
        from skimage.metrics import structural_similarity as ssim
        from skimage.metrics import peak_signal_noise_ratio as psnr
        
        # Convert to RGB
        img1_rgb = cv2.cvtColor(img1, cv2.COLOR_BGR2RGB)
        img2_rgb = cv2.cvtColor(img2, cv2.COLOR_BGR2RGB)
        
        ssim_val = ssim(img1_rgb, img2_rgb, channel_axis=2, data_range=255)
        psnr_val = psnr(img1_rgb, img2_rgb, data_range=255)
        
        # Mean Absolute Error
        mae = np.mean(np.abs(img1_rgb.astype(float) - img2_rgb.astype(float)))
        
    except ImportError:
        error_console.print("❌ scikit-image required for comparison. Install with: pip install scikit-image")
        raise typer.Exit(1)
    
    # Display results
    table = Table(title="📏 Comparison Results", box=box.ROUNDED, border_style="cyan")
    table.add_column("Metric", style="cyan bold")
    table.add_column("Value", style="white")
    table.add_column("Quality", style="white")
    
    # SSIM row
    ssim_quality = format_ssim(ssim_val)
    table.add_row("SSIM", f"{ssim_val * 100:.2f}%", ssim_quality)
    
    # PSNR row
    if psnr_val >= 40:
        psnr_quality = Text("✅ Excellent", style="green")
    elif psnr_val >= 35:
        psnr_quality = Text("👍 Good", style="green")
    elif psnr_val >= 30:
        psnr_quality = Text("⚠️ Fair", style="yellow")
    else:
        psnr_quality = Text("❌ Poor", style="red")
    table.add_row("PSNR", f"{psnr_val:.2f} dB", psnr_quality)
    
    # MAE row
    table.add_row("MAE", f"{mae:.2f}", "Lower is better")
    
    console.print()
    console.print(table)


@app.command("optimal", rich_help_panel="Commands")
def optimal(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to input image (PNG, JPG, etc.)",
            show_default=False,
        )
    ],
    output_file: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path for output SVG [dim](default: input_name.svg)[/]",
            show_default=False,
        )
    ] = None,
    compare: Annotated[
        bool,
        typer.Option(
            "--compare", "-c",
            help="Generate comparison images (rendered PNG, diff map)",
        )
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
            help="Show detailed progress information",
        )
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f",
            help="Overwrite output file if it exists",
        )
    ] = False,
):
    """
    🎯 Optimal vectorization with pixel-perfect quality verification.
    
    This command uses the best settings found through extensive testing:
    - Bilateral filter preprocessing (removes JPEG noise, preserves edges)
    - Quality vtracer settings (high color precision, low layer difference)
    - Pixel-by-pixel quality metrics
    
    Achieves ~98.35% SSIM with reasonable file size (~50-100KB for logos).
    
    [bold]Examples:[/]
    
      [dim]# Basic conversion[/]
      $ vectalab optimal logo.png
      
      [dim]# With comparison images[/]
      $ vectalab optimal logo.jpg -c
      
      [dim]# Verbose output[/]
      $ vectalab optimal image.png -v
    """
    # Validate input
    input_path = validate_input_file(input_file)
    
    # Generate output path if not specified
    if output_file is None:
        output_file = input_path.with_suffix('.svg')
    output_path = validate_output_file(output_file)
    
    # Check if output exists
    if output_path.exists() and not force:
        overwrite = typer.confirm(
            f"Output file {output_path} already exists. Overwrite?",
            default=False
        )
        if not overwrite:
            console.print("[yellow]Operation cancelled.[/]")
            raise typer.Exit(0)
    
    show_banner()
    
    # Show info
    info_table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
    info_table.add_column("Property", style="cyan")
    info_table.add_column("Value")
    info_table.add_row("📁 Input", str(input_path))
    info_table.add_row("📄 Output", str(output_path))
    info_table.add_row("🔧 Method", "Optimal (bilateral + quality)")
    console.print(info_table)
    console.print()
    
    try:
        from vectalab.quality import vectorize_optimal, compare_and_visualize
        
        with console.status("[cyan]Vectorizing with optimal settings...[/]"):
            svg_path, metrics = vectorize_optimal(
                str(input_path),
                str(output_path),
                verbose=verbose,
            )
        
        # Generate comparison if requested
        if compare:
            with console.status("[cyan]Generating comparison images...[/]"):
                compare_and_visualize(str(input_path), svg_path, verbose=verbose)
        
        # Show results
        _show_optimal_results(output_path, metrics)
        
    except ImportError as e:
        error_console.print(f"❌ Missing dependency: {e}")
        error_console.print("Install with: pip install vtracer cairosvg scikit-image")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Operation cancelled by user.[/]")
        raise typer.Exit(130)
    except Exception as e:
        error_console.print(f"❌ Conversion failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


def _show_optimal_results(output_path: Path, metrics: dict):
    """Display optimal conversion results."""
    size_bytes = metrics.get('file_size', output_path.stat().st_size)
    
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
    
    # Create results table
    result_table = Table(box=box.ROUNDED, show_header=False, border_style="green")
    result_table.add_column("Metric", style="bold")
    result_table.add_column("Value")
    
    # SSIM
    ssim_val = metrics.get('ssim', 0)
    ssim_text = format_ssim(ssim_val)
    result_table.add_row("Quality (SSIM)", ssim_text)
    
    # PSNR
    psnr = metrics.get('psnr', 0)
    result_table.add_row("PSNR", f"{psnr:.2f} dB")
    
    # File size
    result_table.add_row("File Size", size_str)
    
    # Path count
    path_count = metrics.get('path_count', 0)
    result_table.add_row("SVG Paths", str(path_count))
    
    # Problem pixels
    problem_50 = metrics.get('problem_pixels_50', 0)
    problem_100 = metrics.get('problem_pixels_100', 0)
    result_table.add_row("Problem Pixels (>50)", f"{problem_50:,}")
    result_table.add_row("Problem Pixels (>100)", f"{problem_100:,}")
    
    result_table.add_row("Output", str(output_path))
    
    title = "🎯 Optimal Vectorization Complete"
    border_style = "green"
    
    console.print()
    console.print(Panel(result_table, title=title, border_style=border_style))


@app.command("logo", rich_help_panel="Commands")
def logo(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to input image (PNG, JPG, etc.)",
            show_default=False,
        )
    ],
    output_file: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path for output SVG [dim](default: input_name.svg)[/]",
            show_default=False,
        )
    ] = None,
    colors: Annotated[
        Optional[int],
        typer.Option(
            "--colors", "-c",
            help="Number of colors (8, 16, 24, 32). Auto-detect if not set.",
            min=2,
            max=256,
            rich_help_panel="Quality Options",
        )
    ] = None,
    quality: Annotated[
        LogoQuality,
        typer.Option(
            "--quality", "-q",
            help="Quality preset (clean, balanced, high, ultra)",
            rich_help_panel="Quality Options",
        )
    ] = LogoQuality.balanced,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
            help="Show detailed progress information",
        )
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f",
            help="Overwrite output file if it exists",
        )
    ] = False,
):
    """
    🎨 Logo vectorization with automatic color palette reduction.
    
    This command is optimized for logos, icons, and simple graphics:
    - Detects if image is a logo based on color distribution
    - Reduces to optimal color palette (8-32 colors) using K-means clustering
    - Creates clean, minimal SVG paths without dithering noise
    
    [bold]Examples:[/]
    
      [dim]# Auto-detect best settings[/]
      $ vectalab logo company_logo.png
      
      [dim]# Force 16 colors[/]
      $ vectalab logo icon.jpg -c 16
      
      [dim]# 8 colors for very simple logos[/]
      $ vectalab logo simple.png -c 8
    """
    # Validate input
    input_path = validate_input_file(input_file)
    
    # Generate output path if not specified
    if output_file is None:
        output_file = input_path.with_suffix('.svg')
    output_path = validate_output_file(output_file)
    
    # Check if output exists
    if output_path.exists() and not force:
        overwrite = typer.confirm(
            f"Output file {output_path} already exists. Overwrite?",
            default=False
        )
        if not overwrite:
            console.print("[yellow]Operation cancelled.[/]")
            raise typer.Exit(0)
    
    show_banner()
    
    # Show info
    info_table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
    info_table.add_column("Property", style="cyan")
    info_table.add_column("Value")
    info_table.add_row("📁 Input", str(input_path))
    info_table.add_row("📄 Output", str(output_path))
    info_table.add_row("🔧 Method", "Logo (palette reduction)")
    info_table.add_row("✨ Quality", quality.value)
    if colors:
        info_table.add_row("🎨 Colors", str(colors))
    else:
        info_table.add_row("🎨 Colors", "Auto-detect")
    console.print(info_table)
    console.print()
    
    try:
        from vectalab.quality import vectorize_logo_clean
        
        with console.status("[cyan]Analyzing and vectorizing logo...[/]"):
            svg_path, metrics = vectorize_logo_clean(
                str(input_path),
                str(output_path),
                n_colors=colors,
                quality_preset=quality.value,
                verbose=verbose,
            )
        
        # Show results
        _show_logo_results(output_path, metrics)
        
    except ImportError as e:
        error_console.print(f"❌ Missing dependency: {e}")
        error_console.print("Install with: pip install vtracer cairosvg scikit-image")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Operation cancelled by user.[/]")
        raise typer.Exit(130)
    except Exception as e:
        error_console.print(f"❌ Conversion failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


def _show_logo_results(output_path: Path, metrics: dict):
    """Display logo conversion results."""
    size_bytes = metrics.get('file_size', output_path.stat().st_size)
    
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
    
    # Create results table
    result_table = Table(box=box.ROUNDED, show_header=True, border_style="green", header_style="bold cyan")
    result_table.add_column("Metric", style="bold")
    result_table.add_column("Value")
    result_table.add_column("Meaning", style="dim")
    
    # Palette size
    palette = metrics.get('palette_size', 0)
    result_table.add_row("Color Palette", f"{palette} colors", "Number of unique colors used")
    
    # SSIM
    ssim_val = metrics.get('ssim', 0)
    ssim_text = format_ssim(ssim_val)
    result_table.add_row("Quality (SSIM)", ssim_text, "Pixel-perfect similarity (includes noise)")
    
    # Perceptual SSIM
    ssim_perceptual = metrics.get('ssim_perceptual', 0)
    if ssim_perceptual > 0:
        result_table.add_row("Visual Fidelity", f"{ssim_perceptual*100:.2f}%", "Structural similarity (ignores noise)")
    
    # Edge Similarity
    edge_sim = metrics.get('edge_similarity', 0)
    if edge_sim > 0:
        result_table.add_row("Edge Accuracy", f"{edge_sim*100:.2f}%", "Geometric alignment of boundaries")
        
    # Color Accuracy
    delta_e = metrics.get('delta_e', 0)
    if delta_e > 0:
        # Color code Delta E
        if delta_e < 2.3:
            de_style = "green" # Imperceptible
        elif delta_e < 10:
            de_style = "yellow" # Acceptable
        else:
            de_style = "red" # Bad
        result_table.add_row("Color Error (ΔE)", Text(f"{delta_e:.2f}", style=de_style), "Color deviation (lower is better)")
    
    # Topology
    topology = metrics.get('topology_score', 0)
    if topology > 0:
        result_table.add_row("Topology", f"{topology*100:.2f}%", "Preservation of holes and islands")
    
    # SSIM vs reduced
    ssim_reduced = metrics.get('ssim_vs_reduced', 0)
    result_table.add_row("SSIM vs Reduced", f"{ssim_reduced*100:.2f}%", "Similarity to palette-reduced image")
    
    # File size
    result_table.add_row("File Size", size_str, "Output SVG file size")
    
    # Path count
    path_count = metrics.get('path_count', 0)
    result_table.add_row("SVG Paths", str(path_count), "Number of independent shapes")
    
    # Segments
    segments = metrics.get('total_segments', 0)
    if segments > 0:
        result_table.add_row("Complexity", f"{segments} segments", "Total number of curve segments")
    
    result_table.add_row("Output", str(output_path), "Path to generated file")
    
    title = "🎨 Logo Vectorization Complete"
    border_style = "green"
    
    console.print()
    console.print(Panel(result_table, title=title, border_style=border_style))


@app.command("optimize", rich_help_panel="Commands")
def optimize_svg(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to input SVG file",
            show_default=False,
        )
    ],
    output_file: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path for output SVG [dim](default: overwrite input)[/]",
            show_default=False,
        )
    ] = None,
    precision: Annotated[
        int,
        typer.Option(
            "--precision", "-p",
            help="Coordinate precision (1-8, lower = smaller files)",
            min=1,
            max=8,
            rich_help_panel="Optimization Options",
        )
    ] = 2,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f",
            help="Overwrite output file without confirmation",
        )
    ] = False,
):
    """
    🔧 Optimize existing SVG files with SVGO.
    
    Use this command to compress SVG files you already have.
    Typically achieves 30-50% file size reduction while preserving quality.
    
    [bold cyan]When to use this vs 'premium':[/]
    • [bold]optimize[/]: You already have an SVG file to compress
    • [bold]premium[/]: You have a raster image (PNG/JPG) to convert to SVG
    
    [bold]Examples:[/]
    
      [dim]# Optimize SVG in-place[/]
      $ vectalab optimize icon.svg
      
      [dim]# Optimize to new file[/]
      $ vectalab optimize icon.svg icon_optimized.svg
      
      [dim]# Maximum compression[/]
      $ vectalab optimize icon.svg -p 1
    """
    # Validate input
    input_path = Path(input_file)
    if not input_path.exists():
        error_console.print(f"❌ Input file not found: [yellow]{input_path}[/]")
        raise typer.Exit(1)
    
    if input_path.suffix.lower() != '.svg':
        error_console.print(f"❌ Not an SVG file: [yellow]{input_path}[/]")
        error_console.print("   Use 'vectalab premium' for raster images (PNG, JPG)")
        raise typer.Exit(1)
    
    # Set output path
    if output_file is None:
        output_path = input_path
        overwrite_self = True
    else:
        output_path = Path(output_file)
        overwrite_self = False
    
    # Confirm overwrite
    if output_path.exists() and not force:
        if overwrite_self:
            msg = f"Optimize {input_path} in place?"
        else:
            msg = f"Output file {output_path} exists. Overwrite?"
        if not typer.confirm(msg, default=True):
            console.print("[yellow]Operation cancelled.[/]")
            raise typer.Exit(0)
    
    show_banner()
    
    # Read input
    with open(input_path, 'r') as f:
        original_svg = f.read()
    
    original_size = len(original_svg.encode('utf-8'))
    
    # Show info
    info_table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
    info_table.add_column("Property", style="cyan")
    info_table.add_column("Value")
    info_table.add_row("📁 Input", str(input_path))
    info_table.add_row("📄 Output", str(output_path))
    info_table.add_row("📐 Precision", str(precision))
    info_table.add_row("📊 Original Size", f"{original_size:,} bytes")
    console.print(info_table)
    console.print()
    
    try:
        from vectalab.optimizations import optimize_with_svgo, check_svgo_available
        
        if not check_svgo_available():
            console.print(Panel(
                "[yellow]⚠️ SVGO not installed[/]\n\n"
                "[bold]Install SVGO:[/]\n"
                "  [cyan]npm install -g svgo[/]\n\n"
                "[dim]Run 'vectalab svgo-info' for detailed instructions.[/]",
                title="💡 SVGO Required",
                border_style="yellow",
            ))
            raise typer.Exit(1)
        
        with console.status("[cyan]Optimizing SVG with SVGO...[/]"):
            optimized_svg, metrics = optimize_with_svgo(
                original_svg,
                precision=precision,
                multipass=True,
            )
        
        # Write output
        with open(output_path, 'w') as f:
            f.write(optimized_svg)
        
        # Show results
        optimized_size = metrics.get('optimized_size', len(optimized_svg.encode('utf-8')))
        reduction = metrics.get('reduction_percent', 0)
        
        result_table = Table(box=box.ROUNDED, show_header=False, border_style="green")
        result_table.add_column("Metric", style="bold")
        result_table.add_column("Value")
        
        result_table.add_row("Original Size", f"{original_size:,} bytes")
        result_table.add_row("Optimized Size", f"{optimized_size:,} bytes")
        result_table.add_row("Reduction", f"[green]{reduction:.1f}%[/]")
        result_table.add_row("Output", str(output_path))
        
        console.print()
        console.print(Panel(result_table, title="✨ SVG Optimization Complete", border_style="green"))
        
    except ImportError as e:
        error_console.print(f"❌ Missing dependency: {e}")
        raise typer.Exit(1)
    except Exception as e:
        error_console.print(f"❌ Optimization failed: {e}")
        raise typer.Exit(1)


@app.command("premium", rich_help_panel="Commands")
def premium(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to input image (PNG, JPG, etc.)",
            show_default=False,
        )
    ],
    output_file: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path for output SVG [dim](default: input_name.svg)[/]",
            show_default=False,
        )
    ] = None,
    target_ssim: Annotated[
        float,
        typer.Option(
            "--target-ssim", "-t",
            help="Target SSIM quality (0.90-1.0)",
            min=0.90,
            max=1.0,
            rich_help_panel="Quality Options",
        )
    ] = 0.98,
    colors: Annotated[
        Optional[int],
        typer.Option(
            "--colors", "-c",
            help="Force specific palette size (auto-detect if not set)",
            min=4,
            max=64,
            rich_help_panel="Quality Options",
        )
    ] = None,
    iterations: Annotated[
        int,
        typer.Option(
            "--iterations", "-i",
            help="Maximum refinement iterations",
            min=1,
            max=10,
            rich_help_panel="Quality Options",
        )
    ] = 5,
    mode: Annotated[
        str,
        typer.Option(
            "--mode", "-m",
            help="Optimization mode: 'logo' for logos/icons, 'photo' for photographs",
            rich_help_panel="Quality Options",
        )
    ] = "auto",
    svgo: Annotated[
        bool,
        typer.Option(
            "--svgo/--no-svgo",
            help="Apply SVGO optimization (30-50% smaller files)",
            rich_help_panel="80/20 Optimizations",
        )
    ] = True,
    precision: Annotated[
        int,
        typer.Option(
            "--precision", "-p",
            help="Coordinate precision (1-8, lower = smaller files)",
            min=1,
            max=8,
            rich_help_panel="80/20 Optimizations",
        )
    ] = 2,
    detect_shapes: Annotated[
        bool,
        typer.Option(
            "--shapes/--no-shapes",
            help="Detect shape primitives (circles, rectangles)",
            rich_help_panel="80/20 Optimizations",
        )
    ] = False,
    lab_metrics: Annotated[
        bool,
        typer.Option(
            "--lab/--no-lab",
            help="Use LAB color space for perceptually accurate quality metrics",
            rich_help_panel="80/20 Optimizations",
        )
    ] = True,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
            help="Show detailed progress information",
        )
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f",
            help="Overwrite output file if it exists",
        )
    ] = False,
):
    """
    ✨ Premium SOTA-quality vectorization with 80/20 optimizations.
    
    This command uses state-of-the-art techniques for the best possible output:
    
    [bold cyan]Core Features:[/]
    • Edge-aware preprocessing - Preserves sharp edges in text/logos
    • Iterative refinement - Keeps improving until quality target met
    • Color snapping - Rounds colors to exact values (pure black/white)
    • Path merging - Combines same-color paths for smaller files
    
    [bold magenta]80/20 Optimizations:[/]
    • SVGO integration - 30-50% file size reduction (requires Node.js)
    • Coordinate precision - Reduces file size by 10-15%
    • Shape detection - Identifies circles, rectangles, ellipses
    • LAB color metrics - Perceptually accurate quality measurement
    
    [bold]Examples:[/]
    
      [dim]# Auto-detect and optimize with SVGO[/]
      $ vectalab premium logo.png
      
      [dim]# Logo mode with shape detection[/]
      $ vectalab premium logo.jpg --mode logo --shapes
      
      [dim]# Maximum compression (lower precision)[/]
      $ vectalab premium image.png --precision 1
      
      [dim]# Disable SVGO if Node.js not available[/]
      $ vectalab premium image.png --no-svgo
    """
    # Validate input
    input_path = validate_input_file(input_file)
    
    # Generate output path if not specified
    if output_file is None:
        output_file = input_path.with_suffix('.svg')
    output_path = validate_output_file(output_file)
    
    # Check if output exists
    if output_path.exists() and not force:
        overwrite = typer.confirm(
            f"Output file {output_path} already exists. Overwrite?",
            default=False
        )
        if not overwrite:
            console.print("[yellow]Operation cancelled.[/]")
            raise typer.Exit(0)
    
    show_banner()
    
    # Check SVGO availability and show installation instructions if needed
    svgo_available = False
    if svgo:
        try:
            from vectalab.optimizations import check_svgo_available, check_node_available
            svgo_available = check_svgo_available()
            if not svgo_available:
                node_available = check_node_available()
                if not node_available:
                    console.print(Panel(
                        "[yellow]⚠️ SVGO optimization requires Node.js[/]\n\n"
                        "[bold]Install Node.js:[/]\n"
                        "  • macOS:   [cyan]brew install node[/]\n"
                        "  • Ubuntu:  [cyan]sudo apt install nodejs npm[/]\n"
                        "  • Windows: Download from [link=https://nodejs.org]nodejs.org[/link]\n"
                        "  • nvm:     [cyan]nvm install --lts[/]\n\n"
                        "[dim]Then install SVGO: [cyan]npm install -g svgo[/][/]",
                        title="💡 Enable SVGO for 30-50% smaller files",
                        border_style="yellow",
                    ))
                else:
                    console.print(Panel(
                        "[yellow]⚠️ SVGO not found but Node.js is available[/]\n\n"
                        "[bold]Install SVGO globally:[/]\n"
                        "  [cyan]npm install -g svgo[/]\n\n"
                        "[dim]SVGO v4.0+ is recommended for best results.[/]",
                        title="💡 Enable SVGO for 30-50% smaller files",
                        border_style="yellow",
                    ))
                console.print()
        except ImportError:
            pass
    
    # Show info
    info_table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
    info_table.add_column("Property", style="cyan")
    info_table.add_column("Value")
    info_table.add_row("📁 Input", str(input_path))
    info_table.add_row("📄 Output", str(output_path))
    info_table.add_row("🔧 Method", "Premium (SOTA + 80/20)")
    info_table.add_row("🎯 Target SSIM", f"{target_ssim*100:.0f}%")
    info_table.add_row("🔄 Iterations", str(iterations))
    info_table.add_row("📐 Precision", str(precision))
    if mode != "auto":
        info_table.add_row("📊 Mode", mode.capitalize())
    if colors:
        info_table.add_row("🎨 Colors", str(colors))
    svgo_status = "✓" if svgo_available else ("⚠️ Not installed" if svgo else "✗")
    info_table.add_row("🔧 SVGO", svgo_status)
    info_table.add_row("🔬 Shapes", "✓" if detect_shapes else "✗")
    info_table.add_row("🎨 LAB Metrics", "✓" if lab_metrics else "✗")
    console.print(info_table)
    console.print()
    
    try:
        from vectalab.premium import vectorize_premium, vectorize_logo_premium, vectorize_photo_premium
        
        with console.status("[cyan]Applying premium vectorization with 80/20 optimizations...[/]"):
            if mode == "logo":
                svg_path, metrics = vectorize_logo_premium(
                    str(input_path),
                    str(output_path),
                    use_svgo=svgo,
                    precision=precision,
                    detect_shapes=detect_shapes,
                    verbose=verbose,
                )
            elif mode == "photo":
                svg_path, metrics = vectorize_photo_premium(
                    str(input_path),
                    str(output_path),
                    n_colors=colors or 64,  # Updated default to 64 based on tuning
                    use_svgo=svgo,
                    precision=precision,
                    verbose=verbose,
                )
            else:  # auto
                svg_path, metrics = vectorize_premium(
                    str(input_path),
                    str(output_path),
                    target_ssim=target_ssim,
                    max_iterations=iterations,
                    n_colors=colors,
                    use_svgo=svgo,
                    precision=precision,
                    detect_shapes=detect_shapes,
                    use_lab_metrics=lab_metrics,
                    verbose=verbose,
                )
        
        # Show results
        _show_premium_results(output_path, metrics)
        
    except ImportError as e:
        error_console.print(f"❌ Missing dependency: {e}")
        error_console.print("Install with: pip install vtracer cairosvg scikit-image")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Operation cancelled by user.[/]")
        raise typer.Exit(130)
    except Exception as e:
        error_console.print(f"❌ Conversion failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


def _show_premium_results(output_path: Path, metrics: dict):
    """Display premium conversion results with 80/20 optimization details."""
    size_bytes = metrics.get('file_size', output_path.stat().st_size)
    
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
    
    # Create results table
    result_table = Table(box=box.ROUNDED, show_header=False, border_style="magenta")
    result_table.add_column("Metric", style="bold")
    result_table.add_column("Value")
    
    # SSIM RGB
    ssim_val = metrics.get('ssim', 0)
    target_ssim = metrics.get('target_ssim', 0.98)
    ssim_text = format_ssim(ssim_val)
    if ssim_val >= target_ssim:
        ssim_text += " ✅"
    result_table.add_row("Quality (SSIM RGB)", ssim_text)
    
    # SSIM LAB (if available)
    ssim_lab = metrics.get('ssim_lab', 0)
    if ssim_lab > 0:
        result_table.add_row("Quality (SSIM LAB)", f"{ssim_lab*100:.2f}%")
    
    # Delta E (if available)
    delta_e = metrics.get('delta_e', 0)
    if delta_e > 0:
        delta_e_quality = "Imperceptible" if delta_e < 1 else "Excellent" if delta_e < 2 else "Good" if delta_e < 5 else "Visible"
        result_table.add_row("Color Accuracy (ΔE)", f"{delta_e:.2f} ({delta_e_quality})")
    
    # File size
    result_table.add_row("File Size", size_str)
    
    # Size reduction (if available)
    size_reduction = metrics.get('size_reduction_percent', 0)
    if size_reduction > 0:
        result_table.add_row("Size Reduction", f"{size_reduction:.1f}%")
    
    # Path count
    path_count = metrics.get('path_count', 0)
    result_table.add_row("SVG Paths", str(path_count))
    
    # Color palette
    palette = metrics.get('palette_size', 0)
    orig_colors = metrics.get('original_colors', 0)
    if palette and orig_colors:
        result_table.add_row("Colors", f"{orig_colors:,} → {palette}")
    
    # Optimization details
    opt_metrics = metrics.get('optimizations', {})
    if opt_metrics:
        opts_applied = opt_metrics.get('optimizations_applied', [])
        if opts_applied:
            result_table.add_row("Optimizations", ", ".join(opts_applied))
        
        # Shape detection
        shapes = opt_metrics.get('shapes', {})
        if shapes:
            circles = shapes.get('circles_detected', 0)
            rects = shapes.get('rectangles_detected', 0)
            ellipses = shapes.get('ellipses_detected', 0)
            if circles or rects or ellipses:
                result_table.add_row("Shapes Detected", f"⭕ {circles} circles, ▢ {rects} rects, ⬭ {ellipses} ellipses")
    
    result_table.add_row("Output", str(output_path))
    
    title = "✨ Premium Vectorization Complete (80/20 Optimized)"
    
    console.print()
    console.print(Panel(result_table, title=title, border_style="magenta"))


@app.command("smart", rich_help_panel="Commands")
def smart(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to input image (PNG, JPG, etc.)",
            show_default=False,
        )
    ],
    output_file: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path for output SVG [dim](default: input_name.svg)[/]",
            show_default=False,
        )
    ] = None,
    target_size: Annotated[
        int,
        typer.Option(
            "--size", "-s",
            help="Target file size in KB",
            min=1,
            max=10000,
            rich_help_panel="Quality Options",
        )
    ] = 100,
    target_ssim: Annotated[
        float,
        typer.Option(
            "--quality", "-q",
            help="Minimum SSIM quality (0.0-1.0)",
            min=0.5,
            max=1.0,
            rich_help_panel="Quality Options",
        )
    ] = 0.92,
    max_iterations: Annotated[
        int,
        typer.Option(
            "--iterations", "-i",
            help="Maximum optimization iterations",
            min=1,
            max=20,
            rich_help_panel="Quality Options",
        )
    ] = 5,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
            help="Show detailed progress information",
        )
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f",
            help="Overwrite output file if it exists",
        )
    ] = False,
):
    """
    🚀 Smart vectorization with automatic optimization.
    
    This is the recommended command for vectorizing logos, icons, and illustrations.
    It automatically:
    
    • Detects image type (logo, icon, illustration, photo)
    • Applies optimal color quantization
    • Uses adaptive vtracer settings
    • Iteratively optimizes until targets are met
    
    [bold]Examples:[/]
    
      [dim]# Convert a logo (auto-detects settings)[/]
      $ vectalab smart logo.png
      
      [dim]# Target a specific file size[/]
      $ vectalab smart image.jpg -s 50
      
      [dim]# Higher quality threshold[/]
      $ vectalab smart photo.png -q 0.95
    """
    # Validate input
    input_path = validate_input_file(input_file)
    
    # Generate output path if not specified
    if output_file is None:
        output_file = input_path.with_suffix('.svg')
    output_path = validate_output_file(output_file)
    
    # Check if output exists
    if output_path.exists() and not force:
        overwrite = typer.confirm(
            f"Output file {output_path} already exists. Overwrite?",
            default=False
        )
        if not overwrite:
            console.print("[yellow]Operation cancelled.[/]")
            raise typer.Exit(0)
    
    show_banner()
    
    # Show info
    info_table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
    info_table.add_column("Property", style="cyan")
    info_table.add_column("Value")
    info_table.add_row("📁 Input", str(input_path))
    info_table.add_row("📄 Output", str(output_path))
    info_table.add_row("🎯 Target Size", f"{target_size} KB")
    info_table.add_row("⚡ Min Quality", f"{target_ssim * 100:.0f}%")
    info_table.add_row("🔄 Max Iterations", str(max_iterations))
    console.print(info_table)
    console.print()
    
    try:
        from vectalab.sota import vectorize_smart as sota_vectorize
        
        with console.status("[cyan]Analyzing image and optimizing...[/]"):
            svg_path, metrics = sota_vectorize(
                str(input_path),
                str(output_path),
                target_ssim=target_ssim,
                max_file_size=target_size * 1024,
                max_iterations=max_iterations,
                verbose=verbose,
            )
        
        # Show results
        _show_smart_results(output_path, metrics)
        
    except ImportError as e:
        error_console.print(f"❌ Missing dependency: {e}")
        error_console.print("Install with: pip install vtracer cairosvg scikit-image")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Operation cancelled by user.[/]")
        raise typer.Exit(130)
    except Exception as e:
        error_console.print(f"❌ Conversion failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command("auto", rich_help_panel="Commands")
def auto(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to input image (PNG, JPG, etc.)",
            show_default=False,
        )
    ],
    output_file: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path for output SVG [dim](default: input_name.svg)[/]",
            show_default=False,
        )
    ] = None,
    target_ssim: Annotated[
        float,
        typer.Option(
            "--quality", "-q",
            help="Minimum SSIM quality (0.0-1.0)",
            min=0.5,
            max=1.0,
            rich_help_panel="Quality Options",
        )
    ] = 0.95,
    workers: Annotated[
        int,
        typer.Option(
            "--workers", "-w",
            help="Number of parallel workers",
            min=1,
            max=16,
            rich_help_panel="Performance Options",
        )
    ] = 4,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
            help="Show detailed progress information",
        )
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f",
            help="Overwrite output file if it exists",
        )
    ] = False,
):
    """
    🤖 Auto mode: Run multiple strategies in parallel and pick the best one.
    
    This command runs 4 different vectorization strategies simultaneously:
    1. Logo Clean (Ultra)
    2. Premium Logo
    3. Premium Photo
    4. Smart Adaptive
    
    It then selects the best result based on a balance of SSIM quality and file size.
    
    [bold]Examples:[/]
    
      [dim]# Run auto optimization[/]
      $ vectalab auto image.png
      
      [dim]# Use more workers for faster results[/]
      $ vectalab auto image.png -w 8
    """
    # Validate input
    input_path = validate_input_file(input_file)
    
    # Generate output path if not specified
    if output_file is None:
        output_file = input_path.with_suffix('.svg')
    output_path = validate_output_file(output_file)
    
    # Check if output exists
    if output_path.exists() and not force:
        overwrite = typer.confirm(
            f"Output file {output_path} already exists. Overwrite?",
            default=False
        )
        if not overwrite:
            console.print("[yellow]Operation cancelled.[/]")
            raise typer.Exit(0)
    
    show_banner()
    
    # Show info
    info_table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
    info_table.add_column("Property", style="cyan")
    info_table.add_column("Value")
    info_table.add_row("📁 Input", str(input_path))
    info_table.add_row("📄 Output", str(output_path))
    info_table.add_row("🤖 Mode", "Auto (Parallel Competition)")
    info_table.add_row("⚡ Workers", str(workers))
    console.print(info_table)
    console.print()
    
    try:
        from vectalab.sota import vectorize_auto
        
        with console.status("[cyan]Running parallel strategies...[/]"):
            svg_path, metrics = vectorize_auto(
                str(input_path),
                str(output_path),
                target_ssim=target_ssim,
                max_workers=workers,
                verbose=verbose,
            )
        
        # Show results
        _show_smart_results(output_path, metrics)
        
    except ImportError as e:
        error_console.print(f"❌ Missing dependency: {e}")
        error_console.print("Install with: pip install vtracer cairosvg scikit-image")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Operation cancelled by user.[/]")
        raise typer.Exit(130)
    except Exception as e:
        error_console.print(f"❌ Conversion failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


def _show_smart_results(output_path: Path, metrics: dict):
    """Display smart conversion results."""
    size_bytes = metrics.get('file_size', output_path.stat().st_size)
    
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
    
    # Create results table
    result_table = Table(box=box.ROUNDED, show_header=False, border_style="green")
    result_table.add_column("Metric", style="bold")
    result_table.add_column("Value")
    
    # Image type
    image_type = metrics.get('image_type', 'unknown')
    result_table.add_row("Image Type", image_type.capitalize())
    
    # SSIM
    ssim_val = metrics.get('ssim', 0)
    ssim_text = format_ssim(ssim_val)
    result_table.add_row("Quality (SSIM)", ssim_text)
    
    # File size
    result_table.add_row("File Size", size_str)
    
    # Path count
    path_count = metrics.get('path_count', 0)
    result_table.add_row("SVG Paths", str(path_count))
    
    # Preset used
    preset = metrics.get('quality_preset', 'balanced')
    result_table.add_row("Preset Used", preset.capitalize())
    
    result_table.add_row("Output", str(output_path))
    
    title = "🚀 Smart Vectorization Complete"
    border_style = "green"
    
    console.print()
    console.print(Panel(result_table, title=title, border_style=border_style))


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version", "-V",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        )
    ] = None,
):
    """
    🎨 [bold cyan]Vectalab[/] - Professional High-Fidelity Image Vectorization
    
    Convert raster images to SVG with [bold green]99.8%+ structural similarity[/].
    
    [bold]Quick Start:[/]
    
      [dim]# Convert an image to SVG[/]
      $ vectalab convert image.png
      
      [dim]# Get info about an image[/]
      $ vectalab info image.png
      
      [dim]# Check SVGO status[/]
      $ vectalab svgo-info
    
    [bold]Learn More:[/]
    
      🌐 https://vectalab.com
      📖 https://github.com/vectalab/vectalab
    """
    # If no command is provided and help is not requested, show help
    if ctx.invoked_subcommand is None:
        # The help will be shown automatically due to no_args_is_help=True
        pass


@app.command("svgo-info", rich_help_panel="Utilities")
def svgo_info():
    """
    📦 Check SVGO installation status and get installation instructions.
    
    SVGO (SVG Optimizer) is a Node.js tool that provides 30-50% additional
    file size reduction for SVG files. It's highly recommended for the
    'premium' command.
    
    [bold]Examples:[/]
    
      [dim]# Check if SVGO is available[/]
      $ vectalab svgo-info
    """
    console.print()
    console.print("[bold cyan]📦 SVGO (SVG Optimizer) Status[/]")
    console.print()
    
    # Check Node.js
    node_available = False
    node_version = None
    try:
        import subprocess
        result = subprocess.run(
            ['node', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            node_available = True
            node_version = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Check SVGO
    svgo_available = False
    svgo_version = None
    try:
        import subprocess
        result = subprocess.run(
            ['svgo', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            svgo_available = True
            svgo_version = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Build status table
    status_table = Table(box=box.ROUNDED, show_header=False, border_style="cyan")
    status_table.add_column("Component", style="bold")
    status_table.add_column("Status")
    status_table.add_column("Version")
    
    if node_available:
        status_table.add_row("Node.js", "[green]✓ Installed[/]", node_version or "")
    else:
        status_table.add_row("Node.js", "[red]✗ Not found[/]", "")
    
    if svgo_available:
        status_table.add_row("SVGO", "[green]✓ Installed[/]", f"v{svgo_version}" if svgo_version else "")
    else:
        status_table.add_row("SVGO", "[yellow]⚠ Not installed[/]", "")
    
    console.print(status_table)
    console.print()
    
    if svgo_available:
        console.print(Panel(
            "[green]✅ SVGO is ready to use![/]\n\n"
            "The 'premium' command will automatically use SVGO\n"
            "for 30-50% additional file size reduction.\n\n"
            "[bold]Usage:[/]\n"
            "  [cyan]vectalab premium image.png --svgo[/]",
            title="🎉 All Set!",
            border_style="green",
        ))
    elif node_available:
        console.print(Panel(
            "[bold]Install SVGO globally:[/]\n\n"
            "  [cyan]npm install -g svgo[/]\n\n"
            "[dim]SVGO v4.0+ is recommended for best compatibility.[/]\n\n"
            "[bold]Verify installation:[/]\n"
            "  [cyan]svgo --version[/]",
            title="📥 Install SVGO",
            border_style="yellow",
        ))
    else:
        console.print(Panel(
            "[bold]Step 1: Install Node.js[/]\n\n"
            "  • [bold]macOS (Homebrew):[/]\n"
            "    [cyan]brew install node[/]\n\n"
            "  • [bold]macOS/Linux (nvm - recommended):[/]\n"
            "    [cyan]curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash[/]\n"
            "    [cyan]nvm install --lts[/]\n\n"
            "  • [bold]Ubuntu/Debian:[/]\n"
            "    [cyan]sudo apt update && sudo apt install nodejs npm[/]\n\n"
            "  • [bold]Windows:[/]\n"
            "    Download from [link=https://nodejs.org]https://nodejs.org[/link]\n\n"
            "[bold]Step 2: Install SVGO[/]\n\n"
            "  [cyan]npm install -g svgo[/]\n\n"
            "[bold]Step 3: Verify[/]\n\n"
            "  [cyan]svgo --version[/]",
            title="📥 Installation Instructions",
            border_style="yellow",
        ))
    
    console.print()


# Convenience alias for the main convert command
@app.command("hifi", hidden=True)
def hifi_alias(
    input_file: Annotated[Path, typer.Argument(help="Input image")],
    output_file: Annotated[Optional[Path], typer.Argument(help="Output SVG")] = None,
    target: Annotated[float, typer.Option("--target", "-t", min=0.0, max=1.0)] = 0.998,
    quality: Annotated[Quality, typer.Option("--quality", "-q")] = Quality.ultra,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
):
    """Alias for 'convert --method hifi'."""
    convert(
        input_file=input_file,
        output_file=output_file,
        method=Method.hifi,
        quality=quality,
        target_ssim=target,
        verbose=verbose,
        device=Device.auto,
        quiet=False,
        force=False,
    )


def run():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    app()