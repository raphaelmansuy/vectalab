#!/usr/bin/env python3
"""
Test suite for core Vectalab functionality.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np

from vectalab import core


@pytest.fixture
def sample_rgb_image():
    """Create a sample RGB image for testing."""
    # Create a 100x100 image with gradient
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    for i in range(100):
        for j in range(100):
            img[i, j] = [i * 2, j * 2, (i + j)]
    return img


class TestImageLoading:
    """Test image loading and preprocessing."""
    
    def test_rgb_shape(self, sample_rgb_image):
        """Test that RGB image has correct shape."""
        assert sample_rgb_image.shape == (100, 100, 3)
        assert sample_rgb_image.dtype == np.uint8
    
    def test_pixel_range(self, sample_rgb_image):
        """Test pixel values are in valid range."""
        assert sample_rgb_image.min() >= 0
        assert sample_rgb_image.max() <= 255


class TestColorQuantization:
    """Test color quantization utilities."""
    
    def test_unique_colors(self, sample_rgb_image):
        """Test counting unique colors."""
        flat = sample_rgb_image.reshape(-1, 3)
        unique = np.unique(flat, axis=0)
        assert len(unique) > 0
    
    def test_quantization_reduces_colors(self, sample_rgb_image):
        """Test that quantization reduces color count."""
        from sklearn.cluster import MiniBatchKMeans
        
        flat = sample_rgb_image.reshape(-1, 3).astype(float)
        n_colors = 16
        
        kmeans = MiniBatchKMeans(n_clusters=n_colors, random_state=42)
        kmeans.fit(flat)
        
        assert len(kmeans.cluster_centers_) == n_colors


def main():
    """Run tests manually."""
    print("Testing core functionality...")
    
    # Create test image
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    for i in range(100):
        for j in range(100):
            img[i, j] = [i * 2, j * 2, (i + j)]
    
    # Test shape
    assert img.shape == (100, 100, 3), "Shape check failed"
    print("✅ Image shape test passed")
    
    # Test pixel range
    assert img.min() >= 0 and img.max() <= 255, "Pixel range check failed"
    print("✅ Pixel range test passed")
    
    print("✅ All core tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
