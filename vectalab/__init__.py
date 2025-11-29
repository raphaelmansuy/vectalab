"""
Vectalab - Professional High-Fidelity Image Vectorization

Vectalab converts raster images (PNG, JPG) to scalable vector graphics (SVG)
with optimized output for design tools like Figma and Illustrator.

Website: https://vectalab.com
"""

from .core import Vectalab
from .bayesian import optimize_vectorization, BayesianVectorRenderer
from .hifi import (
    vectorize_high_fidelity, 
    vectorize_for_figma,
    vectorize_with_quality,
    render_svg_to_png,
    compute_quality_metrics,
    list_presets,
)
from .optimize import (
    SVGOptimizer,
    create_figma_optimizer,
    create_quality_optimizer,
    optimize_svg_file,
    optimize_svg_string,
    get_vtracer_preset,
    VTRACER_PRESETS,
)

__version__ = "0.2.0"
__author__ = "Vectalab Contributors"

__all__ = [
    # Core
    'Vectalab', 
    'optimize_vectorization', 
    'BayesianVectorRenderer',
    # High-fidelity vectorization
    'vectorize_high_fidelity',
    'vectorize_for_figma',
    'vectorize_with_quality',
    'render_svg_to_png',
    'compute_quality_metrics',
    'list_presets',
    # Optimization
    'SVGOptimizer',
    'create_figma_optimizer',
    'create_quality_optimizer',
    'optimize_svg_file',
    'optimize_svg_string',
    'get_vtracer_preset',
    'VTRACER_PRESETS',
]
