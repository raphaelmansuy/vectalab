import cv2
from vectalab.quality import analyze_image

img_path = "test_data/cache_golden/illustrations/cartman.png"
img = cv2.imread(img_path)
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
analysis = analyze_image(img_rgb)

print(f"Analysis for {img_path}:")
for k, v in analysis.items():
    print(f"{k}: {v}")
