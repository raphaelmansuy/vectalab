"""
Vectalab Auto Mode Logic.

This module centralizes the decision logic for the 'auto' vectorization mode.
It is used by both the CLI and the Benchmark tool to ensure consistent behavior.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

# Import dependencies
try:
    from vectalab.quality import analyze_image
    from vectalab.icon import is_monochrome_icon
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False

def determine_auto_mode(
    input_path: str, 
    set_name: Optional[str] = None
) -> Tuple[str, str, Optional[Tuple[int, int, int]]]:
    """
    Determine the best vectorization mode and quality settings for an image.
    
    Args:
        input_path: Path to the input image.
        set_name: Optional name of the dataset (e.g., 'complex', 'mono') for fallback hints.
        
    Returns:
        Tuple containing:
        - effective_mode: The selected mode ('geometric_icon', 'logo', 'premium').
        - effective_quality: The selected quality preset (e.g., 'ultra', 'clean').
        - mono_color: The detected color for geometric icons (or None).
    """
    if not DEPENDENCIES_AVAILABLE:
        # Fallback if dependencies missing
        return "premium", "ultra", None

    effective_mode = "premium"
    effective_quality = "ultra"
    mono_color = None
    
    try:
        # 1. Check for Monochrome Icon first (Geometric shapes)
        is_mono, m_color = is_monochrome_icon(input_path)
        if is_mono:
            # Use logo mode which now handles monochrome icons with binary tracing
            return "logo", "ultra", m_color
            
        # 2. Analyze image content
        img = cv2.imread(str(input_path))
        if img is not None:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            analysis = analyze_image(img_rgb)
            
            if analysis['is_logo']:
                # Heuristic: High color count (> 1000) usually means complex illustration/gradients
                # even if top-10 coverage is high (e.g. cartoons). Use Premium for these.
                if analysis['unique_colors'] > 1000:
                    effective_mode = "premium"
                else:
                    effective_mode = "logo"
                    # Heuristic: Very simple logos (high top-10 coverage) benefit from 'clean'
                    # Complex logos benefit from 'ultra'
                    if analysis['top_10_coverage'] > 0.90:
                        effective_quality = "clean"
                    else:
                        effective_quality = "ultra"
            else:
                effective_mode = "premium"
        else:
            # Fallback if image load fails
            if set_name == "complex":
                effective_mode = "premium"
            else:
                effective_mode = "logo"
                
    except Exception:
        # Fallback on error
        if set_name == "complex":
            effective_mode = "premium"
        else:
            effective_mode = "logo"
            
    return effective_mode, effective_quality, mono_color
