import cv2
from vectalab.quality import analyze_image
import sys

files = [
    "test_data/cache_golden/icons/alert-octagon.png",
    "test_data/cache_golden/logos/adobe-after-effects.png",
    "test_data/cache_golden/logos/android.png"
]

for f in files:
    try:
        img = cv2.imread(f)
        if img is None:
            print(f"Failed to load {f}")
            continue
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        analysis = analyze_image(img_rgb)
        print(f"\nAnalysis for {f}:")
        print(f"  unique_colors: {analysis['unique_colors']}")
        print(f"  top_10_coverage: {analysis['top_10_coverage']:.4f}")
        print(f"  is_logo: {analysis['is_logo']}")
    except Exception as e:
        print(f"Error analyzing {f}: {e}")
