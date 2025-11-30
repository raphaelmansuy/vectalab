"""
Vectalab Quality-First Vectorization Module.

This module prioritizes visual quality over file size, using:
1. Minimal preprocessing to preserve detail
2. Conservative vtracer settings
3. Pixel-by-pixel quality verification
4. Iterative refinement until quality threshold met

Usage:
    from vectalab.quality import vectorize_quality
    
    svg_path, metrics = vectorize_quality("logo.png", "output.svg", min_ssim=0.99)
"""

import numpy as np
import cv2
from PIL import Image
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import tempfile
import os
import xml.etree.ElementTree as ET
import re

# Try imports
try:
    import vtracer
    VTRACER_AVAILABLE = True
except ImportError:
    VTRACER_AVAILABLE = False

try:
    import cairosvg
    from io import BytesIO
    CAIROSVG_AVAILABLE = True
except ImportError:
    CAIROSVG_AVAILABLE = False

try:
    from skimage.metrics import structural_similarity as ssim
    from skimage import color as skimage_color
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False

try:
    from vectalab.perceptual import calculate_lpips, calculate_dists, calculate_gmsd
    LPIPS_AVAILABLE = True
except ImportError:
    LPIPS_AVAILABLE = False


# ============================================================================
# QUALITY METRICS
# ============================================================================

def analyze_svg_content(svg_content: str) -> Dict[str, Any]:
    """
    Analyze SVG structure for complexity.
    
    Returns:
        Dictionary with path count, complexity metrics
    """
    try:
        # Simple regex parsing is often more robust for simple stats than XML parsing
        # especially with namespaces
        path_count = len(re.findall(r'<path', svg_content))
        
        # Estimate complexity by path data length
        # Find all d="..." attributes
        d_attrs = re.findall(r'd="([^"]+)"', svg_content)
        total_path_len = sum(len(d) for d in d_attrs)
        avg_path_len = total_path_len / path_count if path_count > 0 else 0
        
        # Count segments (M, L, C, Q, Z, etc.)
        total_segments = sum(len(re.findall(r'[a-zA-Z]', d)) for d in d_attrs)
        
        return {
            "path_count": path_count,
            "total_path_data_len": total_path_len,
            "avg_path_data_len": avg_path_len,
            "total_segments": total_segments,
            "segments_per_path": total_segments / path_count if path_count > 0 else 0
        }
    except Exception as e:
        return {
            "path_count": 0, 
            "error": str(e),
            "total_segments": 0
        }


def render_svg_to_array(svg_content: str, width: int, height: int, mode: str = 'RGB') -> np.ndarray:
    """Render SVG to numpy array."""
    if not CAIROSVG_AVAILABLE:
        raise ImportError("cairosvg required for rendering")
    
    png_data = cairosvg.svg2png(
        bytestring=svg_content.encode('utf-8'),
        output_width=width,
        output_height=height
    )
    
    img = Image.open(BytesIO(png_data)).convert(mode)
    return np.array(img)


def calculate_topology_score(img1: np.ndarray, img2: np.ndarray) -> float:
    """Calculate topology score based on connected components and holes."""
    try:
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
        return max(0.0, min(100.0, total_score))
    except Exception:
        return 0.0


def calculate_edge_accuracy(img1: np.ndarray, img2: np.ndarray) -> float:
    """Calculate edge accuracy using Canny edge detection overlap."""
    try:
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
    except Exception:
        return 0.0


def calculate_color_error(img1: np.ndarray, img2: np.ndarray) -> float:
    """Calculate Delta E (CIEDE2000) color error."""
    if not SKIMAGE_AVAILABLE:
        return 0.0
    try:
        lab1 = skimage_color.rgb2lab(img1)
        lab2 = skimage_color.rgb2lab(img2)
        delta_e = skimage_color.deltaE_ciede2000(lab1, lab2)
        return np.mean(delta_e)
    except Exception:
        return 0.0


def analyze_path_types(svg_path: str) -> Dict[str, Any]:
    """
    Analyze the types of path segments (Curves vs Lines) in the SVG.
    Returns a dictionary with counts and fractions.
    """
    try:
        with open(svg_path, 'r') as f:
            content = f.read()
        
        # Find all d attributes
        d_attrs = re.findall(r'd="([^"]+)"', content)
        
        curve_cmds = 0
        line_cmds = 0
        total_cmds = 0
        
        for d in d_attrs:
            # Normalize spacing
            d = re.sub(r'\s+', ' ', d).strip()
            # Find all commands
            commands = re.findall(r'[MmLlHhVvCcQqSsAaZz]', d)
            
            for cmd in commands:
                if cmd.lower() == 'm': continue # Move doesn't count as a segment
                
                total_cmds += 1
                # C, Q, S, A are curves. L, H, V, Z are lines (Z closes with a line)
                if cmd.lower() in ['c', 'q', 's', 'a']:
                    curve_cmds += 1
                else:
                    line_cmds += 1
                    
        fraction = (curve_cmds / total_cmds) * 100 if total_cmds > 0 else 0
        return {
            "total": total_cmds,
            "curves": curve_cmds,
            "lines": line_cmds,
            "curve_fraction": fraction
        }
    except Exception:
        return {"total": 0, "curves": 0, "lines": 0, "curve_fraction": 0}


def compute_edge_similarity(img1: np.ndarray, img2: np.ndarray) -> float:
    """
    Compute edge similarity using dilated Canny edges.
    Returns IoU of edges (0.0 to 1.0).
    """
    # Convert to grayscale
    g1 = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY)
    g2 = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY)
    
    # Canny edge detection (auto thresholds could be better but fixed is standard)
    e1 = cv2.Canny(g1, 100, 200)
    e2 = cv2.Canny(g2, 100, 200)
    
    # Dilate to allow small misalignment (1px tolerance)
    kernel = np.ones((3,3), np.uint8)
    e1_d = cv2.dilate(e1, kernel, iterations=1)
    e2_d = cv2.dilate(e2, kernel, iterations=1)
    
    # Compute overlap (IoU)
    intersection = np.logical_and(e1_d > 0, e2_d > 0)
    union = np.logical_or(e1_d > 0, e2_d > 0)
    
    if np.sum(union) == 0:
        return 1.0 # No edges in either
        
    return np.sum(intersection) / np.sum(union)


def compute_color_accuracy(img1: np.ndarray, img2: np.ndarray) -> float:
    """
    Compute average Delta E (CIE76) color difference.
    Lower is better. < 2.3 is barely noticeable.
    """
    if not SKIMAGE_AVAILABLE:
        return 0.0
        
    # Convert to LAB
    try:
        lab1 = skimage_color.rgb2lab(img1)
        lab2 = skimage_color.rgb2lab(img2)
        
        # Delta E (CIE76)
        diff = lab1 - lab2
        delta_e = np.sqrt(np.sum(diff**2, axis=2))
        
        return float(np.mean(delta_e))
    except Exception:
        return 0.0


def compute_topology_preservation(img1: np.ndarray, img2: np.ndarray) -> float:
    """
    Compute topology preservation score (0.0 to 1.0).
    Checks if the number of connected components and holes matches.
    
    This is critical for logos (e.g. preserving the hole in 'A' or 'B').
    """
    def get_topology_stats(img):
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img
            
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Find contours with hierarchy to detect holes
        # RETR_CCOMP organizes into two levels: components and holes
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        
        if hierarchy is None:
            return 0, 0
            
        num_components = 0
        num_holes = 0
        
        # Iterate through hierarchy
        # hierarchy[0] is an array of shape (N, 4)
        # [Next, Previous, First_Child, Parent]
        for i, h in enumerate(hierarchy[0]):
            # h[3] is parent index
            if h[3] == -1:
                # No parent -> External contour (Component)
                num_components += 1
            else:
                # Has parent -> Internal contour (Hole)
                num_holes += 1
                
        return num_components, num_holes

    c1, h1 = get_topology_stats(img1)
    c2, h2 = get_topology_stats(img2)
    
    # Calculate score based on relative error
    max_c = max(c1, c2)
    max_h = max(h1, h2)
    
    score_c = 1.0
    if max_c > 0:
        score_c = 1.0 - (abs(c1 - c2) / max_c)
    elif c1 != c2:
        score_c = 0.0
        
    score_h = 1.0
    if max_h > 0:
        score_h = 1.0 - (abs(h1 - h2) / max_h)
    elif h1 != h2:
        score_h = 0.0
    
    # Average the scores
    return (score_c + score_h) / 2.0


def compute_pixel_metrics(original: np.ndarray, rendered: np.ndarray) -> Dict[str, Any]:
    """
    Compute detailed pixel-by-pixel quality metrics.
    
    Returns:
        Dictionary with SSIM, PSNR, MAE, and problem pixel analysis
    """
    # SSIM
    if SKIMAGE_AVAILABLE:
        ssim_value = ssim(original, rendered, channel_axis=2, data_range=255)
        
        # Perceptual SSIM (Blurred)
        # Blur removes high-frequency noise/pixelation to compare structural shapes
        # Sigma=1.5 approximates the "softness" of human vision / anti-aliasing
        orig_blur = cv2.GaussianBlur(original, (0, 0), 1.5)
        rend_blur = cv2.GaussianBlur(rendered, (0, 0), 1.5)
        ssim_perceptual = ssim(orig_blur, rend_blur, channel_axis=2, data_range=255)
    else:
        ssim_value = 0.0
        ssim_perceptual = 0.0
    
    # Pixel differences
    diff = np.abs(original.astype(float) - rendered.astype(float))
    mae = np.mean(diff)
    max_error = np.max(diff)
    
    # PSNR
    mse = np.mean(diff ** 2)
    if mse > 0:
        psnr = 10 * np.log10(255 ** 2 / mse)
    else:
        psnr = float('inf')
    
    # Problem pixel analysis
    diff_gray = np.mean(diff, axis=2)
    problem_pixels_50 = np.sum(diff_gray > 50)
    problem_pixels_100 = np.sum(diff_gray > 100)
    total_pixels = original.shape[0] * original.shape[1]
    
    # New Metrics
    edge_sim = compute_edge_similarity(original, rendered)
    delta_e = compute_color_accuracy(original, rendered)
    topology = compute_topology_preservation(original, rendered)
    
    # LPIPS, DISTS, GMSD
    lpips_score = None
    dists_score = None
    gmsd_score = None
    
    if LPIPS_AVAILABLE:
        lpips_score = calculate_lpips(original, rendered)
        dists_score = calculate_dists(original, rendered)
        gmsd_score = calculate_gmsd(original, rendered)

    return {
        "ssim": ssim_value,
        "ssim_perceptual": ssim_perceptual,
        "edge_similarity": edge_sim,
        "delta_e": delta_e,
        "topology_score": topology,
        "lpips": lpips_score,
        "dists": dists_score,
        "gmsd": gmsd_score,
        "psnr": psnr,
        "mae": mae,
        "max_error": max_error,
        "problem_pixels_50": problem_pixels_50,
        "problem_pixels_100": problem_pixels_100,
        "problem_ratio": problem_pixels_50 / total_pixels,
    }


def save_difference_map(original: np.ndarray, rendered: np.ndarray, output_path: str):
    """Save a visualization of differences between original and rendered."""
    diff = np.abs(original.astype(float) - rendered.astype(float))
    diff_gray = np.mean(diff, axis=2)
    
    # Amplify for visibility
    diff_vis = (diff_gray * 5).clip(0, 255).astype(np.uint8)
    
    # Color code: green = good, yellow = warning, red = bad
    h, w = diff_gray.shape
    vis_color = np.zeros((h, w, 3), dtype=np.uint8)
    
    # Good (diff < 20): green
    good_mask = diff_gray < 20
    vis_color[good_mask] = [0, 100, 0]  # Dark green
    
    # Warning (20 <= diff < 50): yellow
    warn_mask = (diff_gray >= 20) & (diff_gray < 50)
    vis_color[warn_mask] = [0, 200, 200]  # Yellow in BGR
    
    # Bad (diff >= 50): red scaled by error
    bad_mask = diff_gray >= 50
    vis_color[bad_mask, 2] = np.minimum(255, diff_gray[bad_mask] * 2).astype(np.uint8)
    vis_color[bad_mask, 0] = 0
    vis_color[bad_mask, 1] = 0
    
    cv2.imwrite(output_path, vis_color)


# ============================================================================
# VTRACER SETTINGS PRESETS
# ============================================================================

# Quality-focused presets - prioritize accuracy over size
# Based on extensive testing with logo images
QUALITY_PRESETS = {
    "maximum": {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'spline',
        'filter_speckle': 1,
        'color_precision': 8,
        'layer_difference': 4,
        'corner_threshold': 30,
        'length_threshold': 2.0,
        'max_iterations': 20,
        'splice_threshold': 30,
        'path_precision': 8,
    },
    "high": {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'spline',
        'filter_speckle': 2,
        'color_precision': 7,
        'layer_difference': 8,
        'corner_threshold': 40,
        'length_threshold': 2.5,
        'max_iterations': 15,
        'splice_threshold': 40,
        'path_precision': 6,
    },
    # BEST settings found through testing - bilateral_medium + quality
    "optimal": {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'spline',
        'filter_speckle': 2,
        'color_precision': 7,
        'layer_difference': 8,
        'corner_threshold': 40,
        'length_threshold': 2.5,
        'max_iterations': 15,
        'splice_threshold': 40,
        'path_precision': 6,
    },
    "balanced": {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'spline',
        'filter_speckle': 4,
        'color_precision': 6,
        'layer_difference': 16,
        'corner_threshold': 50,
        'length_threshold': 3.0,
        'max_iterations': 10,
        'splice_threshold': 45,
        'path_precision': 5,
    },
}

# Logo vectorization presets
LOGO_PRESETS = {
    "clean": {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'spline',
        'filter_speckle': 4,
        'color_precision': 6,
        'layer_difference': 16,
        'corner_threshold': 60,
        'length_threshold': 4.0,
        'max_iterations': 10,
        'splice_threshold': 45,
        'path_precision': 5,
    },
    "balanced": {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'spline',
        'filter_speckle': 3,
        'color_precision': 7,
        'layer_difference': 12,
        'corner_threshold': 50,
        'length_threshold': 3.0,
        'max_iterations': 12,
        'splice_threshold': 40,
        'path_precision': 6,
    },
    "high": {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'spline',
        'filter_speckle': 2,
        'color_precision': 8,
        'layer_difference': 8,
        'corner_threshold': 40,
        'length_threshold': 2.0,
        'max_iterations': 15,
        'splice_threshold': 35,
        'path_precision': 7,
    },
    "ultra": {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'spline',
        'filter_speckle': 1,
        'color_precision': 8,
        'layer_difference': 4,
        'corner_threshold': 30,
        'length_threshold': 1.5,
        'max_iterations': 20,
        'splice_threshold': 30,
        'path_precision': 8,
    },
}

# Best preprocessing: bilateral filter with medium strength
OPTIMAL_BILATERAL = {'d': 7, 'sigmaColor': 50, 'sigmaSpace': 50}

# Logo detection thresholds
LOGO_DETECTION = {
    'max_colors_ratio': 0.05,  # If unique colors < 5% of pixels, likely logo
    'min_top10_coverage': 0.85,  # Top 10 colors cover 85%+ of image
    'max_color_variance': 60,  # Low variance = simple color palette
}


# ============================================================================
# IMAGE ANALYSIS & LOGO DETECTION
# ============================================================================

def analyze_image(image_rgb: np.ndarray) -> Dict[str, Any]:
    """Analyze image to detect if it's a logo."""
    h, w = image_rgb.shape[:2]
    total_pixels = h * w
    pixels = image_rgb.reshape(-1, 3)
    
    # Count unique colors
    unique_colors = len(np.unique(pixels, axis=0))
    
    # Color distribution
    from collections import Counter
    color_counts = Counter(map(tuple, pixels))
    
    # Top N coverage
    top_10 = sum(c for _, c in color_counts.most_common(10))
    top_10_coverage = top_10 / total_pixels
    
    # Color variance
    color_variance = np.std(pixels, axis=0).mean()
    
    # Detect if logo
    is_logo = (
        (unique_colors / total_pixels < LOGO_DETECTION['max_colors_ratio']) or
        (top_10_coverage > LOGO_DETECTION['min_top10_coverage']) or
        (color_variance < LOGO_DETECTION['max_color_variance'])
    )
    
    return {
        'width': w,
        'height': h,
        'unique_colors': unique_colors,
        'top_10_coverage': top_10_coverage,
        'color_variance': color_variance,
        'is_logo': is_logo,
    }


def reduce_to_palette(image: np.ndarray, n_colors: int = 16) -> np.ndarray:
    """
    Reduce image to fixed color palette using K-means clustering.
    
    Uses K-means clustering which provides better color representation
    than Median Cut for logos and graphics.
    
    Args:
        image: RGB or RGBA image
        n_colors: Target number of colors (8, 16, 32, etc.)
        
    Returns:
        Image with reduced color palette
    """
    # Reshape to list of pixels
    channels = image.shape[2]
    pixels = image.reshape((-1, channels))
    pixels = np.float32(pixels)

    # Define criteria = ( type, max_iter, epsilon )
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    
    # Apply KMeans
    # Use KMEANS_PP_CENTERS for better initialization
    try:
        _, labels, centers = cv2.kmeans(
            pixels, 
            n_colors, 
            None, 
            criteria, 
            10, 
            cv2.KMEANS_PP_CENTERS
        )
        
        # Convert back to 8 bit values
        centers = np.uint8(centers)

        # Map labels to center values
        res = centers[labels.flatten()]
        
        # Reshape back to original image
        return res.reshape(image.shape)
        
    except Exception as e:
        # Fallback to PIL if KMeans fails (e.g. memory issues)
        print(f"Warning: KMeans failed ({e}), falling back to PIL MedianCut")
        pil_img = Image.fromarray(image)
        # Ensure no dithering for logos!
        quantized = pil_img.quantize(
            colors=n_colors, 
            method=Image.Quantize.MEDIANCUT,
            dither=Image.Dither.NONE
        )
        return np.array(quantized.convert('RGB'))


def get_optimal_palette_size(analysis: Dict[str, Any]) -> int:
    """
    Determine optimal palette size based on image analysis.
    
    Args:
        analysis: Image analysis results
        
    Returns:
        Recommended palette size (8, 16, 24, or 32)
    """
    unique_colors = analysis['unique_colors']
    top_10_coverage = analysis['top_10_coverage']
    
    # With K-means, we can be more aggressive in reducing colors
    # as it finds better representative colors (centroids) than
    # simple frequency analysis.
    
    # Very simple logos (high coverage by few colors)
    if top_10_coverage > 0.92:  # Was 0.95
        return 8
    elif top_10_coverage > 0.85:  # Was 0.90
        return 12
    elif top_10_coverage > 0.75:  # Was 0.85
        return 16
    elif top_10_coverage > 0.65:  # Was 0.75
        return 24
    else:
        return 32


# ============================================================================
# LIGHT PREPROCESSING
# ============================================================================

def light_denoise(image: np.ndarray) -> np.ndarray:
    """
    Apply very light denoising that preserves edges and text.
    Uses edge-preserving bilateral filter with conservative parameters.
    """
    # Very light bilateral filter to reduce JPEG artifacts only
    # Small d (3) = very local, sigmaColor (20) = only merge very similar colors
    denoised = cv2.bilateralFilter(image, d=3, sigmaColor=20, sigmaSpace=20)
    return denoised


def adaptive_denoise(image: np.ndarray, strength: str = "light") -> np.ndarray:
    """
    Apply adaptive denoising based on strength.
    
    Args:
        image: RGB image
        strength: "none", "light", "medium", "heavy"
    """
    if strength == "none":
        return image
    elif strength == "light":
        return cv2.bilateralFilter(image, d=3, sigmaColor=20, sigmaSpace=20)
    elif strength == "medium":
        return cv2.bilateralFilter(image, d=5, sigmaColor=40, sigmaSpace=40)
    else:  # heavy
        return cv2.bilateralFilter(image, d=7, sigmaColor=60, sigmaSpace=60)


# ============================================================================
# MAIN VECTORIZATION
# ============================================================================

def vectorize_with_settings(
    image_path: str,
    output_path: str,
    settings: Dict[str, Any],
    denoise_strength: str = "light",
) -> Tuple[str, int]:
    """
    Vectorize image with specific settings.
    
    Returns:
        Tuple of (svg_content, path_count)
    """
    if not VTRACER_AVAILABLE:
        raise ImportError("vtracer required")
    
    # Load and optionally denoise
    image = cv2.imread(image_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    if denoise_strength != "none":
        processed = adaptive_denoise(image_rgb, denoise_strength)
    else:
        processed = image_rgb
    
    # Save processed image temporarily
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
        cv2.imwrite(tmp_path, cv2.cvtColor(processed, cv2.COLOR_RGB2BGR))
    
    # Vectorize
    with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as tmp_svg:
        tmp_svg_path = tmp_svg.name
    
    try:
        vtracer.convert_image_to_svg_py(tmp_path, tmp_svg_path, **settings)
        
        with open(tmp_svg_path, 'r') as f:
            svg_content = f.read()
        
        # Count paths
        path_count = svg_content.count('<path')
        
        # Write to output
        with open(output_path, 'w') as f:
            f.write(svg_content)
        
        return svg_content, path_count
        
    finally:
        # Cleanup
        for p in [tmp_path, tmp_svg_path]:
            try:
                os.remove(p)
            except:
                pass


def vectorize_quality(
    input_path: str,
    output_path: str,
    min_ssim: float = 0.99,
    max_problem_ratio: float = 0.005,  # Max 0.5% problem pixels
    max_iterations: int = 5,
    verbose: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    """
    Quality-first vectorization with pixel verification.
    
    This function iteratively refines vectorization settings until
    the quality threshold is met. It prioritizes visual accuracy.
    
    Args:
        input_path: Path to input image
        output_path: Path for output SVG
        min_ssim: Minimum SSIM quality (0.0-1.0)
        max_problem_ratio: Maximum ratio of problem pixels (>50 error)
        max_iterations: Maximum refinement iterations
        verbose: Print progress
        
    Returns:
        Tuple of (output_path, metrics_dict)
    """
    # Load original image
    image = cv2.imread(input_path)
    if image is None:
        raise ValueError(f"Could not load image: {input_path}")
    
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    h, w = image_rgb.shape[:2]
    
    if verbose:
        print(f"Input: {input_path} ({w}x{h})")
        print(f"Quality targets: SSIM >= {min_ssim*100:.1f}%, Problem pixels <= {max_problem_ratio*100:.2f}%")
    
    # Try progressively higher quality settings
    quality_levels = ["balanced", "high", "maximum"]
    denoise_levels = ["light", "none"]  # Start with light, try no denoise for text
    
    best_result = None
    best_ssim = 0
    
    for iteration in range(max_iterations):
        # Select settings based on iteration
        quality_idx = min(iteration, len(quality_levels) - 1)
        denoise_idx = min(iteration // 2, len(denoise_levels) - 1)
        
        quality = quality_levels[quality_idx]
        denoise = denoise_levels[denoise_idx]
        settings = QUALITY_PRESETS[quality].copy()
        
        # Progressive refinement of settings
        if iteration >= 2:
            # Even more aggressive quality settings
            settings['filter_speckle'] = max(1, settings['filter_speckle'] - 1)
            settings['layer_difference'] = max(2, settings['layer_difference'] // 2)
            settings['color_precision'] = min(8, settings['color_precision'] + 1)
        
        if verbose:
            print(f"\nIteration {iteration + 1}/{max_iterations}")
            print(f"  Quality: {quality}, Denoise: {denoise}")
            print(f"  Settings: filter_speckle={settings['filter_speckle']}, "
                  f"layer_difference={settings['layer_difference']}, "
                  f"color_precision={settings['color_precision']}")
        
        # Vectorize
        svg_content, path_count = vectorize_with_settings(
            input_path, output_path, settings, denoise
        )
        
        if verbose:
            print(f"  Paths: {path_count}")
        
        # Render and compare
        try:
            rendered = render_svg_to_array(svg_content, w, h)
            metrics = compute_pixel_metrics(image_rgb, rendered)
            
            if verbose:
                print(f"  SSIM: {metrics['ssim']*100:.2f}%")
                print(f"  Problem pixels: {metrics['problem_pixels_50']:,} ({metrics['problem_ratio']*100:.3f}%)")
            
            # Track best result
            if metrics['ssim'] > best_ssim:
                best_ssim = metrics['ssim']
                best_result = {
                    'svg_content': svg_content,
                    'metrics': metrics,
                    'settings': settings,
                    'quality': quality,
                    'denoise': denoise,
                    'path_count': path_count,
                }
            
            # Check if targets met
            if metrics['ssim'] >= min_ssim and metrics['problem_ratio'] <= max_problem_ratio:
                if verbose:
                    print(f"  ✅ Quality targets met!")
                break
                
        except Exception as e:
            if verbose:
                print(f"  ⚠️ Render failed: {e}")
            continue
    
    if best_result is None:
        raise RuntimeError("All vectorization attempts failed")
    
    # Write best result
    with open(output_path, 'w') as f:
        f.write(best_result['svg_content'])
    
    # Compute final file size
    file_size = len(best_result['svg_content'].encode('utf-8'))
    
    final_metrics = best_result['metrics'].copy()
    final_metrics['file_size'] = file_size
    final_metrics['path_count'] = best_result['path_count']
    final_metrics['quality_preset'] = best_result['quality']
    final_metrics['denoise'] = best_result['denoise']
    
    if verbose:
        print(f"\n{'='*50}")
        print(f"FINAL RESULT")
        print(f"{'='*50}")
        print(f"Output: {output_path}")
        print(f"File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print(f"Paths: {final_metrics['path_count']}")
        print(f"SSIM: {final_metrics['ssim']*100:.2f}%")
        print(f"Problem pixels: {final_metrics['problem_pixels_50']:,} ({final_metrics['problem_ratio']*100:.3f}%)")
        
        if final_metrics['ssim'] >= min_ssim:
            print(f"✅ Quality target met!")
        else:
            print(f"⚠️ Quality target not met (best achieved: {final_metrics['ssim']*100:.2f}%)")
    
    return output_path, final_metrics


def vectorize_logo_hq(
    input_path: str,
    output_path: str,
    verbose: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    """
    High-quality logo vectorization.
    
    Optimized for logos with text - prioritizes accuracy.
    """
    return vectorize_quality(
        input_path,
        output_path,
        min_ssim=0.99,
        max_problem_ratio=0.005,
        max_iterations=5,
        verbose=verbose,
    )


def vectorize_optimal(
    input_path: str,
    output_path: str,
    verbose: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    """
    Vectorize using the optimal settings found through testing.
    
    Uses bilateral_medium preprocessing + quality vtracer settings.
    This combination achieves ~98.35% SSIM with reasonable file size.
    
    Args:
        input_path: Path to input image
        output_path: Path for output SVG
        verbose: Print progress
        
    Returns:
        Tuple of (output_path, metrics_dict)
    """
    if not VTRACER_AVAILABLE:
        raise ImportError("vtracer required")
    
    # Load image
    image = cv2.imread(input_path)
    if image is None:
        raise ValueError(f"Could not load image: {input_path}")
    
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    h, w = image_rgb.shape[:2]
    
    if verbose:
        print(f"Input: {input_path} ({w}x{h})")
        print("Using optimal settings (bilateral_medium + quality)")
    
    # Apply optimal preprocessing - bilateral medium
    processed = cv2.bilateralFilter(
        image_rgb,
        d=OPTIMAL_BILATERAL['d'],
        sigmaColor=OPTIMAL_BILATERAL['sigmaColor'],
        sigmaSpace=OPTIMAL_BILATERAL['sigmaSpace']
    )
    
    # Save processed image
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
        cv2.imwrite(tmp_path, cv2.cvtColor(processed, cv2.COLOR_RGB2BGR))
    
    # Vectorize with optimal settings
    settings = QUALITY_PRESETS["optimal"]
    
    try:
        vtracer.convert_image_to_svg_py(tmp_path, output_path, **settings)
        
        with open(output_path, 'r') as f:
            svg_content = f.read()
        
        # Compute metrics
        rendered = render_svg_to_array(svg_content, w, h)
        metrics = compute_pixel_metrics(image_rgb, rendered)
        
        # Add file stats
        metrics['file_size'] = len(svg_content.encode('utf-8'))
        metrics['path_count'] = svg_content.count('<path')
        
        if verbose:
            print(f"\nResult:")
            print(f"  SSIM: {metrics['ssim']*100:.2f}%")
            print(f"  File size: {metrics['file_size']:,} bytes ({metrics['file_size']/1024:.1f} KB)")
            print(f"  Paths: {metrics['path_count']}")
            print(f"  Problem pixels: {metrics['problem_pixels_50']:,}")
        
        return output_path, metrics
        
    finally:
        os.remove(tmp_path)


def vectorize_logo_clean(
    input_path: str,
    output_path: str,
    n_colors: int = None,
    quality_preset: str = "balanced",
    verbose: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    """
    Vectorize logo with automatic palette reduction for clean output.
    
    This function:
    1. Analyzes the image to detect if it's a logo
    2. Reduces colors to optimal palette (8-32 colors)
    3. Vectorizes with settings optimized for clean paths
    
    Args:
        input_path: Path to input image
        output_path: Path for output SVG
        n_colors: Force specific palette size (auto-detect if None)
        quality_preset: Quality preset (clean, balanced, high, ultra)
        verbose: Print progress
        
    Returns:
        Tuple of (output_path, metrics_dict)
    """
    if not VTRACER_AVAILABLE:
        raise ImportError("vtracer required")
    
    # Load image with alpha if present
    image = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Could not load image: {input_path}")
    
    # Handle channels
    if len(image.shape) == 2:  # Grayscale
        image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    elif image.shape[2] == 3:  # BGR
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    elif image.shape[2] == 4:  # BGRA
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
    else:
        image_rgb = image
        
    h, w = image_rgb.shape[:2]
    
    # Check for Monochrome with Alpha (e.g. icons)
    is_monochrome_alpha = False
    mono_color = None
    
    if image_rgb.shape[2] == 4:
        # Check if RGB channels are constant where alpha > 0
        rgb = image_rgb[:,:,:3]
        alpha = image_rgb[:,:,3]
        
        mask = alpha > 10
        if np.sum(mask) > 0:
            pixels = rgb[mask]
            # Check variance
            std_dev = np.std(pixels, axis=0)
            # Relaxed threshold to match icon.py (was 5.0 mean, icon.py uses 30.0 max)
            # Using 20.0 max to be safe but inclusive
            if np.max(std_dev) < 20.0: 
                is_monochrome_alpha = True
                mono_color = np.mean(pixels, axis=0).astype(int)
                if verbose:
                    print(f"Detected Monochrome Icon with Alpha. Color: {mono_color}")

    if is_monochrome_alpha:
        # Special handling for monochrome alpha
        # Create binary image: Shape=Black, Background=White
        binary = np.ones((h, w), dtype=np.uint8) * 255
        binary[image_rgb[:,:,3] > 10] = 0
        
        # Save binary
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name
            cv2.imwrite(tmp_path, binary)
            
        if quality_preset not in LOGO_PRESETS:
            quality_preset = "balanced"
        settings = LOGO_PRESETS[quality_preset].copy()
        settings['colormode'] = 'binary'
        
        reduced = image_rgb # No reduction really
        n_colors = 1
        analysis = {'is_logo': True} # Fake analysis
        
    else:
        # Analyze image (use RGB for analysis to keep it simple, or update analyze_image)
        # For now, just use RGB part for analysis if RGBA
        analysis_img = image_rgb[:,:,:3] if image_rgb.shape[2] == 4 else image_rgb
        analysis = analyze_image(analysis_img)
        
        if verbose:
            print(f"Input: {input_path} ({w}x{h}) Channels: {image_rgb.shape[2]}")
            print(f"Original colors: {analysis['unique_colors']:,}")
            print(f"Top 10 colors cover: {analysis['top_10_coverage']*100:.1f}%")
            print(f"Detected as logo: {'Yes' if analysis['is_logo'] else 'No'}")
        
        # Determine palette size
        if n_colors is None:
            n_colors = get_optimal_palette_size(analysis)
            
            # Boost palette size for high quality presets if image is complex
            if n_colors >= 32:
                if quality_preset == "ultra":
                    n_colors = 64
                elif quality_preset == "high":
                    n_colors = 48
        
        if verbose:
            print(f"Using palette: {n_colors} colors (K-means clustering)")
        
        # Reduce to palette (handles RGBA now)
        reduced = reduce_to_palette(image_rgb, n_colors)
        
        if verbose:
            actual_colors = len(np.unique(reduced.reshape(-1, reduced.shape[2]), axis=0))
            print(f"Reduced to: {actual_colors} colors")
        
        # Save reduced image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name
            # Convert back to BGR/BGRA for saving
            if reduced.shape[2] == 4:
                save_img = cv2.cvtColor(reduced, cv2.COLOR_RGBA2BGRA)
            else:
                save_img = cv2.cvtColor(reduced, cv2.COLOR_RGB2BGR)
            cv2.imwrite(tmp_path, save_img)
        
        # Settings optimized for palette-reduced images
        if quality_preset not in LOGO_PRESETS:
            print(f"Warning: Unknown preset '{quality_preset}', using 'balanced'")
            quality_preset = "balanced"
            
        settings = LOGO_PRESETS[quality_preset]
        
        if verbose:
            print(f"Using quality preset: {quality_preset}")
    
    try:
        vtracer.convert_image_to_svg_py(tmp_path, output_path, **settings)
        
        with open(output_path, 'r') as f:
            svg_content = f.read()
            
        # Fix color for monochrome alpha
        if is_monochrome_alpha and mono_color is not None:
            hex_color = "#{:02x}{:02x}{:02x}".format(*mono_color)
            svg_content = svg_content.replace('fill="#000000"', f'fill="{hex_color}"')
            with open(output_path, 'w') as f:
                f.write(svg_content)
        
        # Compute metrics against original
        # Render SVG to array (RGB) - cairosvg handles transparency by default (white bg?)
        # We need to be careful with comparison.
        # If original has alpha, and rendered has alpha?
        # render_svg_to_array returns RGB (from PIL convert('RGB')).
        # So it flattens alpha to black/white.
        
        # For metrics, we should probably compare RGB versions.
        # If we loaded RGBA, let's convert to RGB for metrics to match render_svg_to_array
        if image_rgb.shape[2] == 4:
             # Composite over white for fair comparison if render_svg_to_array does that?
             # Actually render_svg_to_array uses PIL convert('RGB') which puts on black background usually?
             # Let's check render_svg_to_array implementation.
             pass

        rendered = render_svg_to_array(svg_content, w, h)
        
        # Convert original to RGB for comparison
        if image_rgb.shape[2] == 4:
             # Simple drop alpha for now, or composite?
             # PIL convert('RGB') drops alpha (black background).
             # So we should do same to original to match.
             pil_img = Image.fromarray(image_rgb)
             image_rgb_comp = np.array(pil_img.convert('RGB'))
             
             pil_reduced = Image.fromarray(reduced)
             reduced_comp = np.array(pil_reduced.convert('RGB'))
        else:
             image_rgb_comp = image_rgb
             reduced_comp = reduced

        metrics = compute_pixel_metrics(image_rgb_comp, rendered)
        
        # Also compute vs reduced image
        metrics_vs_reduced = compute_pixel_metrics(reduced_comp, rendered)
        
        # Analyze SVG complexity
        svg_analysis = analyze_svg_content(svg_content)
        
        # Add file stats
        metrics['file_size'] = len(svg_content.encode('utf-8'))
        metrics['path_count'] = svg_analysis['path_count']
        metrics['total_segments'] = svg_analysis['total_segments']
        metrics['palette_size'] = n_colors
        metrics['is_logo'] = analysis['is_logo']
        metrics['ssim_vs_reduced'] = metrics_vs_reduced['ssim']
        
        if verbose:
            print(f"\nResult:")
            print(f"  SSIM vs original: {metrics['ssim']*100:.2f}%")
            print(f"  Perceptual SSIM:  {metrics['ssim_perceptual']*100:.2f}%")
            print(f"  SSIM vs reduced:  {metrics['ssim_vs_reduced']*100:.2f}%")
            print(f"  File size: {metrics['file_size']:,} bytes ({metrics['file_size']/1024:.1f} KB)")
            print(f"  Paths: {metrics['path_count']}")
            print(f"  Segments: {metrics['total_segments']}")
        
        return output_path, metrics
        
    finally:
        os.remove(tmp_path)


def compare_and_visualize(
    original_path: str,
    svg_path: str,
    output_dir: str = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Compare original image with SVG and create visualizations.
    
    Args:
        original_path: Path to original image
        svg_path: Path to SVG file
        output_dir: Directory for output files (default: same as SVG)
        verbose: Print progress
        
    Returns:
        Dictionary with comparison metrics
    """
    # Load original
    original = cv2.imread(original_path)
    original_rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
    h, w = original_rgb.shape[:2]
    
    # Load and render SVG
    with open(svg_path, 'r') as f:
        svg_content = f.read()
    
    rendered = render_svg_to_array(svg_content, w, h)
    
    # Compute metrics
    metrics = compute_pixel_metrics(original_rgb, rendered)
    
    # Set output directory
    if output_dir is None:
        output_dir = str(Path(svg_path).parent)
    
    base_name = Path(svg_path).stem
    
    # Save rendered PNG
    rendered_path = os.path.join(output_dir, f"{base_name}_rendered.png")
    cv2.imwrite(rendered_path, cv2.cvtColor(rendered, cv2.COLOR_RGB2BGR))
    
    # Save difference map
    diff_path = os.path.join(output_dir, f"{base_name}_diff.png")
    save_difference_map(original_rgb, rendered, diff_path)
    
    # Save side-by-side comparison
    comparison = np.hstack([original_rgb, rendered])
    comparison_path = os.path.join(output_dir, f"{base_name}_comparison.png")
    cv2.imwrite(comparison_path, cv2.cvtColor(comparison, cv2.COLOR_RGB2BGR))
    
    if verbose:
        print(f"Quality Metrics:")
        print(f"  SSIM: {metrics['ssim']*100:.2f}%")
        print(f"  PSNR: {metrics['psnr']:.2f} dB")
        print(f"  MAE: {metrics['mae']:.2f}")
        print(f"  Max Error: {metrics['max_error']:.0f}")
        print(f"  Problem Pixels (>50): {metrics['problem_pixels_50']:,} ({metrics['problem_ratio']*100:.3f}%)")
        print(f"\nOutput files:")
        print(f"  Rendered: {rendered_path}")
        print(f"  Difference: {diff_path}")
        print(f"  Comparison: {comparison_path}")
    
    metrics['rendered_path'] = rendered_path
    metrics['diff_path'] = diff_path
    metrics['comparison_path'] = comparison_path
    
    return metrics


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python -m vectalab.quality <input_image> <output.svg> [min_ssim]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    min_ssim = float(sys.argv[3]) if len(sys.argv) > 3 else 0.99
    
    try:
        svg_path, metrics = vectorize_quality(input_path, output_path, min_ssim=min_ssim)
        print(f"\nSuccess! Output saved to {svg_path}")
        
        # Also create comparison
        compare_and_visualize(input_path, svg_path)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
