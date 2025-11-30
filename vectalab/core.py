"""
Vectalab Core - Professional High-Fidelity Image Vectorization

This module contains the main Vectalab class for image vectorization.
"""

import os
import cv2
import numpy as np
from pathlib import Path
from .segmentation import SAMSegmenter
from .tracing import Tracer
from .output import SVGWriter


class Vectalab:
    def __init__(self, model_type="vit_h", checkpoint_path=None, device="cpu", method="sam", use_modal=False, **kwargs):
        self.method = method
        self.device = device
        # Separate arguments
        tracing_keys = ['turdsize', 'alphamax', 'opticurve']
        tracing_args = {k: v for k, v in kwargs.items() if k in tracing_keys}
        segmentation_args = {k: v for k, v in kwargs.items() if k not in tracing_keys}
        
        self.segmenter = SAMSegmenter(model_type, checkpoint_path, device, use_modal=use_modal, **segmentation_args)
        self.tracer = Tracer(turdsize=0, alphamax=0, **tracing_args)
        self.writer = SVGWriter()

    def vectorize(self, image_path, output_path):
        """
        Main pipeline:
        1. Load Image
        2. Segment Image (SAM)
        3. Trace Segments (Potrace)
        4. Save to SVG
        """
        print(f"Processing {image_path}...")
        
        # 1. Load Image
        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")
            
        alpha_mask = None
        if image.ndim == 3 and image.shape[2] == 4:
            alpha_mask = image[:, :, 3]
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        elif image.ndim == 3 and image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        
        # Upsample for better fidelity (4x)
        orig_h, orig_w = image.shape[:2]
        scale_factor = 4.0
        new_size = (int(orig_w * scale_factor), int(orig_h * scale_factor))
        print(f"Upsampling image to {new_size} for higher fidelity...")
        image = cv2.resize(image, new_size, interpolation=cv2.INTER_LANCZOS4)

        # 2. Segment Image (Always run this first for initialization)
        print("Running segmentation...")
        masks = self.segmenter.segment(image)
        print(f"Found {len(masks)} segments.")
        
        # Filter masks based on alpha transparency
        if alpha_mask is not None:
            print("Filtering segments based on transparency...")
            # Resize alpha mask to match upsampled image
            alpha_mask_resized = cv2.resize(alpha_mask, new_size, interpolation=cv2.INTER_NEAREST)
            
            valid_masks = []
            for m in masks:
                # m['segmentation'] is boolean mask of the object
                object_mask = m['segmentation']
                object_area = np.sum(object_mask)
                
                if object_area == 0:
                    continue
                
                # Pixels that are in the object AND are transparent (alpha < 10)
                # We use a low threshold to be safe
                transparent_pixels = np.logical_and(object_mask, alpha_mask_resized < 10)
                transparent_area = np.sum(transparent_pixels)
                
                # If object is more than 50% transparent, skip it
                if transparent_area / object_area > 0.5:
                    continue
                    
                valid_masks.append(m)
            
            print(f"Filtered {len(masks) - len(valid_masks)} transparent segments.")
            masks = valid_masks

        # 3. Trace Segments (Always run this first)
        print("Tracing paths...")
        initial_paths = self.tracer.trace(image, masks)

        if self.method == "bayesian":
            print("Running Bayesian Vectorization (Hybrid)...")
            from .bayesian import BayesianVectorRenderer
            import torch
            import torch.optim as optim
            
            # Prepare initial paths for Bayesian renderer
            bayesian_init_paths = []
            for item in initial_paths:
                path_obj = item['path']
                color = item['color']
                
                # Extract points from potrace path
                points = []
                for curve in path_obj:
                    points.append([curve.start_point.x, curve.start_point.y])
                    for segment in curve:
                        points.append([segment.end_point.x, segment.end_point.y])
                
                if len(points) > 2:
                    bayesian_init_paths.append({
                        'points': points,
                        'color': color
                    })
            
            print(f"Initializing Bayesian renderer with {len(bayesian_init_paths)} paths...")

            # Use higher resolution for better fidelity
            # Limit to 1024x1024 for high fidelity
            target_size = (1024, 1024)
            h, w, _ = image.shape
            scale = min(target_size[0]/w, target_size[1]/h)
            # If image is smaller than target, use original size
            if scale > 1.0:
                scale = 1.0
            
            new_w, new_h = int(w*scale), int(h*scale)
            img_small = cv2.resize(image, (new_w, new_h))
            
            # Scale initial points to new resolution
            scale_x = new_w / w
            scale_y = new_h / h
            
            for p in bayesian_init_paths:
                for pt in p['points']:
                    pt[0] *= scale_x
                    pt[1] *= scale_y

            # Determine device for Bayesian renderer
            device = self.device
            if device == 'cuda' and not torch.cuda.is_available():
                device = 'cpu'
            elif device == 'mps' and not (hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()):
                device = 'cpu'
            
            renderer = BayesianVectorRenderer(img_small, device=device, init_paths=bayesian_init_paths, num_segments=16)
            
            print("Optimizing paths (Fine-tuning)...")
            # More iterations for fidelity
            # num_iters = 300
            # start_sigma = 5.0
            # end_sigma = 0.5
            
            # for i in range(num_iters):
            #     # Anneal sigma
            #     sigma = start_sigma + (end_sigma - start_sigma) * (i / num_iters)
            #     
            #     optimizer.zero_grad()
            #     rendered = renderer.render_antialiased(sigma=sigma)
            #     
            #     # L1 loss might be better for sharp edges than MSE
            #     loss = torch.mean(torch.abs(rendered - renderer.target_image)) \
            #            + 1e-5 * renderer.complexity_penalty() \
            #            + 1e-5 * renderer.corner_penalty()
            #     
            #     loss.backward()
            #     optimizer.step()
            #     
            #     if i % 50 == 0:
            #         print(f"  Iter {i}: Loss = {loss.item():.4f}, Sigma = {sigma:.2f}")
            
            print("Converting to SVG...")
            paths = []
            
            # Scale back to ORIGINAL resolution (before upsampling)
            # Current renderer points are in `new_w` (which is ~1024)
            # We want to go back to `orig_w` (256)
            
            inv_scale_x = orig_w / new_w
            inv_scale_y = orig_h / new_h
            
            with torch.no_grad():
                for i in range(renderer.num_paths):
                    color = torch.sigmoid(renderer.colors[i]).cpu().numpy() * 255
                    points = renderer.points[i].cpu().numpy()
                    
                    # Scale points
                    points[:, 0] *= inv_scale_x
                    points[:, 1] *= inv_scale_y
                    
                    path_data = []
                    for s in range(renderer.num_segments):
                        idx = s * 3
                        p0 = points[idx]
                        c1 = points[idx+1]
                        c2 = points[idx+2]
                        p1 = points[idx+3]
                        path_data.append(('C', p0, c1, c2, p1))
                        
                    paths.append({
                        'type': 'bezier',
                        'data': path_data,
                        'color': color.astype(int)
                    })
            
            print(f"Saving to {output_path}...")
            self.writer.save_bezier(paths, output_path, (orig_h, orig_w))
            print("Done.")
            return

        # 4. Save Output (Standard SAM mode)
        print(f"Saving to {output_path}...")
        self.writer.save(paths, output_path, image.shape[:2])
        print("Done.")
