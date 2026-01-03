#!/usr/bin/env python3
"""Collision detection rules for SVG elements."""

from measure_text import measure_en_dash_width

MIN_MARKER_SEGMENT_RATIO = 2.0  # segment must be at least 2x marker width


def nearest_gap(text, box) -> tuple:
    """
    Calculate the nearest gap between text and box, only if they're adjacent.
    Returns (gap, True) if they're adjacent (overlap in one axis, gap in other).
    Returns (None, False) if they're not adjacent (gap in both axes).
    """
    # Check overlap in each axis
    x_overlap = text.x_max > box.x_min and box.x_max > text.x_min
    y_overlap = text.y_max > box.y_min and box.y_max > text.y_min

    if x_overlap and y_overlap:
        return (0, True)  # actually overlapping

    if x_overlap:
        # They overlap in x, check y gap
        gap_above = box.y_min - text.y_max  # text is above box
        gap_below = text.y_min - box.y_max  # text is below box
        if gap_above > 0:
            return (gap_above, True)
        if gap_below > 0:
            return (gap_below, True)

    if y_overlap:
        # They overlap in y, check x gap
        gap_left = box.x_min - text.x_max  # text is left of box
        gap_right = text.x_min - box.x_max  # text is right of box
        if gap_left > 0:
            return (gap_left, True)
        if gap_right > 0:
            return (gap_right, True)

    # No overlap in either axis - not adjacent
    return (None, False)


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
            min_length = marker.width * MIN_MARKER_SEGMENT_RATIO
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
            gap, is_adjacent = nearest_gap(text, box)
            if is_adjacent and gap is not None and 0 < gap < min_gap_required:
                issues.append(("text too close to box", text.name, f"{gap:.1f}px < {min_gap_required:.1f}px"))

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
    for owner_name, marker_box in rendered_markers:
        for line in lines:
            if line.name == owner_name or line.name.startswith(owner_name + "_seg"):
                continue
            if line.passes_through_box(marker_box):
                issues.append(("line through marker", line.name, marker_box.name))
            elif line.touches_box_corner(marker_box):
                warnings.append(("line touches marker corner", line.name, marker_box.name))

    return issues, warnings
