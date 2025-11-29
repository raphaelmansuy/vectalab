import svgwrite
from typing import List, Dict, Any, Optional, Tuple

# Try to import optimizer
try:
    from .optimize import SVGOptimizer, optimize_svg_string
    OPTIMIZER_AVAILABLE = True
except ImportError:
    OPTIMIZER_AVAILABLE = False


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB to hex color, using short form if possible."""
    hex_color = f"#{r:02x}{g:02x}{b:02x}"
    # Use short form if possible
    if hex_color[1] == hex_color[2] and hex_color[3] == hex_color[4] and hex_color[5] == hex_color[6]:
        hex_color = f"#{hex_color[1]}{hex_color[3]}{hex_color[5]}"
    return hex_color


class SVGWriter:
    def __init__(self, optimize: bool = True, precision: int = 2):
        """
        Initialize SVG writer.
        
        Args:
            optimize: Apply post-processing optimization
            precision: Decimal precision for coordinates
        """
        self.optimize = optimize and OPTIMIZER_AVAILABLE
        self.precision = precision

    def save(self, paths, output_path, size, optimize: bool = None):
        """
        Saves paths to an SVG file.
        
        Args:
            paths: list of {'path': <potrace path>, 'color': (r, g, b)}
            output_path: Path for output SVG
            size: (height, width)
            optimize: Override default optimization setting
        """
        height, width = size
        dwg = svgwrite.Drawing(output_path, size=(width, height), profile='tiny')
        dwg.viewbox(0, 0, width, height)

        for item in paths:
            path_obj = item['path']
            color = item['color']
            # Use hex color for smaller file size
            rgb_str = rgb_to_hex(color[0], color[1], color[2])
            
            # Convert potrace path to SVG path data
            for curve in path_obj:
                d = []
                start = curve.start_point
                d.append(f"M{start.x:.{self.precision}f} {start.y:.{self.precision}f}")
                
                for segment in curve:
                    if segment.is_corner:
                        c = segment.c
                        end = segment.end_point
                        d.append(f"L{c.x:.{self.precision}f} {c.y:.{self.precision}f}")
                        d.append(f"L{end.x:.{self.precision}f} {end.y:.{self.precision}f}")
                    else:
                        c1 = segment.c1
                        c2 = segment.c2
                        end = segment.end_point
                        d.append(f"C{c1.x:.{self.precision}f} {c1.y:.{self.precision}f} "
                                f"{c2.x:.{self.precision}f} {c2.y:.{self.precision}f} "
                                f"{end.x:.{self.precision}f} {end.y:.{self.precision}f}")
                
                d.append("Z")  # Close path
                
                dwg.add(dwg.path(d=" ".join(d), fill=rgb_str))

        dwg.save()
        
        # Apply optimization if enabled
        should_optimize = optimize if optimize is not None else self.optimize
        if should_optimize and OPTIMIZER_AVAILABLE:
            self._optimize_file(output_path)
    
    def _optimize_file(self, svg_path: str) -> None:
        """Apply optimization to saved SVG file."""
        with open(svg_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        optimized, _ = optimize_svg_string(content, preset='figma')
        
        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(optimized)

    def save_bezier(self, paths, output_path, size, optimize: bool = None):
        """
        Saves bezier paths to an SVG file.
        
        Args:
            paths: list of {'type': 'bezier', 'data': [(C, p0, c1, c2, p1), ...], 'color': (r, g, b)}
            output_path: Path for output SVG
            size: (height, width)
            optimize: Override default optimization setting
        """
        height, width = size
        dwg = svgwrite.Drawing(output_path, size=(width, height), profile='tiny')
        dwg.viewbox(0, 0, width, height)
        
        # Add white background
        dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill='white'))

        for item in paths:
            if item['type'] != 'bezier':
                continue
                
            color = item['color']
            rgb_str = rgb_to_hex(int(color[0]), int(color[1]), int(color[2]))
            
            d = []
            if not item['data']:
                continue
                
            first_seg = item['data'][0]
            # Format: ('C', p0, c1, c2, p1)
            p0 = first_seg[1]
            d.append(f"M{p0[0]:.{self.precision}f} {p0[1]:.{self.precision}f}")
            
            for seg in item['data']:
                # Cubic Bezier: C x1 y1, x2 y2, x y
                c1 = seg[2]
                c2 = seg[3]
                p1 = seg[4]
                d.append(f"C{c1[0]:.{self.precision}f} {c1[1]:.{self.precision}f} "
                        f"{c2[0]:.{self.precision}f} {c2[1]:.{self.precision}f} "
                        f"{p1[0]:.{self.precision}f} {p1[1]:.{self.precision}f}")
            
            d.append("Z")
            
            # Reduced opacity and no stroke for cleaner output
            dwg.add(dwg.path(d=" ".join(d), fill=rgb_str, opacity=0.8))

        dwg.save()
        
        # Apply optimization if enabled
        should_optimize = optimize if optimize is not None else self.optimize
        if should_optimize and OPTIMIZER_AVAILABLE:
            self._optimize_file(output_path)

    def save_optimized(self, elements: List[Dict], output_path: str, 
                       size: Tuple[int, int], background: str = None) -> Dict:
        """
        Save SVG with full optimization pipeline.
        
        Args:
            elements: List of SVG element dictionaries with 'type' and attributes
            output_path: Path for output SVG
            size: (width, height)
            background: Optional background color
            
        Returns:
            Statistics dictionary
        """
        width, height = size
        
        # Build SVG content
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        ]
        
        if background:
            svg_parts.append(f'<rect width="{width}" height="{height}" fill="{background}"/>')
        
        for elem in elements:
            elem_type = elem.get('type', 'path')
            
            if elem_type == 'path':
                d = elem.get('d', '')
                fill = elem.get('fill', 'black')
                svg_parts.append(f'<path d="{d}" fill="{fill}"/>')
            
            elif elem_type == 'circle':
                svg_parts.append(
                    f'<circle cx="{elem["cx"]:.{self.precision}f}" '
                    f'cy="{elem["cy"]:.{self.precision}f}" '
                    f'r="{elem["r"]:.{self.precision}f}" '
                    f'fill="{elem.get("fill", "black")}"/>'
                )
            
            elif elem_type == 'rect':
                svg_parts.append(
                    f'<rect x="{elem["x"]:.{self.precision}f}" '
                    f'y="{elem["y"]:.{self.precision}f}" '
                    f'width="{elem["width"]:.{self.precision}f}" '
                    f'height="{elem["height"]:.{self.precision}f}" '
                    f'fill="{elem.get("fill", "black")}"/>'
                )
            
            elif elem_type == 'ellipse':
                svg_parts.append(
                    f'<ellipse cx="{elem["cx"]:.{self.precision}f}" '
                    f'cy="{elem["cy"]:.{self.precision}f}" '
                    f'rx="{elem["rx"]:.{self.precision}f}" '
                    f'ry="{elem["ry"]:.{self.precision}f}" '
                    f'fill="{elem.get("fill", "black")}"/>'
                )
        
        svg_parts.append('</svg>')
        svg_content = ''.join(svg_parts)
        
        # Optimize
        if self.optimize and OPTIMIZER_AVAILABLE:
            optimized, stats = optimize_svg_string(svg_content, preset='figma')
        else:
            optimized = svg_content
            stats = {'reduction_percent': 0}
        
        # Write output
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(optimized)
        
        return stats
