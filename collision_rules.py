#!/usr/bin/env python3
"""Collision detection rules for SVG elements."""


def check_collisions(texts, rects, lines, polygons, rendered_markers=None) -> tuple:
    """Check all collision rules. Returns (issues, warnings)."""
    issues = []
    warnings = []

    if rendered_markers is None:
        rendered_markers = []

    boxes = rects + polygons

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
