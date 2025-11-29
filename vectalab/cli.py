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
    hifi = "hifi"
    bayesian = "bayesian"
    sam = "sam"


class Quality(str, Enum):
    """Quality preset for vectorization."""
    fast = "fast"
    balanced = "balanced"
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
):
    """
    🎨 Convert an image to high-fidelity SVG.
    
    [bold]Examples:[/]
    
      [dim]# Basic conversion (auto-detects best settings)[/]
      $ vectalab convert logo.png
      
      [dim]# Specify output path[/]
      $ vectalab convert photo.jpg output.svg
      
      [dim]# Fast conversion for previews[/]
      $ vectalab convert image.png -q fast
      
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
        if method == Method.hifi:
            _run_hifi_conversion(
                input_path, output_path, target_ssim, quality, verbose, quiet
            )
        else:
            _run_standard_conversion(
                input_path, output_path, method, quality, device, verbose, quiet
            )
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Operation cancelled by user.[/]")
        raise typer.Exit(130)
    except Exception as e:
        error_console.print(f"❌ Conversion failed: {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


def _run_hifi_conversion(
    input_path: Path,
    output_path: Path,
    target_ssim: float,
    quality: Quality,
    verbose: bool,
    quiet: bool,
):
    """Run high-fidelity vectorization."""
    from vectalab.hifi import vectorize_high_fidelity
    
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
            
            svg_path, achieved_ssim = vectorize_high_fidelity(
                str(input_path),
                str(output_path),
                target_ssim=target_ssim,
                quality=quality.value,
                verbose=verbose,
            )
            
            progress.update(task, completed=100, total=100)
        
        # Show results
        _show_results(output_path, achieved_ssim, target_ssim)
    else:
        svg_path, achieved_ssim = vectorize_high_fidelity(
            str(input_path),
            str(output_path),
            target_ssim=target_ssim,
            quality=quality.value,
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
            )
            progress.update(task, advance=1, description="[cyan]Segmenting...")
            
            vm.vectorize(str(input_path), str(output_path))
            progress.update(task, completed=4)
        
        console.print(f"\n✅ [bold green]Success![/] Output saved to [cyan]{output_path}[/]")
    else:
        vm = Vectalab(method=method.value, device=resolved_device)
        vm.vectorize(str(input_path), str(output_path))


def _show_results(output_path: Path, achieved_ssim: float, target_ssim: float):
    """Display conversion results in a nice panel."""
    # Get file size
    size_bytes = output_path.stat().st_size
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
    
    ssim_text = format_ssim(achieved_ssim)
    result_table.add_row("SSIM Achieved", ssim_text)
    result_table.add_row("Target SSIM", f"{target_ssim * 100:.1f}%")
    result_table.add_row("File Size", size_str)
    result_table.add_row("Output", str(output_path))
    
    if achieved_ssim >= target_ssim:
        title = "✨ Conversion Complete"
        border_style = "green"
    else:
        title = "⚠️ Conversion Complete (below target)"
        border_style = "yellow"
    
    console.print()
    console.print(Panel(result_table, title=title, border_style=border_style))


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
    
    [bold]Learn More:[/]
    
      🌐 https://vectalab.com
      📖 https://github.com/vectalab/vectalab
    """
    # If no command is provided and help is not requested, show help
    if ctx.invoked_subcommand is None:
        # The help will be shown automatically due to no_args_is_help=True
        pass


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


