#!/usr/bin/env python3
"""SVG parsing and element extraction."""

import math
import re
import xml.etree.ElementTree as ET

from geometry import BBox, Marker, Line
from measure_text import measure_text_bbox


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
    tokens = re.findall(r'[MmLlHhVvZzCcSsQqTtAa]|[-+]?[0-9]*\.?[0-9]+', d)

    i = 0
    current_x, current_y = 0.0, 0.0
    start_x, start_y = 0.0, 0.0

    while i < len(tokens):
        cmd = tokens[i]
        i += 1

        if cmd in 'Mm':
            if i + 1 < len(tokens):
                x, y = float(tokens[i]), float(tokens[i + 1])
                i += 2
                if cmd == 'm':
                    current_x += x
                    current_y += y
                else:
                    current_x, current_y = x, y
                start_x, start_y = current_x, current_y

        elif cmd in 'Ll':
            if i + 1 < len(tokens):
                x, y = float(tokens[i]), float(tokens[i + 1])
                i += 2
                prev_x, prev_y = current_x, current_y
                if cmd == 'l':
                    current_x += x
                    current_y += y
                else:
                    current_x, current_y = x, y
                lines.append((prev_x, prev_y, current_x, current_y))

        elif cmd in 'Hh':
            if i < len(tokens):
                x = float(tokens[i])
                i += 1
                prev_x = current_x
                if cmd == 'h':
                    current_x += x
                else:
                    current_x = x
                lines.append((prev_x, current_y, current_x, current_y))

        elif cmd in 'Vv':
            if i < len(tokens):
                y = float(tokens[i])
                i += 1
                prev_y = current_y
                if cmd == 'v':
                    current_y += y
                else:
                    current_y = y
                lines.append((current_x, prev_y, current_x, current_y))

        elif cmd in 'Zz':
            if current_x != start_x or current_y != start_y:
                lines.append((current_x, current_y, start_x, start_y))
            current_x, current_y = start_x, start_y

        elif cmd in 'Cc':
            if i + 5 < len(tokens):
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


def compute_marker_bbox(line, marker):
    """Compute axis-aligned bounding box for a marker at line end, accounting for rotation.

    Note: Default markerUnits is 'strokeWidth', meaning marker dimensions are
    scaled by the line's stroke-width.
    """
    dx = line.x2 - line.x1
    dy = line.y2 - line.y1
    length = math.sqrt(dx * dx + dy * dy)

    # Scale marker by stroke width (markerUnits="strokeWidth" is default)
    scale = line.stroke_width
    width = marker.width * scale
    height = marker.height * scale
    ref_x = marker.ref_x * scale
    ref_y = marker.ref_y * scale

    if length < 0.001:
        # Degenerate line - just center the marker
        half_w = width / 2
        half_h = height / 2
        return BBox(
            line.x2 - half_w, line.y2 - half_h,
            line.x2 + half_w, line.y2 + half_h,
            f"{line.name}:marker", 'marker'
        )

    # Unit direction vector (line points this way)
    ux, uy = dx / length, dy / length
    # Perpendicular vector (90° counter-clockwise)
    px, py = -uy, ux

    # Marker corners in local coords (before rotation):
    # Origin at (0,0), extends to (width, height) after scaling
    # ref_x, ref_y is the attachment point placed at line endpoint
    corners_local = [
        (0, 0),
        (width, 0),
        (width, height),
        (0, height),
    ]

    # Transform each corner to global coords
    # Local x-axis maps to line direction (ux, uy)
    # Local y-axis maps to perpendicular (px, py)
    # Offset so ref_x, ref_y lands at (line.x2, line.y2)
    global_corners = []
    for lx, ly in corners_local:
        # Offset from ref point in local coords
        off_x = lx - ref_x
        off_y = ly - ref_y
        # Transform to global
        gx = line.x2 + off_x * ux + off_y * px
        gy = line.y2 + off_x * uy + off_y * py
        global_corners.append((gx, gy))

    # Compute axis-aligned bounding box
    xs = [c[0] for c in global_corners]
    ys = [c[1] for c in global_corners]

    return BBox(
        min(xs), min(ys), max(xs), max(ys),
        f"{line.name}:marker", 'marker'
    )


def find_element_line_numbers(svg_path: str) -> dict:
    """Pre-scan SVG to map element tags to line numbers."""
    line_map = {}
    tag_counts = {}

    with open(svg_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            for match in re.finditer(r'<(\w+)(?:\s|>|/)', line):
                tag = match.group(1)
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                line_map[(tag, tag_counts[tag])] = line_num

    return line_map


def extract_elements(svg_path: str, warn_missing_ids: bool = True) -> tuple:
    """Extract all elements from SVG file."""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    line_map = find_element_line_numbers(svg_path)
    tag_counts = {}

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

    defs_elements = set()
    markers = {}
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

    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        in_defs = elem in defs_elements
        name = get_name(elem, tag, skip_warning=in_defs)

        if in_defs:
            continue

        if tag == 'text':
            x = float(elem.get('x', 0))
            y = float(elem.get('y', 0))
            text_content = elem.text or ''

            font_family = elem.get('font-family', 'sans-serif')
            font_size = 12.0
            fs_attr = elem.get('font-size', '12')
            if fs_attr:
                fs_match = re.match(r'([0-9.]+)', fs_attr)
                if fs_match:
                    font_size = float(fs_match.group(1))

            anchor = elem.get('text-anchor', 'start')

            x_min, y_min, x_max, y_max = measure_text_bbox(
                text_content, x, y, font_family, font_size, anchor
            )

            bbox = BBox(x_min, y_min, x_max, y_max, text_content[:20] or name, 'text',
                        font_family=font_family, font_size=font_size)
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
            marker_end_id = None
            marker_end = elem.get('marker-end', '')
            if marker_end.startswith('url(#') and marker_end.endswith(')'):
                marker_end_id = marker_end[5:-1]
            stroke_width = float(elem.get('stroke-width', 1))
            line = Line(x1, y1, x2, y2, name, marker_end_id, stroke_width)
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
                marker_end_id = None
                marker_end = elem.get('marker-end', '')
                if marker_end.startswith('url(#') and marker_end.endswith(')'):
                    marker_end_id = marker_end[5:-1]
                stroke_width = float(elem.get('stroke-width', 1))
                path_segments = parse_path_to_lines(d)
                for idx, (x1, y1, x2, y2) in enumerate(path_segments):
                    segment_name = f"{name}_seg{idx}" if len(path_segments) > 1 else name
                    seg_marker = marker_end_id if idx == len(path_segments) - 1 else None
                    line = Line(x1, y1, x2, y2, segment_name, seg_marker, stroke_width)
                    lines.append(line)

    rendered_markers = []
    for line in lines:
        if line.marker_end_id and line.marker_end_id in markers:
            marker = markers[line.marker_end_id]
            bbox = compute_marker_bbox(line, marker)
            rendered_markers.append((line.name, bbox))

    return texts, rects, lines, polygons, rendered_markers, markers, missing_id_warnings
