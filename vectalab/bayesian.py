"""
Bayesian Vector Renderer - Implementation of VectorMagic-style Bayesian Inversion.

This module implements the core Bayesian vectorization algorithm as described in
James Diebel's 2008 Stanford PhD thesis. The key insight is to treat vectorization
as a Bayesian inverse problem:

    V* = argmax_V P(V | I) = argmax_V P(I | V, C) * P(V | class)

Where:
- V = vector graphics (Bézier paths, colors)
- I = input raster image  
- C = color palette
- P(I | V, C) = likelihood (how well does rendering V match I?)
- P(V | class) = prior (prefer simple, smooth paths)

The optimization uses a differentiable renderer with soft anti-aliasing.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import cv2
from typing import List, Dict, Tuple, Optional
from sklearn.cluster import KMeans
from skimage.segmentation import slic
from skimage.measure import find_contours
from scipy import ndimage


class ColorPalette:
    """
    Hierarchical color palette extraction using LAB space clustering.
    
    Step 3 of the algorithm: Initial Color Palette Proposal
    - Use hierarchical clustering in LAB + spatial regularization
    - Start with K=256 → greedily merge clusters while ΔE² < threshold
    """
    
    def __init__(self, num_colors: int = 64, merge_threshold: float = 5.0):
        self.num_colors = num_colors
        self.merge_threshold = merge_threshold  # ΔE threshold for merging
    
    def extract(self, image_rgb: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract color palette from image.
        
        Args:
            image_rgb: RGB image [H, W, 3] with values 0-255
            
        Returns:
            palette: [K, 3] LAB color values
            labels: [H, W] cluster assignment for each pixel
        """
        h, w = image_rgb.shape[:2]
        
        # Convert to LAB
        image_lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
        
        # Reshape for clustering
        pixels_lab = image_lab.reshape(-1, 3)
        
        # Add spatial coordinates for spatial regularization
        y_coords, x_coords = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')
        y_norm = y_coords.flatten() / h * 10  # Scale factor for spatial influence
        x_norm = x_coords.flatten() / w * 10
        
        # Combine LAB + spatial
        features = np.column_stack([pixels_lab, x_norm, y_norm])
        
        # K-means clustering
        kmeans = KMeans(n_clusters=min(self.num_colors, len(features) // 10), 
                       random_state=42, n_init=10)
        labels = kmeans.fit_predict(features)
        
        # Extract palette (LAB values only, not spatial)
        palette = kmeans.cluster_centers_[:, :3]
        
        # Reshape labels
        labels = labels.reshape(h, w)
        
        return palette, labels
    
    def palette_to_rgb(self, palette_lab: np.ndarray) -> np.ndarray:
        """Convert LAB palette to RGB."""
        # Create a 1xK image for conversion
        lab_img = palette_lab.reshape(1, -1, 3).astype(np.float32)
        rgb_img = cv2.cvtColor(lab_img, cv2.COLOR_LAB2RGB)
        return (rgb_img.reshape(-1, 3) * 255).astype(np.uint8)


class RegionExtractor:
    """
    Extract initial regions using superpixel segmentation (SLIC).
    
    Step 5 Initialize of the algorithm:
    - Run superpixel segmentation (SLIC) → candidate regions
    - Fit initial polygons using Ramer–Douglas–Peucker on zero-level sets
    """
    
    def __init__(self, n_segments: int = 200, compactness: float = 10.0):
        self.n_segments = n_segments
        self.compactness = compactness
    
    def extract_regions(self, image_rgb: np.ndarray) -> List[Dict]:
        """
        Extract regions from image using SLIC superpixels.
        
        Returns:
            List of regions with contours and colors
        """
        # SLIC superpixel segmentation
        segments = slic(image_rgb, n_segments=self.n_segments, 
                       compactness=self.compactness, start_label=0)
        
        regions = []
        
        for segment_id in np.unique(segments):
            mask = (segments == segment_id).astype(np.uint8)
            
            # Get contour
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if len(contours) == 0:
                continue
            
            # Get largest contour
            contour = max(contours, key=cv2.contourArea)
            
            if cv2.contourArea(contour) < 10:
                continue
            
            # Simplify contour with Douglas-Peucker
            epsilon = 0.01 * cv2.arcLength(contour, True)
            simplified = cv2.approxPolyDP(contour, epsilon, True)
            
            # Get mean color in region
            mean_color = image_rgb[mask > 0].mean(axis=0)
            
            # Convert contour to points list
            points = simplified.reshape(-1, 2).tolist()
            
            regions.append({
                'points': points,
                'color': mean_color.tolist(),
                'area': cv2.contourArea(contour),
                'mask': mask
            })
        
        # Sort by area (largest first for proper layering)
        regions.sort(key=lambda x: x['area'], reverse=True)
        
        return regions


class DifferentiableBezierRenderer(nn.Module):
    """
    Pure PyTorch differentiable Bézier curve renderer using soft rasterization.
    
    This implements the forward model: Render(V, C) → Î
    with differentiable anti-aliasing for backpropagation.
    """
    
    def __init__(self, width: int, height: int, device: str = 'cpu'):
        super().__init__()
        self.width = width
        self.height = height
        self.device = device
        
        # Create coordinate grids
        y_coords = torch.arange(height, dtype=torch.float32, device=device)
        x_coords = torch.arange(width, dtype=torch.float32, device=device)
        self.register_buffer('grid_y', y_coords.view(-1, 1).expand(height, width))
        self.register_buffer('grid_x', x_coords.view(1, -1).expand(height, width))
    
    def cubic_bezier(self, t: torch.Tensor, p0: torch.Tensor, p1: torch.Tensor,
                     p2: torch.Tensor, p3: torch.Tensor) -> torch.Tensor:
        """Evaluate cubic Bézier curve at parameter t."""
        t = t.view(-1, 1)
        t2 = t * t
        t3 = t2 * t
        mt = 1 - t
        mt2 = mt * mt
        mt3 = mt2 * mt
        
        return mt3 * p0 + 3 * mt2 * t * p1 + 3 * mt * t2 * p2 + t3 * p3
    
    def sample_bezier_path(self, control_points: torch.Tensor, 
                           samples_per_segment: int = 20) -> torch.Tensor:
        """
        Sample points along a Bézier path.
        
        Args:
            control_points: [N, 2] where N = num_segments * 3 + 1
            samples_per_segment: Number of samples per Bézier segment
            
        Returns:
            [M, 2] sampled points
        """
        num_points = control_points.shape[0]
        num_segments = (num_points - 1) // 3
        
        if num_segments < 1:
            return control_points
        
        all_points = []
        t_vals = torch.linspace(0, 1, samples_per_segment, device=self.device)
        
        for seg in range(num_segments):
            idx = seg * 3
            p0 = control_points[idx]
            p1 = control_points[idx + 1]
            p2 = control_points[idx + 2]
            p3 = control_points[min(idx + 3, num_points - 1)]
            
            points = self.cubic_bezier(t_vals, p0, p1, p2, p3)
            all_points.append(points)
        
        return torch.cat(all_points, dim=0)
    
    def compute_winding_number(self, path_points: torch.Tensor, 
                               sigma: float = 1.0) -> torch.Tensor:
        """
        Compute soft winding number for all pixels using scanline approach.
        
        Uses ray casting with soft boundaries for differentiability.
        More memory efficient by processing in chunks.
        """
        n_points = path_points.shape[0]
        
        # Process in chunks to avoid memory issues
        chunk_size = 32
        winding = torch.zeros(self.height, self.width, device=self.device)
        
        for i in range(0, n_points, chunk_size):
            end_i = min(i + chunk_size, n_points)
            
            for j in range(i, end_i):
                # Current and next point (wrap around)
                p0 = path_points[j]
                p1 = path_points[(j + 1) % n_points]
                
                x0, y0 = p0[0], p0[1]
                x1, y1 = p1[0], p1[1]
                
                # Skip horizontal segments
                dy = y1 - y0
                if torch.abs(dy) < 1e-6:
                    continue
                
                # For each pixel, check if horizontal ray to the right crosses this segment
                # t parameter where ray at pixel's y crosses the segment
                t_cross = (self.grid_y - y0) / (dy + 1e-8)
                
                # x coordinate where crossing occurs
                x_cross = x0 + t_cross * (x1 - x0)
                
                # Soft validity check (t in [0, 1])
                valid_t = torch.sigmoid((t_cross - 0) * 20) * torch.sigmoid((1 - t_cross) * 20)
                
                # Soft check if crossing is to the right of pixel
                crosses_right = torch.sigmoid((x_cross - self.grid_x) / sigma)
                
                # Direction of crossing (up or down)
                direction = torch.sign(dy)
                
                # Accumulate winding contribution
                winding = winding + crosses_right * valid_t * direction
        
        return winding
    
    def render_filled_path(self, control_points: torch.Tensor, 
                           color: torch.Tensor,
                           sigma: float = 1.0) -> torch.Tensor:
        """
        Render a filled closed path with soft anti-aliasing.
        
        Args:
            control_points: [N, 2] Bézier control points
            color: [3] RGB color (0-1)
            sigma: Anti-aliasing width
            
        Returns:
            [H, W, 4] RGBA image
        """
        # Sample path densely
        path_points = self.sample_bezier_path(control_points, samples_per_segment=32)
        
        # Compute soft winding number
        winding = self.compute_winding_number(path_points, sigma)
        
        # Convert to alpha (inside = 1, outside = 0)
        # Use sigmoid for soft threshold
        alpha = torch.sigmoid(winding * 4)
        
        # Create RGBA output
        rgba = torch.zeros(self.height, self.width, 4, device=self.device)
        rgba[..., :3] = color.view(1, 1, 3)
        rgba[..., 3] = alpha
        
        return rgba


class BayesianVectorRenderer(nn.Module):
    """
    Full Bayesian vectorization system implementing the VectorMagic algorithm.
    
    This is the core of the Bayesian inversion approach:
    
    Log-posterior E(V) = −‖ I↑ − Render(V,C) ‖²_LAB
                         − λ_complexity × (number of paths + total Bézier segments)
                         − λ_corner × ∑ corner_penalty
                         − λ_overlap × overlap_area
                         + prior_terms from image class
    """
    
    def __init__(self, 
                 target_image: np.ndarray,
                 device: str = 'cpu',
                 init_paths: Optional[List[Dict]] = None,
                 num_paths: int = 64,
                 num_segments: int = 4,
                 sigma_aa: float = 1.0):
        """
        Initialize the Bayesian vector renderer.
        
        Args:
            target_image: RGB image [H, W, 3] with values 0-255
            device: 'cpu', 'cuda', or 'mps'
            init_paths: Optional initial paths from prior segmentation
            num_paths: Number of vector paths to optimize
            num_segments: Number of Bézier segments per path
            sigma_aa: Anti-aliasing sigma
        """
        super().__init__()
        
        self.device = device
        self.height, self.width = target_image.shape[:2]
        self.num_paths = num_paths
        self.num_segments = num_segments
        self.sigma_aa = sigma_aa
        
        # Convert target to tensor [0, 1]
        target = torch.from_numpy(target_image.copy()).float().to(device) / 255.0
        self.register_buffer('target_image', target)
        
        # Convert to LAB for perceptual loss
        target_lab = self._rgb_to_lab_tensor(target)
        self.register_buffer('target_lab', target_lab)
        
        # Initialize renderer
        self.renderer = DifferentiableBezierRenderer(self.width, self.height, device)
        
        # Estimate AA sigma from edges
        self.sigma_aa = self._estimate_aa_sigma(target_image)
        
        # Initialize paths
        if init_paths is not None and len(init_paths) > 0:
            self._initialize_from_paths(init_paths)
        else:
            self._initialize_from_regions(target_image)
    
    def _rgb_to_lab_tensor(self, rgb: torch.Tensor) -> torch.Tensor:
        """Convert RGB [0,1] tensor to LAB color space (approximate)."""
        # Linearize sRGB
        rgb_linear = torch.where(
            rgb <= 0.04045,
            rgb / 12.92,
            ((rgb + 0.055) / 1.055) ** 2.4
        )
        
        r, g, b = rgb_linear[..., 0], rgb_linear[..., 1], rgb_linear[..., 2]
        
        # RGB to XYZ (D65)
        x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
        y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
        z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
        
        # XYZ to LAB
        xn, yn, zn = 0.95047, 1.0, 1.08883
        
        def f(t):
            delta = 6/29
            return torch.where(t > delta**3, t ** (1/3), t / (3 * delta**2) + 4/29)
        
        L = 116 * f(y/yn) - 16
        a = 500 * (f(x/xn) - f(y/yn))
        b_lab = 200 * (f(y/yn) - f(z/zn))
        
        return torch.stack([L, a, b_lab], dim=-1)
    
    def _estimate_aa_sigma(self, image: np.ndarray) -> float:
        """Estimate anti-aliasing kernel width from edge statistics."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(gx**2 + gy**2)
        
        threshold = np.percentile(grad_mag, 90)
        edge_pixels = grad_mag > threshold
        
        if np.sum(edge_pixels) > 0:
            sigma = 1.0 / (np.mean(grad_mag[edge_pixels]) / 255.0 + 0.1)
            sigma = np.clip(sigma, 0.5, 2.0)
        else:
            sigma = 1.0
        
        return sigma
    
    def _initialize_from_regions(self, image: np.ndarray):
        """Initialize paths from automatic region extraction."""
        print("Extracting regions using SLIC superpixels...")
        extractor = RegionExtractor(n_segments=self.num_paths * 2, compactness=10.0)
        regions = extractor.extract_regions(image)
        
        # Take top regions by area
        regions = regions[:self.num_paths]
        
        if len(regions) > 0:
            self._initialize_from_paths(regions)
        else:
            self._initialize_random_paths()
    
    def _initialize_from_paths(self, init_paths: List[Dict]):
        """Initialize from pre-computed paths."""
        num_init = len(init_paths)
        self.num_paths = max(num_init, 16)  # Ensure minimum paths
        
        points_per_path = self.num_segments * 3 + 1
        points = torch.zeros(self.num_paths, points_per_path, 2, device=self.device)
        colors = torch.zeros(self.num_paths, 3, device=self.device)
        
        for i, path in enumerate(init_paths[:self.num_paths]):
            path_pts = np.array(path['points'])
            color = np.array(path['color']) / 255.0
            
            if len(path_pts) < 2:
                continue
            
            # Resample to required number of control points
            # Use cumulative distance for even sampling
            diffs = np.diff(path_pts, axis=0)
            dists = np.sqrt(np.sum(diffs**2, axis=1))
            cum_dist = np.concatenate([[0], np.cumsum(dists)])
            total_dist = cum_dist[-1]
            
            if total_dist > 0:
                target_dists = np.linspace(0, total_dist, points_per_path)
                resampled_x = np.interp(target_dists, cum_dist, path_pts[:, 0])
                resampled_y = np.interp(target_dists, cum_dist, path_pts[:, 1])
                resampled = np.stack([resampled_x, resampled_y], axis=1)
            else:
                resampled = np.zeros((points_per_path, 2)) + path_pts[0]
            
            points[i] = torch.from_numpy(resampled).float().to(self.device)
            
            # Convert color to logit space
            c = np.clip(color, 0.01, 0.99)
            colors[i] = torch.from_numpy(np.log(c / (1 - c))).float().to(self.device)
        
        # Fill remaining with random paths
        for i in range(num_init, self.num_paths):
            cx = np.random.uniform(0, self.width)
            cy = np.random.uniform(0, self.height)
            radius = np.random.uniform(10, 50)
            
            angles = np.linspace(0, 2 * np.pi, points_per_path, endpoint=False)
            pts = np.stack([
                cx + radius * np.cos(angles),
                cy + radius * np.sin(angles)
            ], axis=1)
            
            points[i] = torch.from_numpy(pts).float().to(self.device)
            
            # Random gray color
            c = np.random.uniform(0.2, 0.8)
            colors[i] = torch.full((3,), np.log(c / (1 - c)), device=self.device)
        
        self.points = nn.Parameter(points)
        self.colors = nn.Parameter(colors)
        self.z_order = nn.Parameter(torch.arange(self.num_paths, dtype=torch.float32, device=self.device))
        
        print(f"Initialized {self.num_paths} paths with {self.num_segments} segments each")
    
    def _initialize_random_paths(self):
        """Initialize with random circular paths."""
        points_per_path = self.num_segments * 3 + 1
        points = torch.zeros(self.num_paths, points_per_path, 2, device=self.device)
        colors = torch.randn(self.num_paths, 3, device=self.device) * 0.5
        
        for i in range(self.num_paths):
            cx = np.random.uniform(0, self.width)
            cy = np.random.uniform(0, self.height)
            radius = np.random.uniform(5, min(self.width, self.height) / 4)
            
            angles = np.linspace(0, 2 * np.pi, points_per_path, endpoint=False)
            pts = np.stack([
                cx + radius * np.cos(angles),
                cy + radius * np.sin(angles)
            ], axis=1)
            
            points[i] = torch.from_numpy(pts).float().to(self.device)
        
        self.points = nn.Parameter(points)
        self.colors = nn.Parameter(colors)
        self.z_order = nn.Parameter(torch.arange(self.num_paths, dtype=torch.float32, device=self.device))
    
    def render_antialiased(self, sigma: Optional[float] = None) -> torch.Tensor:
        """
        Render all paths with anti-aliasing.
        
        This implements: Render(vector V, palette C) → synthetic bitmap Î
        """
        if sigma is None:
            sigma = self.sigma_aa
        
        # Sort paths by z-order (back to front)
        _, order = torch.sort(self.z_order)
        
        # Start with white background
        canvas = torch.ones(self.height, self.width, 3, device=self.device)
        
        for idx in order:
            path_points = self.points[idx]
            path_color = torch.sigmoid(self.colors[idx])
            
            # Render this path
            rgba = self.renderer.render_filled_path(path_points, path_color, sigma)
            
            # Alpha composite (over operation)
            alpha = rgba[..., 3:4]
            rgb = rgba[..., :3]
            canvas = canvas * (1 - alpha) + rgb * alpha
        
        return canvas
    
    def compute_reconstruction_loss(self, rendered: torch.Tensor) -> torch.Tensor:
        """
        Compute reconstruction loss: −‖ I − Render(V,C) ‖²_LAB
        """
        rendered_lab = self._rgb_to_lab_tensor(rendered)
        
        # MSE in LAB space (perceptually uniform)
        lab_loss = F.mse_loss(rendered_lab, self.target_lab)
        
        # Also include RGB for stability
        rgb_loss = F.mse_loss(rendered, self.target_image)
        
        return lab_loss + 0.1 * rgb_loss
    
    def complexity_penalty(self) -> torch.Tensor:
        """
        Complexity penalty: prefer fewer/simpler paths.
        
        Penalizes total path length.
        """
        total_length = torch.tensor(0.0, device=self.device)
        
        for i in range(self.num_paths):
            diffs = self.points[i, 1:] - self.points[i, :-1]
            lengths = torch.sqrt(torch.sum(diffs ** 2, dim=-1) + 1e-8)
            total_length = total_length + torch.sum(lengths)
        
        # Normalize
        diag = np.sqrt(self.width ** 2 + self.height ** 2)
        return total_length / (diag * self.num_paths)
    
    def corner_penalty(self) -> torch.Tensor:
        """
        Corner penalty: prefer smooth curves.
        
        Penalizes sharp angles at control point junctions.
        """
        total_cost = torch.tensor(0.0, device=self.device)
        
        for i in range(self.num_paths):
            pts = self.points[i]
            
            for j in range(1, len(pts) - 1):
                v1 = pts[j] - pts[j-1]
                v2 = pts[j+1] - pts[j]
                
                # Normalize
                v1_n = v1 / (torch.norm(v1) + 1e-8)
                v2_n = v2 / (torch.norm(v2) + 1e-8)
                
                # Dot product = cos(angle)
                cos_angle = torch.sum(v1_n * v2_n)
                
                # Penalty for sharp corners (cos close to -1)
                corner_cost = (1 - cos_angle) / 2
                total_cost = total_cost + corner_cost ** 2
        
        return total_cost / (self.num_paths * self.num_segments)
    
    def smoothness_penalty(self) -> torch.Tensor:
        """
        Smoothness penalty for G1 continuity.
        """
        total = torch.tensor(0.0, device=self.device)
        
        for i in range(self.num_paths):
            pts = self.points[i]
            
            # Second derivative approximation
            for j in range(1, len(pts) - 1):
                d2 = pts[j-1] - 2 * pts[j] + pts[j+1]
                total = total + torch.sum(d2 ** 2)
        
        return total / (self.num_paths * self.num_segments)
    
    def compute_total_loss(self,
                           lambda_complexity: float = 0.02,
                           lambda_corner: float = 0.01,
                           lambda_smooth: float = 0.001,
                           sigma: Optional[float] = None) -> Tuple[torch.Tensor, Dict]:
        """
        Compute total Bayesian posterior energy.
        
        E(V) = reconstruction + λ_c*complexity + λ_corner*corners + λ_s*smooth
        """
        rendered = self.render_antialiased(sigma)
        
        recon = self.compute_reconstruction_loss(rendered)
        complexity = self.complexity_penalty()
        corners = self.corner_penalty()
        smooth = self.smoothness_penalty()
        
        total = recon + lambda_complexity * complexity + lambda_corner * corners + lambda_smooth * smooth
        
        losses = {
            'total': total.item(),
            'reconstruction': recon.item(),
            'complexity': complexity.item(),
            'corners': corners.item(),
            'smoothness': smooth.item()
        }
        
        return total, losses
    
    def propose_topology_changes(self, threshold: float = 0.1):
        """
        Propose topology changes (Phase C of the algorithm).
        
        Reinitialize poorly performing paths to high-error regions.
        """
        with torch.no_grad():
            rendered = self.render_antialiased()
            
            # Find high-error regions
            error = torch.sum((rendered - self.target_image) ** 2, dim=-1)
            
            # Evaluate each path's contribution
            path_errors = []
            for i in range(self.num_paths):
                pts = self.points[i]
                center = pts.mean(dim=0)
                x, y = int(center[0].clamp(0, self.width-1)), int(center[1].clamp(0, self.height-1))
                path_errors.append((i, error[y, x].item()))
            
            # Reinitialize worst paths
            path_errors.sort(key=lambda x: x[1], reverse=True)
            num_reinit = max(1, self.num_paths // 10)
            
            for idx, _ in path_errors[:num_reinit]:
                # Sample from high-error region
                flat_error = error.view(-1)
                probs = F.softmax(flat_error * 10, dim=0)
                sampled_idx = torch.multinomial(probs, 1).item()
                y, x = sampled_idx // self.width, sampled_idx % self.width
                
                # Create new path
                points_per_path = self.num_segments * 3 + 1
                radius = np.random.uniform(10, 30)
                angles = np.linspace(0, 2 * np.pi, points_per_path, endpoint=False)
                
                new_pts = torch.zeros(points_per_path, 2, device=self.device)
                new_pts[:, 0] = x + radius * torch.cos(torch.from_numpy(angles).float().to(self.device))
                new_pts[:, 1] = y + radius * torch.sin(torch.from_numpy(angles).float().to(self.device))
                
                new_pts[:, 0].clamp_(0, self.width - 1)
                new_pts[:, 1].clamp_(0, self.height - 1)
                
                self.points.data[idx] = new_pts
                
                # Set color to match target
                target_color = self.target_image[y, x]
                self.colors.data[idx] = torch.logit(target_color.clamp(0.01, 0.99))
    
    def export_svg(self, filepath: str):
        """Export current paths to SVG."""
        _, order = torch.sort(self.z_order)
        
        svg = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">',
            '  <rect width="100%" height="100%" fill="white"/>',
        ]
        
        for idx in order:
            pts = self.points[idx].detach().cpu().numpy()
            color = torch.sigmoid(self.colors[idx]).detach().cpu().numpy()
            r, g, b = int(color[0]*255), int(color[1]*255), int(color[2]*255)
            
            # Build path
            d = f"M {pts[0,0]:.2f} {pts[0,1]:.2f}"
            
            for seg in range(self.num_segments):
                i = seg * 3
                if i + 3 < len(pts):
                    c1, c2, p1 = pts[i+1], pts[i+2], pts[i+3]
                    d += f" C {c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {p1[0]:.2f} {p1[1]:.2f}"
            
            d += " Z"
            svg.append(f'  <path d="{d}" fill="rgb({r},{g},{b})" stroke="none"/>')
        
        svg.append('</svg>')
        
        with open(filepath, 'w') as f:
            f.write('\n'.join(svg))


def optimize_vectorization(image: np.ndarray,
                          device: str = 'cpu',
                          num_paths: int = 128,
                          num_segments: int = 8,
                          num_iterations: int = 500,
                          learning_rate: float = 1.0,
                          topology_interval: int = 50,
                          target_psnr: float = 38.0,
                          verbose: bool = True) -> BayesianVectorRenderer:
    """
    Full Bayesian vectorization optimization.
    
    Implements the iterative optimization (Step 5):
    - Phase A: Color & Topology Reassignment
    - Phase B: Geometry Optimization (continuous)
    - Phase C: Topology Proposal
    
    Args:
        image: Input RGB image [H, W, 3] with values 0-255
        device: Computation device
        num_paths: Number of vector paths
        num_segments: Bézier segments per path
        num_iterations: Optimization iterations
        learning_rate: Adam learning rate
        topology_interval: How often to propose topology changes
        target_psnr: Target PSNR (algorithm terminates if reached)
        verbose: Print progress
        
    Returns:
        Optimized BayesianVectorRenderer
    """
    renderer = BayesianVectorRenderer(
        image,
        device=device,
        num_paths=num_paths,
        num_segments=num_segments
    )
    
    optimizer = torch.optim.Adam(renderer.parameters(), lr=learning_rate)
    
    # Sigma annealing (start blurry, sharpen over time)
    start_sigma = 5.0
    end_sigma = renderer.sigma_aa
    
    best_psnr = 0.0
    
    for i in range(num_iterations):
        progress = i / num_iterations
        
        # Anneal sigma
        sigma = start_sigma + (end_sigma - start_sigma) * progress
        
        # Anneal regularization (relax over time)
        lambda_complexity = 0.02 * (1 - progress * 0.5)
        lambda_corner = 0.01 * (1 - progress * 0.5)
        
        optimizer.zero_grad()
        
        loss, losses = renderer.compute_total_loss(
            lambda_complexity=lambda_complexity,
            lambda_corner=lambda_corner,
            sigma=sigma
        )
        
        loss.backward()
        
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(renderer.parameters(), 1.0)
        
        optimizer.step()
        
        # Clamp points to image bounds
        with torch.no_grad():
            renderer.points.data[..., 0].clamp_(0, renderer.width - 1)
            renderer.points.data[..., 1].clamp_(0, renderer.height - 1)
        
        # Compute PSNR
        with torch.no_grad():
            rendered = renderer.render_antialiased()
            mse = F.mse_loss(rendered, renderer.target_image).item()
            psnr = 10 * np.log10(1.0 / (mse + 1e-10))
            
            if psnr > best_psnr:
                best_psnr = psnr
        
        # Topology changes (Phase C)
        if (i + 1) % topology_interval == 0:
            renderer.propose_topology_changes()
        
        if verbose and (i + 1) % 25 == 0:
            print(f"Iter {i+1}/{num_iterations}: Loss={losses['total']:.4f}, "
                  f"Recon={losses['reconstruction']:.4f}, PSNR={psnr:.2f}dB, sigma={sigma:.2f}")
        
        # Early termination if target reached
        if psnr >= target_psnr:
            if verbose:
                print(f"Target PSNR {target_psnr}dB reached at iteration {i+1}")
            break
    
    if verbose:
        print(f"Best PSNR: {best_psnr:.2f}dB")
    
    return renderer
