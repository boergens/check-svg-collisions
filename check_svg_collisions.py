#!/usr/bin/env python3
"""
SVG Collision Checker - Detects problematic element interactions in SVG figures.

Collision rules:
1. Text ↔ Text: No overlap
2. Text ↔ Line: Line must not pass through text
3. Rect ↔ Rect: No overlap unless one fully contains the other
"""

import sys
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from measure_text import measure_text_bbox


@dataclass
class BBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    name: str
    elem_type: str  # 'text', 'rect', 'line', 'polygon'

    def overlaps(self, other: 'BBox', eps: float = 0.5) -> bool:
        if self.x_max <= other.x_min + eps or other.x_max <= self.x_min + eps:
            return False
        if self.y_max <= other.y_min + eps or other.y_max <= self.y_min + eps:
            return False
        return True

    def contains(self, other: 'BBox') -> bool:
        return (self.x_min <= other.x_min and self.x_max >= other.x_max and
                self.y_min <= other.y_min and self.y_max >= other.y_max)

    @property
    def width(self):
        return self.x_max - self.x_min

    @property
    def height(self):
        return self.y_max - self.y_min


@dataclass
class Marker:
    id: str
    width: float
    height: float
    ref_x: float
    ref_y: float


@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    name: str
    marker_end_id: str = None

    def _point_at_box_edge(self, px: float, py: float, box: BBox, eps: float = 5.0) -> bool:
        """Check if point is at box edge (not deep inside)."""
        in_x = box.x_min - eps <= px <= box.x_max + eps
        in_y = box.y_min - eps <= py <= box.y_max + eps
        if not (in_x and in_y):
            return False
        # Must be near an edge, not deep inside
        near_left = abs(px - box.x_min) <= eps
        near_right = abs(px - box.x_max) <= eps
        near_top = abs(py - box.y_min) <= eps
        near_bottom = abs(py - box.y_max) <= eps
        return near_left or near_right or near_top or near_bottom

    def _segments_intersect(self, ax1, ay1, ax2, ay2, bx1, by1, bx2, by2) -> bool:
        """Check if two line segments intersect using cross products."""
        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        p1, p2 = (ax1, ay1), (ax2, ay2)
        p3, p4 = (bx1, by1), (bx2, by2)

        d1 = cross(p3, p4, p1)
        d2 = cross(p3, p4, p2)
        d3 = cross(p1, p2, p3)
        d4 = cross(p1, p2, p4)

        if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
           ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
            return True
        return False

    def _point_in_box(self, px, py, box: BBox, eps: float = 0.5) -> bool:
        """Check if point is strictly inside box (not on edge)."""
        return (box.x_min + eps < px < box.x_max - eps and
                box.y_min + eps < py < box.y_max - eps)

    def intersects_box(self, box: BBox, eps: float = 1.0) -> bool:
        """Check if line segment actually intersects box (not just bounding box overlap)."""
        # Quick bounding box rejection
        line_x_min, line_x_max = min(self.x1, self.x2), max(self.x1, self.x2)
        line_y_min, line_y_max = min(self.y1, self.y2), max(self.y1, self.y2)

        if line_x_max < box.x_min - eps or line_x_min > box.x_max + eps:
            return False
        if line_y_max < box.y_min - eps or line_y_min > box.y_max + eps:
            return False

        # Check if either endpoint is inside the box
        if self._point_in_box(self.x1, self.y1, box):
            return True
        if self._point_in_box(self.x2, self.y2, box):
            return True

        # Check intersection with each of the 4 box edges
        edges = [
            (box.x_min, box.y_min, box.x_max, box.y_min),  # top
            (box.x_max, box.y_min, box.x_max, box.y_max),  # right
            (box.x_min, box.y_max, box.x_max, box.y_max),  # bottom
            (box.x_min, box.y_min, box.x_min, box.y_max),  # left
        ]
        for ex1, ey1, ex2, ey2 in edges:
            if self._segments_intersect(self.x1, self.y1, self.x2, self.y2,
                                        ex1, ey1, ex2, ey2):
                return True
        return False

    def _touches_corner(self, box: BBox, eps: float = 2.0) -> bool:
        """Check if line touches a box corner without passing through."""
        corners = [
            (box.x_min, box.y_min), (box.x_max, box.y_min),
            (box.x_min, box.y_max), (box.x_max, box.y_max),
        ]
        for cx, cy in corners:
            # Check if corner is on the line segment
            # Use parametric form: point = p1 + t*(p2-p1), 0 <= t <= 1
            dx, dy = self.x2 - self.x1, self.y2 - self.y1
            if abs(dx) < 0.001 and abs(dy) < 0.001:
                continue
            if abs(dx) > abs(dy):
                t = (cx - self.x1) / dx
                if 0 <= t <= 1:
                    y_on_line = self.y1 + t * dy
                    if abs(y_on_line - cy) < eps:
                        return True
            else:
                t = (cy - self.y1) / dy
                if 0 <= t <= 1:
                    x_on_line = self.x1 + t * dx
                    if abs(x_on_line - cx) < eps:
                        return True
        return False

    def passes_through_box(self, box: BBox) -> bool:
        """Check if line passes through box (not just connects to it)."""
        if not self.intersects_box(box):
            return False
        # If either endpoint is at box edge, it's a connection, not a pass-through
        if self._point_at_box_edge(self.x1, self.y1, box):
            return False
        if self._point_at_box_edge(self.x2, self.y2, box):
            return False
        return True

    def touches_box_corner(self, box: BBox) -> bool:
        """Check if line touches box corner (warning, not error)."""
        if self.passes_through_box(box):
            return False  # It's a pass-through, not just a touch
        return self._touches_corner(box)


def parse_points(points_str: str) -> list:
    """Parse SVG points attribute into list of (x, y) tuples."""
    points = []
    parts = points_str.replace(',', ' ').split()
    for i in range(0, len(parts) - 1, 2):
        points.append((float(parts[i]), float(parts[i + 1])))
    return points


def parse_path_to_lines(d: str) -> list:
    """Parse SVG path d attribute and return list of (x1, y1, x2, y2) line segments."""
    lines = []

    # Tokenize: split into commands and numbers
    tokens = re.findall(r'[MmLlHhVvZzCcSsQqTtAa]|[-+]?[0-9]*\.?[0-9]+', d)

    i = 0
    current_x, current_y = 0.0, 0.0
    start_x, start_y = 0.0, 0.0  # For Z command

    while i < len(tokens):
        cmd = tokens[i]
        i += 1

        if cmd in 'Mm':
            # MoveTo
            if i + 1 < len(tokens):
                x, y = float(tokens[i]), float(tokens[i + 1])
                i += 2
                if cmd == 'm':  # relative
                    current_x += x
                    current_y += y
                else:
                    current_x, current_y = x, y
                start_x, start_y = current_x, current_y

        elif cmd in 'Ll':
            # LineTo
            if i + 1 < len(tokens):
                x, y = float(tokens[i]), float(tokens[i + 1])
                i += 2
                prev_x, prev_y = current_x, current_y
                if cmd == 'l':  # relative
                    current_x += x
                    current_y += y
                else:
                    current_x, current_y = x, y
                lines.append((prev_x, prev_y, current_x, current_y))

        elif cmd in 'Hh':
            # Horizontal LineTo
            if i < len(tokens):
                x = float(tokens[i])
                i += 1
                prev_x = current_x
                if cmd == 'h':  # relative
                    current_x += x
                else:
                    current_x = x
                lines.append((prev_x, current_y, current_x, current_y))

        elif cmd in 'Vv':
            # Vertical LineTo
            if i < len(tokens):
                y = float(tokens[i])
                i += 1
                prev_y = current_y
                if cmd == 'v':  # relative
                    current_y += y
                else:
                    current_y = y
                lines.append((current_x, prev_y, current_x, current_y))

        elif cmd in 'Zz':
            # ClosePath - line back to start
            if current_x != start_x or current_y != start_y:
                lines.append((current_x, current_y, start_x, start_y))
            current_x, current_y = start_x, start_y

        elif cmd in 'Cc':
            # Cubic Bezier - approximate with line from current to endpoint
            if i + 5 < len(tokens):
                # Skip control points, just get endpoint
                if cmd == 'c':
                    end_x = current_x + float(tokens[i + 4])
                    end_y = current_y + float(tokens[i + 5])
                else:
                    end_x = float(tokens[i + 4])
                    end_y = float(tokens[i + 5])
                i += 6
                lines.append((current_x, current_y, end_x, end_y))
                current_x, current_y = end_x, end_y

        elif cmd in 'Ss':
            # Smooth cubic Bezier
            if i + 3 < len(tokens):
                if cmd == 's':
                    end_x = current_x + float(tokens[i + 2])
                    end_y = current_y + float(tokens[i + 3])
                else:
                    end_x = float(tokens[i + 2])
                    end_y = float(tokens[i + 3])
                i += 4
                lines.append((current_x, current_y, end_x, end_y))
                current_x, current_y = end_x, end_y

        elif cmd in 'Qq':
            # Quadratic Bezier
            if i + 3 < len(tokens):
                if cmd == 'q':
                    end_x = current_x + float(tokens[i + 2])
                    end_y = current_y + float(tokens[i + 3])
                else:
                    end_x = float(tokens[i + 2])
                    end_y = float(tokens[i + 3])
                i += 4
                lines.append((current_x, current_y, end_x, end_y))
                current_x, current_y = end_x, end_y

        elif cmd in 'Tt':
            # Smooth quadratic Bezier
            if i + 1 < len(tokens):
                if cmd == 't':
                    end_x = current_x + float(tokens[i])
                    end_y = current_y + float(tokens[i + 1])
                else:
                    end_x = float(tokens[i])
                    end_y = float(tokens[i + 1])
                i += 2
                lines.append((current_x, current_y, end_x, end_y))
                current_x, current_y = end_x, end_y

        elif cmd in 'Aa':
            # Arc - approximate with line to endpoint
            if i + 6 < len(tokens):
                if cmd == 'a':
                    end_x = current_x + float(tokens[i + 5])
                    end_y = current_y + float(tokens[i + 6])
                else:
                    end_x = float(tokens[i + 5])
                    end_y = float(tokens[i + 6])
                i += 7
                lines.append((current_x, current_y, end_x, end_y))
                current_x, current_y = end_x, end_y
        else:
            # Unknown command or number without command (implicit LineTo after M)
            # Try to parse as implicit lineto
            try:
                x = float(cmd)
                if i < len(tokens):
                    y = float(tokens[i])
                    i += 1
                    prev_x, prev_y = current_x, current_y
                    current_x, current_y = x, y
                    lines.append((prev_x, prev_y, current_x, current_y))
            except ValueError:
                pass

    return lines


def find_element_line_numbers(svg_path: str) -> dict:
    """Pre-scan SVG to map element tags to line numbers."""
    line_map = {}  # (tag, occurrence_index) -> line_number
    tag_counts = {}

    with open(svg_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            # Find element tags in this line
            for match in re.finditer(r'<(\w+)(?:\s|>|/)', line):
                tag = match.group(1)
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                line_map[(tag, tag_counts[tag])] = line_num

    return line_map


def extract_elements(svg_path: str, warn_missing_ids: bool = True) -> tuple:
    """Extract all elements from SVG file."""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # Pre-scan for line numbers
    line_map = find_element_line_numbers(svg_path)
    tag_counts = {}  # Track which occurrence of each tag we're on

    # Handle SVG namespace
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    if root.tag.startswith('{'):
        ns_uri = root.tag[1:root.tag.index('}')]
        ns = {'svg': ns_uri}

    texts = []
    rects = []
    lines = []
    polygons = []
    missing_id_warnings = []

    elem_counter = 0

    def get_name(elem, tag, skip_warning=False):
        nonlocal elem_counter
        elem_counter += 1

        # Track tag occurrence for line number lookup
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        line_num = line_map.get((tag, tag_counts[tag]), '?')

        if elem.get('id'):
            return elem.get('id')
        else:
            temp_name = f"elem_{elem_counter}"
            if warn_missing_ids and not skip_warning and tag in ('rect', 'line', 'path', 'polygon', 'polyline', 'text'):
                missing_id_warnings.append(
                    f"  <{tag}> at line {line_num} has no id, temporarily named '{temp_name}'"
                )
            return temp_name

    # Build set of elements inside <defs> (these don't need IDs)
    # Also parse marker definitions for later use
    defs_elements = set()
    markers = {}  # id -> Marker
    for defs in root.iter():
        defs_tag = defs.tag.split('}')[-1] if '}' in defs.tag else defs.tag
        if defs_tag == 'defs':
            for child in defs.iter():
                defs_elements.add(child)
                child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if child_tag == 'marker':
                    marker_id = child.get('id')
                    if marker_id:
                        markers[marker_id] = Marker(
                            id=marker_id,
                            width=float(child.get('markerWidth', 10)),
                            height=float(child.get('markerHeight', 7)),
                            ref_x=float(child.get('refX', 0)),
                            ref_y=float(child.get('refY', 0)),
                        )

    # Find all elements (handle namespace)
    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        in_defs = elem in defs_elements
        name = get_name(elem, tag, skip_warning=in_defs)

        # Skip elements inside <defs> - they're definitions (markers, patterns, etc.)
        if in_defs:
            continue

        if tag == 'text':
            x = float(elem.get('x', 0))
            y = float(elem.get('y', 0))
            text_content = elem.text or ''

            # Get font properties
            font_family = elem.get('font-family', 'sans-serif')
            font_size = 12.0
            fs_attr = elem.get('font-size', '12')
            if fs_attr:
                fs_match = re.match(r'([0-9.]+)', fs_attr)
                if fs_match:
                    font_size = float(fs_match.group(1))

            # Get text anchor
            anchor = elem.get('text-anchor', 'start')

            # Measure actual text dimensions using Cairo
            x_min, y_min, x_max, y_max = measure_text_bbox(
                text_content, x, y, font_family, font_size, anchor
            )

            bbox = BBox(x_min, y_min, x_max, y_max, text_content[:20] or name, 'text')
            texts.append(bbox)

        elif tag == 'rect':
            x = float(elem.get('x', 0))
            y = float(elem.get('y', 0))
            w = float(elem.get('width', 0))
            h = float(elem.get('height', 0))
            bbox = BBox(x, y, x + w, y + h, name, 'rect')
            rects.append(bbox)

        elif tag == 'line':
            x1 = float(elem.get('x1', 0))
            y1 = float(elem.get('y1', 0))
            x2 = float(elem.get('x2', 0))
            y2 = float(elem.get('y2', 0))
            # Check for marker-end reference
            marker_end_id = None
            marker_end = elem.get('marker-end', '')
            if marker_end.startswith('url(#') and marker_end.endswith(')'):
                marker_end_id = marker_end[5:-1]
            line = Line(x1, y1, x2, y2, name, marker_end_id)
            lines.append(line)

        elif tag == 'polygon' or tag == 'polyline':
            points_str = elem.get('points', '')
            if points_str:
                points = parse_points(points_str)
                if points:
                    xs = [p[0] for p in points]
                    ys = [p[1] for p in points]
                    bbox = BBox(min(xs), min(ys), max(xs), max(ys), name, 'polygon')
                    polygons.append(bbox)

        elif tag == 'path':
            d = elem.get('d', '')
            if d:
                # Check for marker-end reference
                marker_end_id = None
                marker_end = elem.get('marker-end', '')
                if marker_end.startswith('url(#') and marker_end.endswith(')'):
                    marker_end_id = marker_end[5:-1]
                path_segments = parse_path_to_lines(d)
                for idx, (x1, y1, x2, y2) in enumerate(path_segments):
                    segment_name = f"{name}_seg{idx}" if len(path_segments) > 1 else name
                    # Only the last segment gets the marker-end
                    seg_marker = marker_end_id if idx == len(path_segments) - 1 else None
                    line = Line(x1, y1, x2, y2, segment_name, seg_marker)
                    lines.append(line)

    # Create bounding boxes for rendered markers at line endpoints
    # Keep markers separate - they need special collision handling
    rendered_markers = []  # list of (owner_line_name, BBox)
    for line in lines:
        if line.marker_end_id and line.marker_end_id in markers:
            marker = markers[line.marker_end_id]
            # Marker is rendered at line endpoint (x2, y2)
            # The refX, refY point aligns with the endpoint
            # Create a bbox centered around the endpoint with marker dimensions
            x2, y2 = line.x2, line.y2
            # Simplified: create a box around the endpoint with marker size
            # Offset by ref point (marker's reference point aligns with endpoint)
            half_w = marker.width / 2
            half_h = marker.height / 2
            bbox = BBox(
                x2 - half_w, y2 - half_h,
                x2 + half_w, y2 + half_h,
                f"{line.name}:marker",
                'marker'
            )
            rendered_markers.append((line.name, bbox))

    return texts, rects, lines, polygons, rendered_markers, missing_id_warnings


def check_collisions(texts, rects, lines, polygons, rendered_markers=None) -> tuple:
    """Check all collision rules. Returns (issues, warnings)."""
    issues = []
    warnings = []

    if rendered_markers is None:
        rendered_markers = []

    # Combine rects and polygons as "boxes"
    boxes = rects + polygons

    # Rule 1: Text ↔ Text - no overlap
    for i, t1 in enumerate(texts):
        for t2 in texts[i + 1:]:
            if t1.overlaps(t2):
                issues.append(("text overlap", t1.name, t2.name))

    # Rule 2: Text ↔ Line - line must not pass through text
    for line in lines:
        for text in texts:
            if line.intersects_box(text):
                issues.append(("line through text", line.name, text.name))

    # Rule 3: Text ↔ Box - text should not CROSS box borders
    # (text fully inside or fully outside is OK)
    for text in texts:
        for box in boxes:
            if text.overlaps(box):
                # OK if box contains text (text is inside)
                if box.contains(text):
                    continue
                # OK if text contains box (box is inside text - rare but valid)
                if text.contains(box):
                    continue
                # Not OK: text crosses the border
                issues.append(("text crosses box", text.name, box.name))

    # Rule 4: Box ↔ Box - no overlap unless containment
    for i, b1 in enumerate(boxes):
        for b2 in boxes[i + 1:]:
            if b1.overlaps(b2):
                if not (b1.contains(b2) or b2.contains(b1)):
                    issues.append(("box overlap", b1.name, b2.name))

    # Rule 5: Line ↔ Box - line must not pass through box (connecting to box is OK)
    # Corner touches are warnings, not errors
    for line in lines:
        for box in boxes:
            if line.passes_through_box(box):
                issues.append(("line through box", line.name, box.name))
            elif line.touches_box_corner(box):
                warnings.append(("line touches corner", line.name, box.name))

    # Rule 6: Line ↔ Marker - lines must not pass through rendered markers
    # (except for the line that owns the marker)
    for owner_name, marker_box in rendered_markers:
        for line in lines:
            # Skip if this line owns the marker
            if line.name == owner_name or line.name.startswith(owner_name + "_seg"):
                continue
            if line.passes_through_box(marker_box):
                issues.append(("line through marker", line.name, marker_box.name))
            elif line.touches_box_corner(marker_box):
                warnings.append(("line touches marker corner", line.name, marker_box.name))

    return issues, warnings


def check_file(svg_path: str) -> dict:
    """Check a single SVG file for collisions."""
    texts, rects, lines, polygons, rendered_markers, missing_ids = extract_elements(svg_path)
    issues, warnings = check_collisions(texts, rects, lines, polygons, rendered_markers)

    return {
        'file': os.path.basename(svg_path),
        'texts': len(texts),
        'rects': len(rects),
        'lines': len(lines),
        'polygons': len(polygons),
        'issues': issues,
        'warnings': warnings,
        'missing_ids': missing_ids
    }


def main():
    verbose = False
    files = []

    for arg in sys.argv[1:]:
        if arg in ['-h', '--help']:
            print("Usage: check_svg_collisions.py [-v] file.svg [file2.svg ...]")
            print("\nChecks SVG figures for problematic element interactions:")
            print("  1. Text overlapping text")
            print("  2. Lines passing through text")
            print("  3. Boxes overlapping (without containment)")
            print("\n  -v, --verbose  Show element counts")
            return 0
        elif arg in ['-v', '--verbose']:
            verbose = True
        else:
            files.append(arg)

    if not files:
        # Default: check all SVGs in figures directory
        figures_dir = os.path.join(os.path.dirname(__file__), 'figures')
        if os.path.isdir(figures_dir):
            files = [os.path.join(figures_dir, f) for f in os.listdir(figures_dir) if f.endswith('.svg')]
            files.sort()

    if not files:
        print("No SVG files found")
        return 1

    print("Checking SVG files for collisions\n")
    print("=" * 60)

    total_issues = 0
    total_warnings = 0

    total_missing_ids = 0

    for filepath in files:
        result = check_file(filepath)
        issues = result['issues']
        warnings = result['warnings']
        missing_ids = result['missing_ids']
        issue_count = len(issues)
        warning_count = len(warnings)
        missing_id_count = len(missing_ids)
        total_issues += issue_count
        total_warnings += warning_count
        total_missing_ids += missing_id_count

        if issue_count > 0:
            status = f"ISSUES ({issue_count})"
        elif warning_count > 0:
            status = f"WARNINGS ({warning_count})"
        else:
            status = "OK"
        if missing_id_count > 0:
            status += f" [MISSING IDs: {missing_id_count}]"
        counts = f"{result['texts']}t/{result['rects']}r/{result['lines']}l" if verbose else ""
        print(f"\n{result['file']} {counts}: {status}")

        for issue_type, elem1, elem2 in issues:
            print(f"  - {issue_type.upper()}: {elem1} / {elem2}")
        for warn_type, elem1, elem2 in warnings:
            print(f"  - WARNING {warn_type}: {elem1} / {elem2}")
        for msg in missing_ids:
            print(msg)

    print("\n" + "=" * 60)
    if total_issues == 0 and total_warnings == 0 and total_missing_ids == 0:
        print("Result: No issues detected")
    else:
        parts = []
        if total_issues > 0:
            parts.append(f"{total_issues} issue(s)")
        if total_warnings > 0:
            parts.append(f"{total_warnings} warning(s)")
        if total_missing_ids > 0:
            parts.append(f"{total_missing_ids} missing ID(s)")
        print(f"Result: {', '.join(parts)}")

    return 1 if total_issues > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
