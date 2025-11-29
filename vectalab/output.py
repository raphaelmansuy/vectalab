import svgwrite

class SVGWriter:
    def __init__(self):
        pass

    def save(self, paths, output_path, size):
        """
        Saves paths to an SVG file.
        paths: list of {'path': <potrace path>, 'color': (r, g, b)}
        size: (height, width)
        """
        height, width = size
        dwg = svgwrite.Drawing(output_path, size=(width, height), profile='tiny')

        for item in paths:
            path_obj = item['path']
            color = item['color']
            rgb_str = f"rgb({color[0]},{color[1]},{color[2]})"
            
            # Convert potrace path to SVG path data
            # Potrace path consists of curves.
            # We need to iterate over curves and generate 'd' attribute.
            
            for curve in path_obj:
                d = []
                start = curve.start_point
                d.append(f"M {start.x} {start.y}")
                
                for segment in curve:
                    if segment.is_corner:
                        c = segment.c
                        end = segment.end_point
                        d.append(f"L {c.x} {c.y} L {end.x} {end.y}")
                    else:
                        c1 = segment.c1
                        c2 = segment.c2
                        end = segment.end_point
                        d.append(f"C {c1.x} {c1.y} {c2.x} {c2.y} {end.x} {end.y}")
                
                d.append("Z") # Close path
                
                dwg.add(dwg.path(d=" ".join(d), fill=rgb_str, stroke="none"))

        dwg.save()

    def save_bezier(self, paths, output_path, size):
        """
        Saves bezier paths to an SVG file.
        paths: list of {'type': 'bezier', 'data': [(C, p0, c1, c2, p1), ...], 'color': (r, g, b)}
        size: (height, width)
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
            rgb_str = f"rgb({color[0]},{color[1]},{color[2]})"
            
            d = []
            # Start point of the first segment
            if not item['data']:
                continue
                
            first_seg = item['data'][0]
            # Format: ('C', p0, c1, c2, p1)
            p0 = first_seg[1]
            d.append(f"M {p0[0]} {p0[1]}")
            
            for seg in item['data']:
                # Cubic Bezier: C x1 y1, x2 y2, x y
                c1 = seg[2]
                c2 = seg[3]
                p1 = seg[4]
                d.append(f"C {c1[0]} {c1[1]} {c2[0]} {c2[1]} {p1[0]} {p1[1]}")
            
            # Close path? Maybe not for open strokes, but for shapes we usually close.
            # For now, let's assume they are closed shapes if we want to fill them.
            # But our renderer treats them as strokes or filled shapes? 
            # The renderer uses `sigmoid(color)` so it's a filled shape opacity.
            d.append("Z")
            
            dwg.add(dwg.path(d=" ".join(d), fill=rgb_str, stroke="none", opacity=0.8))

        dwg.save()
