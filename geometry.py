#!/usr/bin/env python3
"""Geometric primitives for SVG collision detection."""

from dataclasses import dataclass


@dataclass
class BBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    name: str
    elem_type: str  # 'text', 'rect', 'line', 'polygon'
    font_family: str = None
    font_size: float = None

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
    stroke_width: float = 1.0

    @property
    def length(self) -> float:
        return ((self.x2 - self.x1) ** 2 + (self.y2 - self.y1) ** 2) ** 0.5

    def _point_at_box_edge(self, px: float, py: float, box: BBox, eps: float = 1.0) -> bool:
        """Check if point is at box edge (not deep inside)."""
        in_x = box.x_min - eps <= px <= box.x_max + eps
        in_y = box.y_min - eps <= py <= box.y_max + eps
        if not (in_x and in_y):
            return False
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
        """Check if line segment intersects box using Liang-Barsky clipping."""
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1

        t_min, t_max = 0.0, 1.0

        # Check x bounds
        if abs(dx) > 0.0001:
            t1 = (box.x_min - eps - self.x1) / dx
            t2 = (box.x_max + eps - self.x1) / dx
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            if self.x1 < box.x_min - eps or self.x1 > box.x_max + eps:
                return False

        # Check y bounds
        if abs(dy) > 0.0001:
            t1 = (box.y_min - eps - self.y1) / dy
            t2 = (box.y_max + eps - self.y1) / dy
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            if self.y1 < box.y_min - eps or self.y1 > box.y_max + eps:
                return False

        return t_min <= t_max

    def _touches_corner(self, box: BBox, eps: float = 2.0) -> bool:
        """Check if line touches a box corner without passing through."""
        corners = [
            (box.x_min, box.y_min), (box.x_max, box.y_min),
            (box.x_min, box.y_max), (box.x_max, box.y_max),
        ]
        for cx, cy in corners:
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

    def _clip_to_box(self, box: BBox) -> tuple:
        """Return (t_min, t_max) for line clipped to box, or None if no intersection."""
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        t_min, t_max = 0.0, 1.0

        if abs(dx) > 0.0001:
            t1 = (box.x_min - self.x1) / dx
            t2 = (box.x_max - self.x1) / dx
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            if self.x1 < box.x_min or self.x1 > box.x_max:
                return None

        if abs(dy) > 0.0001:
            t1 = (box.y_min - self.y1) / dy
            t2 = (box.y_max - self.y1) / dy
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
        else:
            if self.y1 < box.y_min or self.y1 > box.y_max:
                return None

        if t_min > t_max:
            return None
        return (t_min, t_max)

    def passes_through_box(self, box: BBox) -> bool:
        """Check if line crosses through box (not just touches corner/edge)."""
        clip = self._clip_to_box(box)
        if clip is None:
            return False

        t_min, t_max = clip

        # Line fully inside box - OK
        if t_min <= 0.001 and t_max >= 0.999:
            p1_inside = self._point_in_box(self.x1, self.y1, box)
            p2_inside = self._point_in_box(self.x2, self.y2, box)
            if p1_inside and p2_inside:
                return False

        # Corner touch - clipped segment is essentially a point
        if abs(t_max - t_min) < 0.01:
            return False

        # Compute clipped segment endpoints
        dx, dy = self.x2 - self.x1, self.y2 - self.y1
        cx1 = self.x1 + t_min * dx
        cy1 = self.y1 + t_min * dy
        cx2 = self.x1 + t_max * dx
        cy2 = self.y1 + t_max * dy

        # Check if both clipped endpoints are on same edge (line runs along edge)
        eps = 1.0
        same_edge = (
            (abs(cx1 - box.x_min) <= eps and abs(cx2 - box.x_min) <= eps) or
            (abs(cx1 - box.x_max) <= eps and abs(cx2 - box.x_max) <= eps) or
            (abs(cy1 - box.y_min) <= eps and abs(cy2 - box.y_min) <= eps) or
            (abs(cy1 - box.y_max) <= eps and abs(cy2 - box.y_max) <= eps)
        )
        if same_edge:
            return False

        # Clipped endpoints on different edges - line crosses through
        return True

    def touches_box_corner(self, box: BBox) -> bool:
        """Check if line touches box corner (warning, not error)."""
        if self.passes_through_box(box):
            return False
        return self._touches_corner(box)

    def direction(self) -> tuple:
        """Return normalized direction vector (dx, dy)."""
        dx, dy = self.x2 - self.x1, self.y2 - self.y1
        length = (dx * dx + dy * dy) ** 0.5
        if length < 0.001:
            return (0, 0)
        return (dx / length, dy / length)

    def is_parallel_to(self, other: 'Line', eps: float = 0.001) -> bool:
        """Check if two lines are exactly parallel (within floating point tolerance)."""
        d1 = self.direction()
        d2 = other.direction()
        if d1 == (0, 0) or d2 == (0, 0):
            return False
        cross = abs(d1[0] * d2[1] - d1[1] * d2[0])
        return cross < eps

    def perpendicular_distance_to(self, other: 'Line') -> float:
        """Calculate perpendicular distance between two parallel lines."""
        dx, dy = self.direction()
        px, py = self.x1 - other.x1, self.y1 - other.y1
        return abs(px * (-dy) + py * dx)

    def _project_onto_axis(self, axis_x: float, axis_y: float) -> tuple:
        """Project line endpoints onto an axis, return (min, max) of projections."""
        p1 = self.x1 * axis_x + self.y1 * axis_y
        p2 = self.x2 * axis_x + self.y2 * axis_y
        return (min(p1, p2), max(p1, p2))

    def overlaps_in_direction(self, other: 'Line') -> bool:
        """Check if two parallel lines overlap when projected onto their shared direction."""
        dx, dy = self.direction()
        if dx == 0 and dy == 0:
            return False
        min1, max1 = self._project_onto_axis(dx, dy)
        min2, max2 = other._project_onto_axis(dx, dy)
        return max1 > min2 and max2 > min1

    def distance_to_box_edge(self, box: BBox) -> float | None:
        """
        Calculate perpendicular distance to nearest parallel box edge.
        Returns None if line is not parallel to any box edge.
        """
        dx, dy = self.direction()
        if dx == 0 and dy == 0:
            return None

        is_horizontal = abs(dy) < 0.001
        is_vertical = abs(dx) < 0.001

        if not is_horizontal and not is_vertical:
            return None

        if is_horizontal:
            line_y = self.y1
            line_min_x, line_max_x = min(self.x1, self.x2), max(self.x1, self.x2)
            distances = []
            if line_max_x > box.x_min and line_min_x < box.x_max:
                distances.append(abs(line_y - box.y_min))
                distances.append(abs(line_y - box.y_max))
            return min(distances) if distances else None
        else:
            line_x = self.x1
            line_min_y, line_max_y = min(self.y1, self.y2), max(self.y1, self.y2)
            distances = []
            if line_max_y > box.y_min and line_min_y < box.y_max:
                distances.append(abs(line_x - box.x_min))
                distances.append(abs(line_x - box.x_max))
            return min(distances) if distances else None
