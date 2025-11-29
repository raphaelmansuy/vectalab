import numpy as np
import potrace
import cv2

class Tracer:
    def __init__(self, turdsize=2, alphamax=1, opticurve=True, **kwargs):
        self.turdsize = turdsize
        self.alphamax = alphamax
        self.opticurve = opticurve

    def trace(self, image, masks):
        """
        Converts masks to vector paths.
        Returns a list of dicts: {'path': <potrace path>, 'color': (r, g, b)}
        """
        paths = []
        # Sort masks by area, largest first, so smaller details are drawn on top?
        # Actually, in SVG, later elements are drawn on top.
        # So we should draw largest first (background) and then smaller details.
        sorted_masks = sorted(masks, key=lambda x: x['area'], reverse=True)

        for mask_data in sorted_masks:
            mask = mask_data['segmentation']
            
            # Convert boolean mask to uint8 for potrace (0 and 1)
            # Potrace expects a 2D array where non-zero is foreground.
            # However, potracer might expect a specific format.
            # Usually it takes a numpy array.
            
            # Convert mask to inverted boolean for potrace
            # Potrace (via potracer) treats False as Black (foreground) and True as White (background).
            # We want to trace the 'True' regions of the mask, so we invert it to 'False'.
            bitmap_data = ~mask.astype(bool)
            
            # Trace
            bmp = potrace.Bitmap(bitmap_data)
            path = bmp.trace(
                turdsize=self.turdsize,
                alphamax=self.alphamax,
                opticurve=self.opticurve
            )

            
            # Get average color of the segment
            color = self._get_average_color(image, mask)
            
            paths.append({
                'path': path,
                'color': color
            })
            
        return paths

    def _get_average_color(self, image, mask):
        # image is RGB
        # mask is boolean
        masked_pixels = image[mask]
        if masked_pixels.size == 0:
            return (0, 0, 0)
        avg_color = np.mean(masked_pixels, axis=0)
        return tuple(map(int, avg_color))
