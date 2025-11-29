#!/usr/bin/env python3
"""
Test suite for Vectalab high-fidelity vectorization.
Verifies PNG -> SVG -> PNG achieves 99.8%+ SSIM.
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
from skimage.metrics import structural_similarity as ssim, peak_signal_noise_ratio as psnr

from vectalab.hifi import vectorize_high_fidelity, render_svg_to_png


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
    
    def test_vectorize_achieves_target_ssim(self, test_image_path, temp_output_dir):
        """Test that vectorization achieves 99.8%+ SSIM."""
        svg_path = os.path.join(temp_output_dir, "output.svg")
        png_path = os.path.join(temp_output_dir, "output.png")
        
        # Load original
        original = cv2.imread(test_image_path)
        original_rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
        h, w = original_rgb.shape[:2]
        
        # Vectorize
        _, achieved_ssim = vectorize_high_fidelity(
            test_image_path,
            svg_path,
            target_ssim=0.998,
            quality="ultra",
            verbose=False
        )
        
        # Render back
        render_svg_to_png(svg_path, png_path)
        
        # Compare
        rendered = cv2.imread(png_path)
        rendered_rgb = cv2.cvtColor(rendered, cv2.COLOR_BGR2RGB)
        
        if rendered_rgb.shape[:2] != original_rgb.shape[:2]:
            rendered_rgb = cv2.resize(rendered_rgb, (w, h))
        
        final_ssim = ssim(original_rgb, rendered_rgb, channel_axis=2, data_range=255)
        
        assert final_ssim >= 0.998, f"SSIM {final_ssim:.4f} below target 0.998"
    
    def test_svg_output_is_valid(self, test_image_path, temp_output_dir):
        """Test that output SVG is valid XML."""
        import xml.etree.ElementTree as ET
        
        svg_path = os.path.join(temp_output_dir, "output.svg")
        
        vectorize_high_fidelity(
            test_image_path,
            svg_path,
            quality="fast",
            verbose=False
        )
        
        # Should parse without error
        tree = ET.parse(svg_path)
        root = tree.getroot()
        
        assert 'svg' in root.tag.lower()
    
    def test_quality_presets(self, test_image_path, temp_output_dir):
        """Test different quality presets."""
        for quality in ["fast", "balanced", "ultra"]:
            svg_path = os.path.join(temp_output_dir, f"output_{quality}.svg")
            
            _, ssim_val = vectorize_high_fidelity(
                test_image_path,
                svg_path,
                quality=quality,
                target_ssim=0.95,
                max_iterations=1,
                verbose=False
            )
            
            assert ssim_val >= 0.95, f"Quality '{quality}' achieved only {ssim_val:.4f}"


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
        png_path = os.path.join(tmpdir, "output.png")
        
        original = cv2.imread(test_image)
        original_rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
        h, w = original_rgb.shape[:2]
        
        print(f"\nInput: {test_image}")
        print(f"Size: {w}x{h}")
        
        print("\nRunning high-fidelity vectorization...")
        _, achieved_ssim = vectorize_high_fidelity(
            test_image, svg_path,
            target_ssim=0.998, quality="ultra", verbose=True
        )
        
        print("\nRendering SVG to PNG...")
        render_svg_to_png(svg_path, png_path)
        
        rendered = cv2.imread(png_path)
        rendered_rgb = cv2.cvtColor(rendered, cv2.COLOR_BGR2RGB)
        if rendered_rgb.shape[:2] != original_rgb.shape[:2]:
            rendered_rgb = cv2.resize(rendered_rgb, (w, h))
        
        final_ssim = ssim(original_rgb, rendered_rgb, channel_axis=2, data_range=255)
        final_psnr = psnr(original_rgb, rendered_rgb, data_range=255)
        
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)
        print(f"SSIM: {final_ssim:.4f} ({final_ssim*100:.2f}%)")
        print(f"PSNR: {final_psnr:.2f} dB")
        
        if final_ssim >= 0.998:
            print("\n✅ SUCCESS! Target SSIM (99.8%) achieved!")
            return 0
        else:
            print(f"\n⚠️ Gap to target: {(0.998 - final_ssim)*100:.3f}%")
            return 1


if __name__ == "__main__":
    sys.exit(main())
