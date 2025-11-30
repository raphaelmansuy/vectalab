import cv2
import numpy as np
import sys

def visualize_components(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"Could not load {path}")
        return

    if len(img.shape) == 2:
        gray = img
    elif img.shape[2] == 4:
        # Use alpha channel as mask if present?
        # Or convert to gray
        gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Threshold
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    
    # Components
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(binary)
    
    print(f"Found {n} components (including background)")
    
    # Create visualization
    vis = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    
    for i in range(1, n): # Skip background
        color = np.random.randint(0, 255, size=3).tolist()
        vis[labels == i] = color
        
        x, y, w, h, area = stats[i]
        print(f"Component {i}: Area={area}, Pos=({x},{y}), Size=({w}x{h})")
        
    cv2.imwrite('test_data/components_vis.png', vis)
    print("Saved visualization to test_data/components_vis.png")

if __name__ == "__main__":
    visualize_components('test_data/png_multi/bitbucket.png')
