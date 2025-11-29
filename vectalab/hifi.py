"""
Vectalab High-Fidelity Vectorization Module.

This module implements a high-fidelity vectorization approach that creates
lightweight, Figma-compatible SVG files while maintaining visual quality.

The approach:
1. Use vtracer with optimized presets for base vectorization
2. Apply path simplification and shape primitive detection
3. Optimize the SVG with scour for minimal file size
4. Result: Clean, editable SVG files suitable for design tools

Usage:
    from vectalab.hifi import vectorize_high_fidelity
    
    svg_path = vectorize_high_fidelity(
        "input.png",
        "output.svg",
        preset="figma"  # or "balanced", "quality"
    )
"""

import numpy as np
import cv2
from PIL import Image
import io
import os
import xml.etree.ElementTree as ET
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

# Import optimizer module
from .optimize import (
    SVGOptimizer, 
    create_figma_optimizer, 
    create_quality_optimizer,
    get_vtracer_preset,
    VTRACER_PRESETS,
    optimize_svg_string,
)

# Try to import optional dependencies
try:
    import vtracer
    VTRACER_AVAILABLE = True
except ImportError:
    VTRACER_AVAILABLE = False

try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except ImportError:
    CAIROSVG_AVAILABLE = False

try:
    from skimage.metrics import structural_similarity as ssim
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False


def check_dependencies(require_metrics: bool = False):
    """Check that required dependencies are available."""
    missing = []
    if not VTRACER_AVAILABLE:
        missing.append("vtracer")
    if not CAIROSVG_AVAILABLE:
        missing.append("cairosvg")
    if require_metrics and not SKIMAGE_AVAILABLE:
        missing.append("scikit-image")
    
    if missing:
        raise ImportError(
            f"Missing required dependencies: {', '.join(missing)}. "
            f"Install with: pip install {' '.join(missing)}"
        )


def render_svg(svg_path: str, width: int, height: int, scale: int = 1) -> np.ndarray:
    """
    Render SVG to RGB numpy array.
    
    Args:
        svg_path: Path to SVG file
        width: Target width
        height: Target height
        scale: Supersampling scale (render at higher res then downsample)
        
    Returns:
        RGB numpy array [H, W, 3]
    """
    png_data = cairosvg.svg2png(
        url=svg_path,
        output_width=width * scale,
        output_height=height * scale
    )
    rendered = np.array(Image.open(io.BytesIO(png_data)).convert('RGB'))
    
    if scale > 1:
        rendered = cv2.resize(rendered, (width, height), interpolation=cv2.INTER_AREA)
    
    return rendered


def render_svg_string(svg_content: str, width: int, height: int) -> np.ndarray:
    """
    Render SVG content string to RGB numpy array.
    
    Args:
        svg_content: SVG content as string
        width: Target width
        height: Target height
        
    Returns:
        RGB numpy array [H, W, 3]
    """
    png_data = cairosvg.svg2png(
        bytestring=svg_content.encode('utf-8'),
        output_width=width,
        output_height=height
    )
    return np.array(Image.open(io.BytesIO(png_data)).convert('RGB'))


def create_base_vectorization(
    image_path: str,
    svg_path: str,
    preset: str = "balanced"
) -> None:
    """
    Create base vectorization using vtracer with optimized presets.
    
    Args:
        image_path: Path to input image
        svg_path: Path for output SVG
        preset: Preset name ('figma', 'balanced', 'quality', 'ultra')
    """
    settings = get_vtracer_preset(preset)
    vtracer.convert_image_to_svg_py(image_path, svg_path, **settings)


def get_svg_stats(svg_path: str) -> Dict[str, Any]:
    """
    Get statistics about an SVG file.
    
    Args:
        svg_path: Path to SVG file
        
    Returns:
        Dictionary with file stats
    """
    with open(svg_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return {
        'file_size': len(content.encode('utf-8')),
        'path_count': content.count('<path'),
        'element_count': content.count('<'),
    }


def vectorize_high_fidelity(
    input_path: str,
    output_path: str,
    preset: str = "balanced",
    optimize: bool = True,
    verbose: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """
    Vectorize an image to a clean, lightweight SVG suitable for design tools.
    
    This function creates an optimized SVG that is:
    - Lightweight (minimal file size)
    - Editable (clean structure for Figma, Illustrator, etc.)
    - Visually accurate (good quality reproduction)
    
    Args:
        input_path: Path to input image (PNG, JPG, etc.)
        output_path: Path for output SVG
        preset: Vectorization preset:
            - 'figma': Smallest file size, best for Figma/design tools
            - 'balanced': Good balance of size and quality
            - 'quality': Higher fidelity, larger files
            - 'ultra': Maximum quality (not recommended for large images)
        optimize: Apply post-processing optimization
        verbose: Print progress messages
        
    Returns:
        Tuple of (output_path, stats_dict)
        
    Example:
        >>> svg_path, stats = vectorize_high_fidelity("logo.png", "logo.svg")
        >>> print(f"Output: {stats['file_size']} bytes, {stats['path_count']} paths")
    """
    check_dependencies(require_metrics=False)
    
    # Load original image to get dimensions
    original = cv2.imread(input_path)
    if original is None:
        raise ValueError(f"Could not load image: {input_path}")
    
    original_rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
    h, w = original_rgb.shape[:2]
    
    if verbose:
        print(f"Input: {input_path} ({w}x{h})")
        print(f"Preset: {preset}")
    
    # Create base vectorization
    temp_svg = output_path.replace('.svg', '_temp.svg')
    create_base_vectorization(input_path, temp_svg, preset)
    
    if verbose:
        base_stats = get_svg_stats(temp_svg)
        print(f"Base vectorization: {base_stats['file_size']:,} bytes, {base_stats['path_count']} paths")
    
    # Optimize if requested
    if optimize:
        if verbose:
            print("Optimizing SVG...")
        
        # Choose optimizer based on preset
        if preset == 'figma':
            optimizer = create_figma_optimizer()
        else:
            optimizer = create_quality_optimizer()
        
        # Read and optimize
        with open(temp_svg, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        
        optimized_content = optimizer.optimize_string(svg_content)
        
        # Write optimized output
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(optimized_content)
        
        # Clean up temp file
        try:
            os.remove(temp_svg)
        except:
            pass
        
        stats = optimizer.get_stats(svg_content, optimized_content)
        
        if verbose:
            print(f"Optimized: {stats['optimized_size']:,} bytes ({stats['reduction_percent']:.1f}% reduction)")
            print(f"Paths: {stats['original_paths']} → {stats['optimized_paths']}")
    else:
        # Just rename temp to output
        import shutil
        shutil.move(temp_svg, output_path)
        
        stats = get_svg_stats(output_path)
        stats['reduction_percent'] = 0
    
    if verbose:
        print(f"✅ Output: {output_path}")
    
    return output_path, stats


def vectorize_for_figma(
    input_path: str,
    output_path: str,
    verbose: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """
    Convenience function for Figma-optimized vectorization.
    
    Creates the smallest possible SVG that looks good in Figma.
    
    Args:
        input_path: Path to input image
        output_path: Path for output SVG
        verbose: Print progress messages
        
    Returns:
        Tuple of (output_path, stats_dict)
    """
    return vectorize_high_fidelity(
        input_path, 
        output_path, 
        preset='figma',
        optimize=True,
        verbose=verbose
    )


def vectorize_with_quality(
    input_path: str,
    output_path: str,
    verbose: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """
    Convenience function for quality-focused vectorization.
    
    Creates higher fidelity SVG at the cost of larger file size.
    
    Args:
        input_path: Path to input image
        output_path: Path for output SVG
        verbose: Print progress messages
        
    Returns:
        Tuple of (output_path, stats_dict)
    """
    return vectorize_high_fidelity(
        input_path, 
        output_path, 
        preset='quality',
        optimize=True,
        verbose=verbose
    )


def compute_quality_metrics(
    input_path: str,
    svg_path: str,
    verbose: bool = False
) -> Dict[str, float]:
    """
    Compute quality metrics between original image and SVG.
    
    Args:
        input_path: Path to original image
        svg_path: Path to SVG file
        verbose: Print metrics
        
    Returns:
        Dictionary with quality metrics (SSIM, PSNR, etc.)
    """
    check_dependencies(require_metrics=True)
    
    # Load original
    original = cv2.imread(input_path)
    if original is None:
        raise ValueError(f"Could not load image: {input_path}")
    original_rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
    h, w = original_rgb.shape[:2]
    
    # Render SVG
    rendered = render_svg(svg_path, w, h, scale=2)
    
    # Compute SSIM
    ssim_value = ssim(original_rgb, rendered, channel_axis=2, data_range=255)
    
    # Compute PSNR
    mse = np.mean((original_rgb.astype(float) - rendered.astype(float)) ** 2)
    if mse > 0:
        psnr = 10 * np.log10(255 ** 2 / mse)
    else:
        psnr = float('inf')
    
    # Compute mean absolute error
    mae = np.mean(np.abs(original_rgb.astype(float) - rendered.astype(float)))
    
    metrics = {
        'ssim': ssim_value,
        'psnr': psnr,
        'mae': mae,
        'similarity_percent': ssim_value * 100,
    }
    
    if verbose:
        print(f"Quality Metrics:")
        print(f"  SSIM: {ssim_value:.4f} ({ssim_value*100:.2f}%)")
        print(f"  PSNR: {psnr:.2f} dB")
        print(f"  MAE: {mae:.2f}")
    
    return metrics
def render_svg_to_png(svg_path: str, png_path: str, scale: int = 1) -> str:
    """
    Render SVG to PNG file.
    
    Args:
        svg_path: Path to input SVG
        png_path: Path for output PNG
        scale: Scale factor for rendering
        
    Returns:
        Path to output PNG
    """
    check_dependencies(require_metrics=False)
    
    # Get SVG dimensions
    tree = ET.parse(svg_path)
    root = tree.getroot()
    
    # Try to get dimensions from viewBox or width/height
    viewbox = root.get('viewBox')
    if viewbox:
        parts = viewbox.split()
        if len(parts) >= 4:
            width = int(float(parts[2]))
            height = int(float(parts[3]))
        else:
            width = int(float(root.get('width', 100)))
            height = int(float(root.get('height', 100)))
    else:
        width = int(float(root.get('width', 100)))
        height = int(float(root.get('height', 100)))
    
    png_data = cairosvg.svg2png(
        url=svg_path,
        output_width=width * scale,
        output_height=height * scale
    )
    
    img = Image.open(io.BytesIO(png_data))
    if scale > 1:
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    
    img.save(png_path)
    return png_path


def list_presets() -> Dict[str, str]:
    """
    List available vectorization presets.
    
    Returns:
        Dictionary of preset names and descriptions
    """
    return {
        'figma': 'Smallest file size, best for Figma and design tools',
        'balanced': 'Good balance of file size and visual quality',
        'quality': 'Higher fidelity, larger files',
        'ultra': 'Maximum quality, may produce large files',
    }


# Command-line interface
if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Vectorize images to clean, optimized SVG files'
    )
    parser.add_argument('input', help='Input image path')
    parser.add_argument('output', help='Output SVG path')
    parser.add_argument(
        '-p', '--preset',
        choices=['figma', 'balanced', 'quality', 'ultra'],
        default='balanced',
        help='Vectorization preset (default: balanced)'
    )
    parser.add_argument(
        '--no-optimize',
        action='store_true',
        help='Skip post-processing optimization'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress output messages'
    )
    parser.add_argument(
        '--metrics',
        action='store_true',
        help='Compute and display quality metrics'
    )
    
    args = parser.parse_args()
    
    svg_path, stats = vectorize_high_fidelity(
        args.input,
        args.output,
        preset=args.preset,
        optimize=not args.no_optimize,
        verbose=not args.quiet
    )
    
    if args.metrics:
        metrics = compute_quality_metrics(args.input, svg_path, verbose=True)
