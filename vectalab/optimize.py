"""
Vectalab SVG Optimization Module.

This module provides comprehensive SVG optimization for creating lightweight,
Figma-compatible SVG files. It includes:
- Path simplification (Ramer-Douglas-Peucker algorithm)
- Shape primitive detection (circles, ellipses, rectangles)
- SVG post-processing (using scour or custom optimization)
- Path merging for same-color regions

Usage:
    from vectalab.optimize import SVGOptimizer
    
    optimizer = SVGOptimizer()
    optimized_svg = optimizer.optimize("input.svg", "output.svg")
"""

import re
import math
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
from io import StringIO
import numpy as np
import cv2

# Try to import scour for SVG optimization
try:
    from scour import scour
    SCOUR_AVAILABLE = True
except ImportError:
    SCOUR_AVAILABLE = False


# ============================================================================
# PATH SIMPLIFICATION
# ============================================================================

def rdp_simplify(points: List[Tuple[float, float]], epsilon: float) -> List[Tuple[float, float]]:
    """
    Ramer-Douglas-Peucker algorithm for path simplification.
    
    Reduces the number of points in a curve while preserving the shape.
    
    Args:
        points: List of (x, y) coordinate tuples
        epsilon: Maximum distance threshold for point removal
        
    Returns:
        Simplified list of points
    """
    if len(points) < 3:
        return points
    
    # Find the point with maximum distance from line between start and end
    start, end = points[0], points[-1]
    max_dist = 0
    max_idx = 0
    
    for i in range(1, len(points) - 1):
        dist = perpendicular_distance(points[i], start, end)
        if dist > max_dist:
            max_dist = dist
            max_idx = i
    
    # If max distance is greater than epsilon, recursively simplify
    if max_dist > epsilon:
        left = rdp_simplify(points[:max_idx + 1], epsilon)
        right = rdp_simplify(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [start, end]


def perpendicular_distance(point: Tuple[float, float], 
                           line_start: Tuple[float, float], 
                           line_end: Tuple[float, float]) -> float:
    """Calculate perpendicular distance from point to line."""
    x, y = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    dx = x2 - x1
    dy = y2 - y1
    
    if dx == 0 and dy == 0:
        return math.sqrt((x - x1) ** 2 + (y - y1) ** 2)
    
    t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))
    
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    
    return math.sqrt((x - proj_x) ** 2 + (y - proj_y) ** 2)


def simplify_svg_path(path_data: str, epsilon: float = 1.0) -> str:
    """
    Simplify an SVG path d attribute using RDP algorithm.
    
    Args:
        path_data: SVG path d attribute string
        epsilon: Simplification tolerance
        
    Returns:
        Simplified path d attribute
    """
    # Parse path into segments
    segments = parse_path_data(path_data)
    
    if not segments:
        return path_data
    
    # Extract all points
    points = []
    current = (0, 0)
    
    for cmd, args in segments:
        if cmd in 'Mm':
            if cmd == 'M':
                current = (args[0], args[1])
            else:
                current = (current[0] + args[0], current[1] + args[1])
            points.append(current)
        elif cmd in 'Ll':
            if cmd == 'L':
                current = (args[0], args[1])
            else:
                current = (current[0] + args[0], current[1] + args[1])
            points.append(current)
        elif cmd in 'Cc':
            # For curves, just add the end point
            if cmd == 'C':
                current = (args[4], args[5])
            else:
                current = (current[0] + args[4], current[1] + args[5])
            points.append(current)
        elif cmd in 'Zz':
            pass  # Close path
    
    if len(points) < 3:
        return path_data
    
    # Simplify points
    simplified = rdp_simplify(points, epsilon)
    
    # Rebuild path (simplified version - lines only)
    if len(simplified) < 2:
        return path_data
    
    d = f"M{simplified[0][0]:.2f},{simplified[0][1]:.2f}"
    for p in simplified[1:]:
        d += f"L{p[0]:.2f},{p[1]:.2f}"
    
    # Check if original path was closed
    if path_data.upper().endswith('Z'):
        d += "Z"
    
    return d


def parse_path_data(d: str) -> List[Tuple[str, List[float]]]:
    """
    Parse SVG path d attribute into segments.
    
    Args:
        d: Path data string
        
    Returns:
        List of (command, arguments) tuples
    """
    # Match commands and their arguments
    pattern = r'([MmLlHhVvCcSsQqTtAaZz])\s*([^MmLlHhVvCcSsQqTtAaZz]*)'
    segments = []
    
    for match in re.finditer(pattern, d):
        cmd = match.group(1)
        args_str = match.group(2).strip()
        
        if args_str:
            # Parse numbers (handle negative numbers and commas)
            args = [float(x) for x in re.findall(r'-?[\d.]+', args_str)]
        else:
            args = []
        
        segments.append((cmd, args))
    
    return segments


# ============================================================================
# SHAPE PRIMITIVE DETECTION
# ============================================================================

def detect_circle(points: List[Tuple[float, float]], tolerance: float = 0.1) -> Optional[Dict]:
    """
    Detect if points form a circle.
    
    Args:
        points: List of (x, y) coordinate tuples
        tolerance: Maximum deviation from perfect circle (0-1)
        
    Returns:
        Dict with cx, cy, r if circle detected, None otherwise
    """
    if len(points) < 8:  # Need enough points to reliably detect
        return None
    
    # Convert to numpy array
    pts = np.array(points, dtype=np.float32)
    
    # Fit minimum enclosing circle
    (cx, cy), radius = cv2.minEnclosingCircle(pts)
    
    if radius < 5:  # Too small to be meaningful
        return None
    
    # Check if points lie on the circle
    distances = np.sqrt((pts[:, 0] - cx) ** 2 + (pts[:, 1] - cy) ** 2)
    deviation = np.std(distances) / radius
    
    if deviation < tolerance:
        return {'cx': cx, 'cy': cy, 'r': radius}
    
    return None


def detect_ellipse(points: List[Tuple[float, float]], tolerance: float = 0.1) -> Optional[Dict]:
    """
    Detect if points form an ellipse.
    
    Args:
        points: List of (x, y) coordinate tuples
        tolerance: Maximum deviation from perfect ellipse (0-1)
        
    Returns:
        Dict with cx, cy, rx, ry, angle if ellipse detected, None otherwise
    """
    if len(points) < 10:  # Need enough points
        return None
    
    # Convert to numpy array and ensure contiguous
    pts = np.array(points, dtype=np.float32).reshape((-1, 1, 2))
    
    if len(pts) < 5:
        return None
    
    try:
        # Fit ellipse
        ellipse = cv2.fitEllipse(pts)
        (cx, cy), (width, height), angle = ellipse
        rx, ry = width / 2, height / 2
        
        if rx < 5 or ry < 5:  # Too small
            return None
        
        # Check fit quality by computing area ratio
        hull = cv2.convexHull(pts)
        hull_area = cv2.contourArea(hull)
        ellipse_area = math.pi * rx * ry
        
        if ellipse_area == 0:
            return None
        
        ratio = hull_area / ellipse_area
        
        if abs(ratio - 1.0) < tolerance:
            return {'cx': cx, 'cy': cy, 'rx': rx, 'ry': ry, 'angle': angle}
    except cv2.error:
        return None
    
    return None


def detect_rectangle(points: List[Tuple[float, float]], tolerance: float = 0.1) -> Optional[Dict]:
    """
    Detect if points form a rectangle.
    
    Args:
        points: List of (x, y) coordinate tuples
        tolerance: Maximum deviation from perfect rectangle (0-1)
        
    Returns:
        Dict with x, y, width, height, angle if rectangle detected, None otherwise
    """
    if len(points) < 4:
        return None
    
    # Convert to numpy array
    pts = np.array(points, dtype=np.float32).reshape((-1, 1, 2))
    
    try:
        # Fit minimum area rectangle
        rect = cv2.minAreaRect(pts)
        (cx, cy), (width, height), angle = rect
        
        if width < 5 or height < 5:  # Too small
            return None
        
        # Check fit quality
        contour_area = cv2.contourArea(pts)
        rect_area = width * height
        
        if rect_area == 0:
            return None
        
        ratio = contour_area / rect_area
        
        if abs(ratio - 1.0) < tolerance:
            x = cx - width / 2
            y = cy - height / 2
            return {'x': x, 'y': y, 'width': width, 'height': height, 'angle': angle}
    except cv2.error:
        return None
    
    return None


def path_to_primitive(path_data: str, tolerance: float = 0.1) -> Optional[Tuple[str, Dict]]:
    """
    Attempt to convert a path to a shape primitive.
    
    Args:
        path_data: SVG path d attribute
        tolerance: Detection tolerance
        
    Returns:
        Tuple of (element_type, attributes) or None
    """
    # Parse path to points
    segments = parse_path_data(path_data)
    if not segments:
        return None
    
    points = []
    current = (0, 0)
    
    for cmd, args in segments:
        if cmd in 'Mm':
            current = (args[0], args[1]) if cmd == 'M' else (current[0] + args[0], current[1] + args[1])
            points.append(current)
        elif cmd in 'LlHhVv':
            if cmd == 'L':
                current = (args[0], args[1])
            elif cmd == 'l':
                current = (current[0] + args[0], current[1] + args[1])
            elif cmd == 'H':
                current = (args[0], current[1])
            elif cmd == 'h':
                current = (current[0] + args[0], current[1])
            elif cmd == 'V':
                current = (current[0], args[0])
            elif cmd == 'v':
                current = (current[0], current[1] + args[0])
            points.append(current)
        elif cmd in 'Cc':
            # For curves, sample points along the curve
            if cmd == 'C' and len(args) >= 6:
                # Sample Bezier curve
                for t in [0.25, 0.5, 0.75]:
                    p = bezier_point(current, (args[0], args[1]), (args[2], args[3]), (args[4], args[5]), t)
                    points.append(p)
                current = (args[4], args[5])
            elif cmd == 'c' and len(args) >= 6:
                end = (current[0] + args[4], current[1] + args[5])
                for t in [0.25, 0.5, 0.75]:
                    p = bezier_point(current, 
                                     (current[0] + args[0], current[1] + args[1]),
                                     (current[0] + args[2], current[1] + args[3]),
                                     end, t)
                    points.append(p)
                current = end
            points.append(current)
    
    if len(points) < 4:
        return None
    
    # Try to detect primitives (order: most specific to least)
    
    # Check for circle first
    circle = detect_circle(points, tolerance * 0.5)  # Stricter for circles
    if circle:
        return ('circle', circle)
    
    # Check for rectangle
    rect = detect_rectangle(points, tolerance)
    if rect:
        # Convert to axis-aligned if angle is small
        if abs(rect['angle']) < 5 or abs(rect['angle'] - 90) < 5 or abs(rect['angle'] + 90) < 5:
            return ('rect', {'x': rect['x'], 'y': rect['y'], 
                            'width': rect['width'], 'height': rect['height']})
        else:
            # Need transform for rotated rect
            return ('rect', rect)
    
    # Check for ellipse
    ellipse = detect_ellipse(points, tolerance)
    if ellipse:
        return ('ellipse', ellipse)
    
    return None


def bezier_point(p0: Tuple[float, float], p1: Tuple[float, float],
                 p2: Tuple[float, float], p3: Tuple[float, float], t: float) -> Tuple[float, float]:
    """Calculate point on cubic Bezier curve at parameter t."""
    u = 1 - t
    x = u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0]
    y = u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]
    return (x, y)


def primitive_to_svg(element_type: str, attrs: Dict, fill: str) -> str:
    """Convert a detected primitive to SVG element string."""
    if element_type == 'circle':
        return f'<circle cx="{attrs["cx"]:.2f}" cy="{attrs["cy"]:.2f}" r="{attrs["r"]:.2f}" fill="{fill}"/>'
    
    elif element_type == 'ellipse':
        transform = ""
        if 'angle' in attrs and abs(attrs['angle']) > 1:
            transform = f' transform="rotate({attrs["angle"]:.1f} {attrs["cx"]:.2f} {attrs["cy"]:.2f})"'
        return f'<ellipse cx="{attrs["cx"]:.2f}" cy="{attrs["cy"]:.2f}" rx="{attrs["rx"]:.2f}" ry="{attrs["ry"]:.2f}" fill="{fill}"{transform}/>'
    
    elif element_type == 'rect':
        transform = ""
        if 'angle' in attrs and abs(attrs['angle']) > 1:
            cx = attrs['x'] + attrs['width'] / 2
            cy = attrs['y'] + attrs['height'] / 2
            transform = f' transform="rotate({attrs["angle"]:.1f} {cx:.2f} {cy:.2f})"'
        return f'<rect x="{attrs["x"]:.2f}" y="{attrs["y"]:.2f}" width="{attrs["width"]:.2f}" height="{attrs["height"]:.2f}" fill="{fill}"{transform}/>'
    
    return ""


# ============================================================================
# SVG OPTIMIZATION
# ============================================================================

class SVGOptimizer:
    """
    Comprehensive SVG optimizer for creating lightweight, Figma-compatible files.
    
    Features:
    - Path simplification using RDP algorithm
    - Shape primitive detection (circles, ellipses, rectangles)
    - Attribute cleanup and optimization
    - Color optimization
    - Scour integration (if available)
    """
    
    def __init__(self, 
                 simplify_paths: bool = True,
                 detect_primitives: bool = True,
                 merge_colors: bool = True,
                 use_scour: bool = True,
                 path_precision: int = 2,
                 simplify_epsilon: float = 1.0,
                 primitive_tolerance: float = 0.1):
        """
        Initialize the optimizer.
        
        Args:
            simplify_paths: Enable path simplification
            detect_primitives: Enable shape primitive detection
            merge_colors: Merge paths with identical colors
            use_scour: Use scour for final optimization (if available)
            path_precision: Decimal precision for path coordinates
            simplify_epsilon: RDP simplification tolerance
            primitive_tolerance: Tolerance for primitive detection
        """
        self.simplify_paths = simplify_paths
        self.detect_primitives = detect_primitives
        self.merge_colors = merge_colors
        self.use_scour = use_scour and SCOUR_AVAILABLE
        self.path_precision = path_precision
        self.simplify_epsilon = simplify_epsilon
        self.primitive_tolerance = primitive_tolerance
    
    def optimize(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Optimize an SVG file.
        
        Args:
            input_path: Path to input SVG file
            output_path: Path for output (None to return string only)
            
        Returns:
            Optimized SVG content as string
        """
        # Read input
        with open(input_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        
        # Apply optimizations
        optimized = self.optimize_string(svg_content)
        
        # Write output if path provided
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
        
        return optimized
    
    def optimize_string(self, svg_content: str) -> str:
        """
        Optimize SVG content string.
        
        Args:
            svg_content: SVG content as string
            
        Returns:
            Optimized SVG content
        """
        # Parse SVG
        try:
            root = ET.fromstring(svg_content)
        except ET.ParseError:
            return svg_content  # Return unchanged if parse fails
        
        # Get namespace
        ns = self._get_namespace(root)
        ns_prefix = f'{{{ns}}}' if ns else ''
        
        # Optimize elements
        self._optimize_element(root, ns_prefix)
        
        # Convert back to string
        optimized = ET.tostring(root, encoding='unicode')
        
        # Clean up namespace declarations
        optimized = self._clean_namespaces(optimized, ns)
        
        # Apply scour if available
        if self.use_scour:
            optimized = self._apply_scour(optimized)
        else:
            # Apply custom final cleanup
            optimized = self._final_cleanup(optimized)
        
        return optimized
    
    def _get_namespace(self, root: ET.Element) -> str:
        """Extract namespace from root element."""
        if root.tag.startswith('{'):
            return root.tag.split('}')[0][1:]
        return ''
    
    def _optimize_element(self, element: ET.Element, ns_prefix: str) -> None:
        """Recursively optimize SVG elements."""
        # Process path elements
        if element.tag == f'{ns_prefix}path' or element.tag == 'path':
            self._optimize_path(element)
        
        # Process groups - check for empty or single-child groups
        if element.tag == f'{ns_prefix}g' or element.tag == 'g':
            # Remove empty groups
            if len(element) == 0 and not element.text:
                parent = element.getparent() if hasattr(element, 'getparent') else None
                if parent is not None:
                    parent.remove(element)
                    return
        
        # Recurse to children
        for child in list(element):
            self._optimize_element(child, ns_prefix)
        
        # Optimize attributes
        self._optimize_attributes(element)
    
    def _optimize_path(self, path_element: ET.Element) -> None:
        """Optimize a path element."""
        d = path_element.get('d', '')
        if not d:
            return
        
        fill = path_element.get('fill', 'black')
        
        # Try to detect primitives
        if self.detect_primitives:
            primitive = path_to_primitive(d, self.primitive_tolerance)
            if primitive:
                elem_type, attrs = primitive
                # Mark for conversion (will be handled in parent)
                path_element.set('_primitive_type', elem_type)
                path_element.set('_primitive_attrs', str(attrs))
                return
        
        # Simplify path if needed
        if self.simplify_paths:
            d = simplify_svg_path(d, self.simplify_epsilon)
        
        # Round coordinates
        d = self._round_path_coords(d)
        
        path_element.set('d', d)
    
    def _round_path_coords(self, d: str) -> str:
        """Round coordinates in path data to specified precision."""
        def round_match(m):
            num = float(m.group(0))
            if num == int(num):
                return str(int(num))
            return f'{num:.{self.path_precision}f}'.rstrip('0').rstrip('.')
        
        return re.sub(r'-?[\d.]+', round_match, d)
    
    def _optimize_attributes(self, element: ET.Element) -> None:
        """Optimize element attributes."""
        # Remove unnecessary attributes
        remove_attrs = ['id', 'class', 'style'] if not self._is_referenced(element) else []
        
        for attr in remove_attrs:
            if attr in element.attrib:
                del element.attrib[attr]
        
        # Optimize colors
        if 'fill' in element.attrib:
            element.set('fill', self._optimize_color(element.get('fill')))
        if 'stroke' in element.attrib:
            element.set('stroke', self._optimize_color(element.get('stroke')))
        
        # Remove stroke="none" if fill is set
        if element.get('stroke') == 'none':
            del element.attrib['stroke']
        
        # Remove fill-opacity and stroke-opacity if 1
        for attr in ['fill-opacity', 'stroke-opacity', 'opacity']:
            if element.get(attr) in ['1', '1.0']:
                del element.attrib[attr]
    
    def _is_referenced(self, element: ET.Element) -> bool:
        """Check if element is referenced elsewhere (e.g., by use or url())."""
        elem_id = element.get('id')
        return elem_id is not None and elem_id.startswith('def')
    
    def _optimize_color(self, color: str) -> str:
        """Optimize color representation."""
        if not color:
            return color
        
        color = color.strip().lower()
        
        # Convert rgb() to hex
        rgb_match = re.match(r'rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', color)
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            color = f'#{r:02x}{g:02x}{b:02x}'
        
        # Shorten 6-char hex to 3-char if possible
        hex_match = re.match(r'#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})', color)
        if hex_match:
            r, g, b = hex_match.groups()
            if r[0] == r[1] and g[0] == g[1] and b[0] == b[1]:
                color = f'#{r[0]}{g[0]}{b[0]}'
        
        # Use named colors where shorter
        color_names = {
            '#000': 'black', '#fff': 'white', '#f00': 'red',
            '#0f0': 'lime', '#00f': 'blue', '#ff0': 'yellow',
            '#0ff': 'cyan', '#f0f': 'magenta'
        }
        if color in color_names:
            color = color_names[color]
        
        return color
    
    def _clean_namespaces(self, svg: str, ns: str) -> str:
        """Clean up namespace declarations in SVG."""
        # Remove redundant namespace prefixes
        if ns:
            svg = re.sub(f'ns\\d+:', '', svg)
            svg = re.sub(f'xmlns:ns\\d+="[^"]*"', '', svg)
        
        # Ensure proper SVG namespace
        if 'xmlns' not in svg:
            svg = svg.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ')
        
        return svg
    
    def _apply_scour(self, svg_content: str) -> str:
        """Apply scour optimization."""
        if not SCOUR_AVAILABLE:
            return svg_content
        
        try:
            # Use scourString for direct string processing
            from scour.scour import scourString
            
            # Scour options for maximum optimization
            options = scour.sanitizeOptions(options={
                'enable_viewboxing': True,
                'strip_ids': True,
                'strip_comments': True,
                'shorten_ids': True,
                'indent_type': 'none',
                'newlines': False,
                'digits': self.path_precision,
                'remove_metadata': True,
                'strip_xml_prolog': False,  # Keep prolog for valid XML
                'remove_titles': True,
                'remove_descriptions': True,
                'remove_descriptive_elements': True,
                'enable_comment_stripping': True,
            })
            
            result = scourString(svg_content, options)
            
            # Remove XML prolog for smaller size
            result = re.sub(r'<\?xml[^?]*\?>\s*', '', result)
            
            return result.strip()
        except Exception as e:
            print(f"Scour optimization failed: {e}")
            return svg_content
    
    def _final_cleanup(self, svg_content: str) -> str:
        """Apply final cleanup without scour."""
        # Remove XML declaration if present
        svg_content = re.sub(r'<\?xml[^?]*\?>\s*', '', svg_content)
        
        # Remove comments
        svg_content = re.sub(r'<!--.*?-->', '', svg_content, flags=re.DOTALL)
        
        # Remove extra whitespace
        svg_content = re.sub(r'\s+', ' ', svg_content)
        svg_content = re.sub(r'>\s+<', '><', svg_content)
        
        # Remove trailing spaces before closing tags
        svg_content = re.sub(r'\s+/>', '/>', svg_content)
        svg_content = re.sub(r'\s+>', '>', svg_content)
        
        return svg_content.strip()
    
    def get_stats(self, original: str, optimized: str) -> Dict[str, Any]:
        """
        Get optimization statistics.
        
        Args:
            original: Original SVG content
            optimized: Optimized SVG content
            
        Returns:
            Statistics dictionary
        """
        original_size = len(original.encode('utf-8'))
        optimized_size = len(optimized.encode('utf-8'))
        
        original_paths = original.count('<path')
        optimized_paths = optimized.count('<path')
        
        return {
            'original_size': original_size,
            'optimized_size': optimized_size,
            'reduction_bytes': original_size - optimized_size,
            'reduction_percent': ((original_size - optimized_size) / original_size * 100) if original_size > 0 else 0,
            'original_paths': original_paths,
            'optimized_paths': optimized_paths,
            'paths_reduced': original_paths - optimized_paths,
        }


# ============================================================================
# FIGMA-OPTIMIZED PRESETS
# ============================================================================

def create_figma_optimizer() -> SVGOptimizer:
    """
    Create an optimizer configured for Figma compatibility.
    
    Returns:
        SVGOptimizer configured for Figma
    """
    return SVGOptimizer(
        simplify_paths=True,
        detect_primitives=True,
        merge_colors=True,
        use_scour=True,
        path_precision=1,  # Aggressive rounding for Figma
        simplify_epsilon=1.5,  # More aggressive simplification
        primitive_tolerance=0.15,  # Detect more primitives
    )


def create_quality_optimizer() -> SVGOptimizer:
    """
    Create an optimizer that prioritizes quality over size.
    
    Returns:
        SVGOptimizer configured for quality
    """
    return SVGOptimizer(
        simplify_paths=True,
        detect_primitives=True,
        merge_colors=True,
        use_scour=True,
        path_precision=2,
        simplify_epsilon=0.5,  # Less aggressive simplification
        primitive_tolerance=0.08,  # Stricter primitive detection
    )


# ============================================================================
# VTRACER PRESETS FOR SMALLER OUTPUT
# ============================================================================

VTRACER_PRESETS = {
    # Figma-optimized: prioritizes small file size and editability
    'figma': {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'spline',
        'filter_speckle': 4,
        'color_precision': 6,
        'layer_difference': 16,
        'corner_threshold': 60,
        'length_threshold': 4.0,
        'max_iterations': 10,
        'splice_threshold': 45,
        'path_precision': 5,
    },
    # Balanced: good quality with reasonable size
    'balanced': {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'spline',
        'filter_speckle': 2,
        'color_precision': 6,
        'layer_difference': 8,
        'corner_threshold': 45,
        'length_threshold': 3.5,
        'max_iterations': 15,
        'splice_threshold': 45,
        'path_precision': 6,
    },
    # Quality: higher fidelity but larger files
    'quality': {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'spline',
        'filter_speckle': 1,
        'color_precision': 8,
        'layer_difference': 4,
        'corner_threshold': 30,
        'length_threshold': 3.0,
        'max_iterations': 20,
        'splice_threshold': 45,
        'path_precision': 8,
    },
    # Ultra: maximum quality (original behavior but still not pixel-perfect)
    'ultra': {
        'colormode': 'color',
        'hierarchical': 'stacked',
        'mode': 'polygon',
        'filter_speckle': 0,
        'color_precision': 8,
        'layer_difference': 1,
        'corner_threshold': 10,
        'length_threshold': 3.5,
        'max_iterations': 30,
        'path_precision': 8,
    },
}


def get_vtracer_preset(name: str) -> Dict:
    """
    Get vtracer settings for a named preset.
    
    Args:
        name: Preset name ('figma', 'balanced', 'quality', 'ultra')
        
    Returns:
        Dictionary of vtracer settings
    """
    return VTRACER_PRESETS.get(name, VTRACER_PRESETS['balanced'])


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def optimize_svg_file(input_path: str, output_path: Optional[str] = None, 
                      preset: str = 'figma') -> Tuple[str, Dict]:
    """
    Optimize an SVG file with a named preset.
    
    Args:
        input_path: Path to input SVG
        output_path: Path for output (defaults to input_path with _optimized suffix)
        preset: Preset name ('figma' or 'quality')
        
    Returns:
        Tuple of (output_path, stats_dict)
    """
    if output_path is None:
        path = Path(input_path)
        output_path = str(path.parent / f"{path.stem}_optimized{path.suffix}")
    
    if preset == 'figma':
        optimizer = create_figma_optimizer()
    else:
        optimizer = create_quality_optimizer()
    
    # Read original
    with open(input_path, 'r', encoding='utf-8') as f:
        original = f.read()
    
    # Optimize
    optimized = optimizer.optimize_string(original)
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(optimized)
    
    # Get stats
    stats = optimizer.get_stats(original, optimized)
    
    return output_path, stats


def optimize_svg_string(svg_content: str, preset: str = 'figma') -> Tuple[str, Dict]:
    """
    Optimize SVG content string.
    
    Args:
        svg_content: SVG content as string
        preset: Preset name ('figma' or 'quality')
        
    Returns:
        Tuple of (optimized_svg, stats_dict)
    """
    if preset == 'figma':
        optimizer = create_figma_optimizer()
    else:
        optimizer = create_quality_optimizer()
    
    optimized = optimizer.optimize_string(svg_content)
    stats = optimizer.get_stats(svg_content, optimized)
    
    return optimized, stats
