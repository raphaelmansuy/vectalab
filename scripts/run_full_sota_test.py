#!/usr/bin/env python3
"""
Full test suite execution using SAM method with Modal cloud offloading.
"""

import sys
import os
import modal
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from vectalab.core import Vectalab

def vectorize_icon(input_png, output_svg, vl):
    """Vectorize using the provided Vectalab instance."""
    try:
        input_path = str(Path(input_png).absolute())
        output_path = str(Path(output_svg).absolute())
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Vectorize
        vl.vectorize(input_path, output_path)
        
        print(f"✓ {Path(input_png).name}")
        return True
    except Exception as e:
        print(f"✗ {Path(input_png).name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # Enable Modal logs
    # modal.enable_output() # Optional: enable if debugging is needed
    
    # Subset for rapid iteration
    test_set_mono = ['circle.png', 'star.png', 'camera.png']
    test_set_multi = ['google.png', 'github.png', 'apple.png']
    
    print("Initializing Vectalab with SOTA (HiFi) method...")
    try:
        # Initialize Vectalab with SOTA method
        vl = Vectalab(
            method="sota", # Changed from "bayesian" to "sota" to use VTracer
            model_type="vit_h",
            device="cpu",
            use_modal=False # SOTA method runs locally
        )
    except Exception as e:
        print(f"Failed to initialize Vectalab: {e}")
        return
        print(f"Failed to initialize Vectalab: {e}")
        return

    print("\n=== Monochrome Icons ===")
    for filename in test_set_mono:
        png_path = f"test_data/png_mono/{filename}"
        svg_path = f"test_data/vectalab_mono/{filename.replace('.png', '.svg')}"
        if os.path.exists(png_path):
            vectorize_icon(png_path, svg_path, vl)
        else:
            print(f"⚠ Missing: {png_path}")
    
    print("\n=== Multi-Color Icons ===")
    for filename in test_set_multi:
        png_path = f"test_data/png_multi/{filename}"
        svg_path = f"test_data/vectalab_multi/{filename.replace('.png', '.svg')}"
        if os.path.exists(png_path):
            vectorize_icon(png_path, svg_path, vl)
        else:
            print(f"⚠ Missing: {png_path}")
    
    print("\n✓ Test suite complete!")

if __name__ == "__main__":
    main()
