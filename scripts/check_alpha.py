import cv2
import sys

img = cv2.imread('test_data/png_multi/bitbucket.png', cv2.IMREAD_UNCHANGED)
if img.shape[2] == 4:
    print("Has alpha channel")
    # Check if alpha is used
    print(f"Min alpha: {img[:,:,3].min()}")
    print(f"Max alpha: {img[:,:,3].max()}")
else:
    print("No alpha channel")
