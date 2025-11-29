"""
Vectalab - Professional High-Fidelity Image Vectorization

Vectalab converts raster images (PNG, JPG) to scalable vector graphics (SVG)
with 99.8%+ structural similarity using Bayesian optimization.

Website: https://vectalab.com
"""

from .core import Vectalab
from .bayesian import optimize_vectorization, BayesianVectorRenderer
from .hifi import vectorize_high_fidelity, render_svg_to_png

__version__ = "0.1.0"
__author__ = "Vectalab Contributors"

__all__ = [
    'Vectalab', 
    'optimize_vectorization', 
    'BayesianVectorRenderer',
    'vectorize_high_fidelity',
    'render_svg_to_png'
]
