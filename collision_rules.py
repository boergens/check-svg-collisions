#!/usr/bin/env python3
"""Collision detection rules for SVG elements."""

from measure_text import measure_en_dash_width

MIN_MARKER_SEGMENT_RATIO = 1.5  # segment must be at least 1.5x marker width


def nearest_gap(text, box) -> tuple:
    """
    Calculate the nearest gap between text and box, only if they're adjacent.
    Returns (gap, is_adjacent, direction) where direction is 'horizontal' or 'vertical'.
    Returns (None, False, None) if they're not adjacent (gap in both axes).
    """
    # Check overlap in each axis
    x_overlap = text.x_max > box.x_min and box.x_max > text.x_min
    y_overlap = text.y_max > box.y_min and box.y_max > text.y_min

    if x_overlap and y_overlap:
        return (0, True, None)  # actually overlapping

    if x_overlap:
        # They overlap in x, check y gap
        gap_above = box.y_min - text.y_max  # text is above box
        gap_below = text.y_min - box.y_max  # text is below box
        if gap_above > 0:
            return (gap_above, True, 'vertical')
        if gap_below > 0:
            return (gap_below, True, 'vertical')

    if y_overlap:
        # They overlap in y, check x gap
        gap_left = box.x_min - text.x_max  # text is left of box
        gap_right = text.x_min - box.x_max  # text is right of box
        if gap_left > 0:
            return (gap_left, True, 'horizontal')
        if gap_right > 0:
            return (gap_right, True, 'horizontal')

    # No overlap in either axis - not adjacent
    return (None, False, None)


def check_collisions(texts, rects, lines, polygons, rendered_markers=None, markers=None) -> tuple:
    """Check all collision rules. Returns (issues, warnings)."""
    issues = []
    warnings = []

    if rendered_markers is None:
        rendered_markers = []
    if markers is None:
        markers = {}

    boxes = rects + polygons

    # Rule 0: Lines with markers should have sufficient length
    for line in lines:
        if line.marker_end_id and line.marker_end_id in markers:
            marker = markers[line.marker_end_id]
            min_length = marker.width * line.stroke_width * MIN_MARKER_SEGMENT_RATIO
            if line.length < min_length:
                issues.append(("short marker segment", line.name, f"{line.length:.0f}px < {min_length:.0f}px"))

    # Rule 1: Text - Text: no overlap
    for i, t1 in enumerate(texts):
        for t2 in texts[i + 1:]:
            if t1.overlaps(t2):
                issues.append(("text overlap", t1.name, t2.name))

    # Rule 2: Text - Line: line must not pass through text
    for line in lines:
        for text in texts:
            if line.intersects_box(text):
                issues.append(("line through text", line.name, text.name))

    # Rule 3: Text - Box: text should not CROSS box borders
    for text in texts:
        for box in boxes:
            if text.overlaps(box):
                if box.contains(text):
                    continue
                if text.contains(box):
                    continue
                issues.append(("text crosses box", text.name, box.name))

    # Rule 3b: Text - Box: text should not be too close to box edge
    for text in texts:
        if not text.font_family or not text.font_size:
            continue
        min_gap_required = measure_en_dash_width(text.font_family, text.font_size)
        for box in boxes:
            if box.contains(text) or text.contains(box):
                continue
            gap, is_adjacent, direction = nearest_gap(text, box)
            if is_adjacent and gap is not None and 0 < gap < min_gap_required:
                dir_str = f" ({direction})" if direction else ""
                issues.append(("text too close to box", text.name, f"{gap:.1f}px < {min_gap_required:.1f}px{dir_str}"))

    # Rule 4: Box - Box: no overlap unless containment
    for i, b1 in enumerate(boxes):
        for b2 in boxes[i + 1:]:
            if b1.overlaps(b2):
                if not (b1.contains(b2) or b2.contains(b1)):
                    issues.append(("box overlap", b1.name, b2.name))

    # Rule 5: Line - Box: line must not pass through box
    for line in lines:
        for box in boxes:
            if line.passes_through_box(box):
                issues.append(("line through box", line.name, box.name))
            elif line.touches_box_corner(box):
                warnings.append(("line touches corner", line.name, box.name))

    # Rule 6: Line - Marker: lines must not pass through rendered markers
    # Exception: lines starting/ending at marker tip going perpendicular are OK
    for owner_name, marker_box, tip_x, tip_y, dir_x, dir_y in rendered_markers:
        for line in lines:
            if line.name == owner_name or line.name.startswith(owner_name + "_seg"):
                continue
            if line.passes_through_box(marker_box):
                # Check if line starts or ends at the marker tip
                eps = 2.0  # tolerance for "at the tip"
                starts_at_tip = abs(line.x1 - tip_x) < eps and abs(line.y1 - tip_y) < eps
                ends_at_tip = abs(line.x2 - tip_x) < eps and abs(line.y2 - tip_y) < eps

                if starts_at_tip or ends_at_tip:
                    # Check if line goes perpendicular (or away from) the marker
                    line_dx, line_dy = line.direction()
                    # If line starts at tip, it goes in its direction; if ends at tip, opposite
                    if ends_at_tip:
                        line_dx, line_dy = -line_dx, -line_dy
                    # Dot product: 0 = perpendicular, negative = going away from marker
                    dot = line_dx * dir_x + line_dy * dir_y
                    if dot <= 0.1:  # perpendicular or going away (small tolerance for rounding)
                        continue  # This is OK, not a collision

                issues.append(("line through marker", line.name, marker_box.name))
            elif line.touches_box_corner(marker_box):
                warnings.append(("line touches marker corner", line.name, marker_box.name))

    # Rule 7: Parallel lines too close
    for i, l1 in enumerate(lines):
        for l2 in lines[i + 1:]:
            if not l1.is_parallel_to(l2):
                continue
            if not l1.overlaps_in_direction(l2):
                continue
            dist = l1.perpendicular_distance_to(l2)
            min_dist = max(l1.stroke_width, l2.stroke_width) * 3
            if dist < min_dist:
                issues.append(("parallel lines too close", l1.name, f"{l2.name} ({dist:.1f}px < {min_dist:.1f}px)"))

    # Rule 8: Line too close to box edge
    for line in lines:
        for box in boxes:
            dist = line.distance_to_box_edge(box)
            if dist is None:
                continue
            min_dist = line.stroke_width * 3
            if 0 < dist < min_dist:
                issues.append(("line too close to box edge", line.name, f"{box.name} ({dist:.1f}px < {min_dist:.1f}px)"))

    return issues, warnings
