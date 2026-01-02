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
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    name: str

    def intersects_box(self, box: BBox, eps: float = 1.0) -> bool:
        """Check if line segment passes through box interior."""
        # Quick bounding box check
        line_x_min, line_x_max = min(self.x1, self.x2), max(self.x1, self.x2)
        line_y_min, line_y_max = min(self.y1, self.y2), max(self.y1, self.y2)

        if line_x_max < box.x_min or line_x_min > box.x_max:
            return False
        if line_y_max < box.y_min or line_y_min > box.y_max:
            return False

        # Check if line endpoints are both outside on same side
        if self.x1 < box.x_min and self.x2 < box.x_min:
            return False
        if self.x1 > box.x_max and self.x2 > box.x_max:
            return False
        if self.y1 < box.y_min and self.y2 < box.y_min:
            return False
        if self.y1 > box.y_max and self.y2 > box.y_max:
            return False

        # Line passes through or near the box
        return True


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


def extract_elements(svg_path: str) -> tuple:
    """Extract all elements from SVG file."""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # Handle SVG namespace
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    if root.tag.startswith('{'):
        ns_uri = root.tag[1:root.tag.index('}')]
        ns = {'svg': ns_uri}

    texts = []
    rects = []
    lines = []
    polygons = []

    elem_counter = 0

    def get_name(elem):
        nonlocal elem_counter
        elem_counter += 1
        return elem.get('id') or f"elem_{elem_counter}"

    # Find all elements (handle namespace)
    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        name = get_name(elem)

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
            line = Line(x1, y1, x2, y2, name)
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
                path_segments = parse_path_to_lines(d)
                for idx, (x1, y1, x2, y2) in enumerate(path_segments):
                    segment_name = f"{name}_seg{idx}" if len(path_segments) > 1 else name
                    line = Line(x1, y1, x2, y2, segment_name)
                    lines.append(line)

    return texts, rects, lines, polygons


def check_collisions(texts, rects, lines, polygons) -> list:
    """Check all collision rules."""
    issues = []

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

    return issues


def check_file(svg_path: str) -> dict:
    """Check a single SVG file for collisions."""
    texts, rects, lines, polygons = extract_elements(svg_path)
    issues = check_collisions(texts, rects, lines, polygons)

    return {
        'file': os.path.basename(svg_path),
        'texts': len(texts),
        'rects': len(rects),
        'lines': len(lines),
        'polygons': len(polygons),
        'issues': issues
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

    for filepath in files:
        result = check_file(filepath)
        issues = result['issues']
        issue_count = len(issues)
        total_issues += issue_count

        status = "OK" if issue_count == 0 else f"ISSUES ({issue_count})"
        counts = f"{result['texts']}t/{result['rects']}r/{result['lines']}l" if verbose else ""
        print(f"\n{result['file']} {counts}: {status}")

        for issue_type, elem1, elem2 in issues:
            print(f"  - {issue_type.upper()}: {elem1} / {elem2}")

    print("\n" + "=" * 60)
    if total_issues == 0:
        print("Result: No issues detected")
    else:
        print(f"Result: {total_issues} issue(s) found")

    return 1 if total_issues > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
