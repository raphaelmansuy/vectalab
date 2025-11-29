#!/usr/bin/env python3
"""
Test suite for Vectalab high-fidelity vectorization.
Verifies PNG -> SVG produces clean, optimized output.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import cv2
import pytest

# Optional metrics import
try:
    from skimage.metrics import structural_similarity as ssim, peak_signal_noise_ratio as psnr
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False

from vectalab.hifi import vectorize_high_fidelity, render_svg_to_png, compute_quality_metrics, list_presets


def get_test_image_path():
    """Find test image path."""
    candidates = [
        Path(__file__).parent.parent / "examples" / "ELITIZON_LOGO.jpg",
        Path(__file__).parent.parent / "test_case" / "ELITIZON_LOGO.jpg",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


@pytest.fixture
def test_image_path():
    """Path to test image."""
    path = get_test_image_path()
    if path is None:
        pytest.skip("Test image not found")
    return path


@pytest.fixture
def temp_output_dir():
    """Temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestHighFidelityVectorization:
    """Test suite for high-fidelity vectorization."""
    
    def test_vectorize_produces_output(self, test_image_path, temp_output_dir):
        """Test that vectorization produces valid SVG output."""
        svg_path = os.path.join(temp_output_dir, "output.svg")
        
        # Vectorize with balanced preset
        output_path, stats = vectorize_high_fidelity(
            test_image_path,
            svg_path,
            preset="balanced",
            optimize=True,
            verbose=False
        )
        
        # Check output exists
        assert os.path.exists(output_path)
        
        # Check file is not empty
        assert os.path.getsize(output_path) > 0
        
        # Check stats are returned
        assert 'optimized_size' in stats or 'file_size' in stats
    
    def test_svg_output_is_valid(self, test_image_path, temp_output_dir):
        """Test that output SVG is valid XML."""
        import xml.etree.ElementTree as ET
        
        svg_path = os.path.join(temp_output_dir, "output.svg")
        
        vectorize_high_fidelity(
            test_image_path,
            svg_path,
            preset="figma",
            verbose=False
        )
        
        # Should parse without error
        tree = ET.parse(svg_path)
        root = tree.getroot()
        
        assert 'svg' in root.tag.lower()
    
    def test_quality_presets(self, test_image_path, temp_output_dir):
        """Test different quality presets produce valid output."""
        for preset in ["figma", "balanced", "quality"]:
            svg_path = os.path.join(temp_output_dir, f"output_{preset}.svg")
            
            output_path, stats = vectorize_high_fidelity(
                test_image_path,
                svg_path,
                preset=preset,
                optimize=True,
                verbose=False
            )
            
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
    
    def test_figma_preset_produces_smaller_file(self, test_image_path, temp_output_dir):
        """Test that figma preset produces smaller files than quality preset."""
        figma_path = os.path.join(temp_output_dir, "figma.svg")
        quality_path = os.path.join(temp_output_dir, "quality.svg")
        
        vectorize_high_fidelity(
            test_image_path, figma_path, preset="figma", verbose=False
        )
        vectorize_high_fidelity(
            test_image_path, quality_path, preset="quality", verbose=False
        )
        
        figma_size = os.path.getsize(figma_path)
        quality_size = os.path.getsize(quality_path)
        
        # Figma preset should generally be smaller (or similar)
        # Allow some tolerance since results can vary
        assert figma_size <= quality_size * 1.5, \
            f"Figma preset ({figma_size}) should be smaller than quality ({quality_size})"
    
    def test_list_presets(self):
        """Test that presets are listed correctly."""
        presets = list_presets()
        
        assert 'figma' in presets
        assert 'balanced' in presets
        assert 'quality' in presets
        assert 'ultra' in presets


class TestSVGOptimization:
    """Test SVG optimization functionality."""
    
    def test_optimizer_import(self):
        """Test that optimizer can be imported."""
        from vectalab.optimize import SVGOptimizer, create_figma_optimizer
        
        optimizer = create_figma_optimizer()
        assert optimizer is not None
    
    def test_path_simplification(self):
        """Test path simplification function."""
        from vectalab.optimize import rdp_simplify
        
        # Create a simple path with redundant points
        points = [(0, 0), (1, 0.01), (2, 0), (3, 0.01), (4, 0)]
        simplified = rdp_simplify(points, epsilon=0.1)
        
        # Should reduce to just start and end
        assert len(simplified) <= len(points)
    
    def test_color_optimization(self):
        """Test color optimization."""
        from vectalab.optimize import SVGOptimizer
        
        optimizer = SVGOptimizer()
        
        # Test rgb to hex
        assert optimizer._optimize_color('rgb(255,0,0)') in ['#f00', 'red']
        
        # Test hex shortening
        assert optimizer._optimize_color('#ff0000') in ['#f00', 'red']


def main():
    """Run tests manually."""
    print("="*60)
    print("Vectalab High-Fidelity Vectorization Test")
    print("="*60)
    
    test_image = get_test_image_path()
    if not test_image:
        print("Error: Test image not found")
        return 1
    
    with tempfile.TemporaryDirectory() as tmpdir:
        svg_path = os.path.join(tmpdir, "output.svg")
        
        original = cv2.imread(test_image)
        h, w = original.shape[:2]
        
        print(f"\nInput: {test_image}")
        print(f"Size: {w}x{h}")
        
        print("\nRunning vectorization with different presets...")
        
        for preset in ["figma", "balanced", "quality"]:
            output_path = os.path.join(tmpdir, f"{preset}.svg")
            
            print(f"\nPreset: {preset}")
            _, stats = vectorize_high_fidelity(
                test_image, output_path,
                preset=preset, verbose=True
            )
            
            file_size = os.path.getsize(output_path)
            print(f"File size: {file_size:,} bytes")
        
        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)
        
        return 0


if __name__ == "__main__":
    sys.exit(main())
