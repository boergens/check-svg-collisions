#!/usr/bin/env python3
"""
TikZ Collision Checker - Detects problematic element interactions in TikZ figures.

Element types:
- Text: Any node with text content
- Box: Rectangles (with or without text inside)
- Arrow: Lines connecting elements

Collision rules:
1. Text ↔ Text: No overlap
2. Text ↔ Arrow: Arrow must not pass through text
3. Text ↔ Box: Text must not cross box border (fully in or fully out)
4. Arrow ↔ Box: Arrow only enters boxes at its endpoints
5. Box ↔ Box: No overlap unless one fully contains the other
"""

import re
import sys
import os
import subprocess
import tempfile
from dataclasses import dataclass


EPS = 0.01  # Tolerance for floating point comparisons


@dataclass
class BBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    name: str
    is_box: bool = False  # True if this is a styled box (not just text)

    def overlaps(self, other: 'BBox') -> bool:
        # Use epsilon tolerance to allow touching borders
        if self.x_max <= other.x_min + EPS or other.x_max <= self.x_min + EPS:
            return False
        if self.y_max <= other.y_min + EPS or other.y_max <= self.y_min + EPS:
            return False
        return True

    def contains(self, other: 'BBox') -> bool:
        return (self.x_min <= other.x_min and self.x_max >= other.x_max and
                self.y_min <= other.y_min and self.y_max >= other.y_max)

    def crosses_border(self, box: 'BBox') -> bool:
        """Check if self crosses the border of box (partially in, partially out)"""
        if not self.overlaps(box):
            return False
        if box.contains(self):
            return False
        if self.contains(box):
            return False
        return True


@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    start_node: str
    end_node: str

    def intersects_box(self, box: BBox) -> bool:
        """Check if line segment intersects with box interior"""
        # Vertical line
        if abs(self.x1 - self.x2) < 0.01:
            x = self.x1
            if box.x_min < x < box.x_max:
                y_min, y_max = min(self.y1, self.y2), max(self.y1, self.y2)
                if not (y_max <= box.y_min or y_min >= box.y_max):
                    return True
        # Horizontal line
        elif abs(self.y1 - self.y2) < 0.01:
            y = self.y1
            if box.y_min < y < box.y_max:
                x_min, x_max = min(self.x1, self.x2), max(self.x1, self.x2)
                if not (x_max <= box.x_min or x_min >= box.x_max):
                    return True
        return False


def parse_coordinate(coord_str: str) -> tuple:
    match = re.match(r'\(([^,]+),\s*([^)]+)\)', coord_str.strip())
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except ValueError:
            pass
    return None, None


def num_to_letters(n: int) -> str:
    """Convert number to letter-only string for LaTeX variable names (0->a, 25->z, 26->aa)"""
    result = []
    while True:
        result.append(chr(ord('a') + n % 26))
        n = n // 26 - 1
        if n < 0:
            break
    return ''.join(reversed(result))


def measure_text_widths_latex(texts: list, preamble: str) -> dict:
    """
    Measure text widths by compiling a LaTeX document.
    Returns dict mapping text -> width in cm.
    """
    if not texts:
        return {}

    # Build measurement document
    doc_lines = [preamble, '\\begin{document}', '\\newwrite\\widthfile', '\\immediate\\openout\\widthfile=widths.txt']

    for i, text in enumerate(texts):
        # Handle line breaks - measure longest line
        lines = text.split('\\\\')
        for j, line in enumerate(lines):
            clean_line = line.strip()
            if clean_line:
                # TeX command names cannot contain digits, use letters only
                var_name = f"w{num_to_letters(i)}x{num_to_letters(j)}"
                doc_lines.append(f'\\newlength{{\\{var_name}}}')
                doc_lines.append(f'\\settowidth{{\\{var_name}}}{{{clean_line}}}')
                doc_lines.append(f'\\immediate\\write\\widthfile{{{i},{j},\\the\\{var_name}}}')

    doc_lines.append('\\immediate\\closeout\\widthfile')
    doc_lines.append('\\end{document}')

    doc_content = '\n'.join(doc_lines)

    # Compile in temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, 'measure.tex')
        with open(tex_path, 'w') as f:
            f.write(doc_content)

        result = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', 'measure.tex'],
            cwd=tmpdir, capture_output=True, text=True
        )

        widths_path = os.path.join(tmpdir, 'widths.txt')
        if not os.path.exists(widths_path):
            print(f"Warning: LaTeX measurement failed", file=sys.stderr)
            return {}

        # Parse results - find max width per text index
        text_widths = {}
        with open(widths_path) as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    text_idx = int(parts[0])
                    # Width is like "42.0pt" - convert to cm
                    width_str = parts[2]
                    match = re.match(r'([0-9.]+)pt', width_str)
                    if match:
                        width_pt = float(match.group(1))
                        width_cm = width_pt * 0.0352778  # 1pt = 0.0352778cm
                        if text_idx not in text_widths:
                            text_widths[text_idx] = 0
                        text_widths[text_idx] = max(text_widths[text_idx], width_cm)

        return {texts[i]: w for i, w in text_widths.items()}


def extract_preamble(latex_content: str) -> str:
    """Extract document preamble (everything before \\begin{document})"""
    match = re.search(r'^(.*?)\\begin\{document\}', latex_content, re.DOTALL)
    if match:
        return match.group(1)
    return ''


def parse_dimension(dim_str: str) -> float:
    match = re.match(r'([0-9.]+)(cm|em|pt|mm)?', dim_str.strip())
    if match:
        value = float(match.group(1))
        unit = match.group(2) or 'cm'
        if unit == 'em':
            return value * 0.4
        elif unit == 'pt':
            return value * 0.0353
        elif unit == 'mm':
            return value * 0.1
        return value
    return 1.0


def extract_tikz_pictures(latex_content: str) -> list:
    pictures = []
    pattern = r'\\subsection\{(FIG\.\s*\d+[^}]*)\}.*?\\begin\{tikzpicture\}(.*?)\\end\{tikzpicture\}'
    for match in re.finditer(pattern, latex_content, re.DOTALL):
        fig_label = match.group(1).strip()
        tikz_content = match.group(2)
        start_line = latex_content[:match.start()].count('\n') + 1
        pictures.append((fig_label, start_line, tikz_content))
    return pictures


def collect_node_texts(tikz_content: str) -> list:
    """Extract all text content from nodes for measurement."""
    texts = []

    # Nodes with explicit positions: \node[...] at (...) {...}
    pattern1 = r'\\node\s*\[[^\]]*\](?:\s*\([^)]*\))?\s*at\s*\([^)]+\)(?:\s*\([^)]*\))?\s*\{([^}]*)\}'
    for match in re.finditer(pattern1, tikz_content):
        content = match.group(1).strip()
        if content and content not in texts:
            texts.append(content)

    # Nodes with relative positioning: \node[...] (name) {...}
    pattern2 = r'\\node\s*\[[^\]]*\]\s*\([^)]+\)\s*\{([^}]*)\}'
    for match in re.finditer(pattern2, tikz_content):
        content = match.group(1).strip()
        if content and content not in texts:
            texts.append(content)

    return texts


def extract_styles(latex_content: str, tikz_content: str) -> dict:
    styles = {}
    # Find tikzset block - use greedy match to capture nested braces
    tikzset_match = re.search(r'\\tikzset\s*\{', latex_content)
    if tikzset_match:
        start = tikzset_match.end()
        depth = 1
        end = start
        while depth > 0 and end < len(latex_content):
            if latex_content[end] == '{':
                depth += 1
            elif latex_content[end] == '}':
                depth -= 1
            end += 1
        content = latex_content[start:end-1]
        # Extract individual style definitions
        for match in re.finditer(r'(\w+)/\.style\s*=\s*\{([^}]+)\}', content):
            styles[match.group(1)] = match.group(2)
    # Local styles in tikz content
    for match in re.finditer(r'(\w+)/\.style\s*=\s*\{([^}]+)\}', tikz_content):
        styles[match.group(1)] = match.group(2)
    return styles


def get_min_dimensions(options: str, styles: dict) -> tuple:
    """Get MINIMUM width/height from options/styles. Returns (min_width, min_height, is_box)"""
    min_width, min_height = None, None
    is_box = False

    for style_name, style_def in styles.items():
        if style_name in options:
            if 'minimum width' in style_def or 'text width' in style_def:
                is_box = True
            if 'minimum width' in style_def:
                match = re.search(r'minimum width\s*=\s*([^,}]+)', style_def)
                if match:
                    min_width = parse_dimension(match.group(1))
            # text width sets the paragraph box width in TikZ
            if 'text width' in style_def:
                match = re.search(r'text width\s*=\s*([^,}]+)', style_def)
                if match:
                    tw = parse_dimension(match.group(1))
                    min_width = max(min_width or 0, tw)
            if 'minimum height' in style_def:
                match = re.search(r'minimum height\s*=\s*([^,}]+)', style_def)
                if match:
                    min_height = parse_dimension(match.group(1))

    if 'minimum width' in options:
        is_box = True
        match = re.search(r'minimum width\s*=\s*([^,\]]+)', options)
        if match:
            min_width = parse_dimension(match.group(1))
    if 'text width' in options:
        match = re.search(r'text width\s*=\s*([^,\]]+)', options)
        if match:
            tw = parse_dimension(match.group(1))
            min_width = max(min_width or 0, tw)
    if 'minimum height' in options:
        match = re.search(r'minimum height\s*=\s*([^,\]]+)', options)
        if match:
            min_height = parse_dimension(match.group(1))

    return min_width, min_height, is_box


def compute_node_dimensions(options: str, content: str, styles: dict, text_widths: dict) -> tuple:
    """Compute node width, height, and is_box flag."""
    min_width, min_height, is_box = get_min_dimensions(options, styles)
    measured = text_widths.get(content.strip(), 0.5) if content else 0.5
    width = max(min_width or 0, measured)
    height = max(min_height or 0, 0.5)

    # Add inner sep padding (TikZ default is ~0.3333em on each side ≈ 0.28cm total)
    inner_sep = 0.28
    width += inner_sep
    height += inner_sep

    return width, height, is_box


def extract_elements(tikz_content: str, styles: dict, text_widths: dict = None) -> tuple:
    """Extract all elements: text nodes, boxes, and arrows"""
    texts = []
    boxes = []
    node_positions = {}
    node_boxes = {}
    node_dims = {}  # Store dimensions before positions are computed
    text_widths = text_widths or {}

    # Extract node distance
    node_distance = 1.5
    dist_match = re.search(r'node distance\s*=\s*([0-9.]+)', tikz_content)
    if dist_match:
        node_distance = float(dist_match.group(1))

    # Pattern for nodes with explicit positions
    node_pattern = r'\\node\s*\[([^\]]*)\](?:\s*\(([^)]*)\))?\s*at\s*(\([^)]+\))(?:\s*\(([^)]*)\))?\s*\{([^}]*)\}'

    for match in re.finditer(node_pattern, tikz_content):
        options = match.group(1)
        name1 = match.group(2)
        coord_str = match.group(3)
        name2 = match.group(4)
        content = match.group(5)
        name = name1 or name2 or f"node_{len(texts) + len(boxes)}"

        x, y = parse_coordinate(coord_str)
        if x is None:
            continue

        node_positions[name] = (x, y)
        width, height, is_box = compute_node_dimensions(options, content, styles, text_widths)
        node_dims[name] = (width, height, is_box, content)

        # Handle anchor positioning
        if 'right' in options.split() or ', right' in options:
            x_min, x_max = x, x + width
        elif 'left' in options.split() or ', left' in options:
            x_min, x_max = x - width, x
        else:
            x_min, x_max = x - width/2, x + width/2

        if 'above' in options and 'below' not in options:
            y_min, y_max = y, y + height
        elif 'below' in options and 'above' not in options:
            y_min, y_max = y - height, y
        else:
            y_min, y_max = y - height/2, y + height/2

        bbox = BBox(x_min, y_min, x_max, y_max, name, is_box)
        node_boxes[name] = bbox

        if is_box:
            boxes.append(bbox)
        if content.strip():
            texts.append(bbox)

    # Pattern for nodes with relative positioning
    rel_pattern = r'\\node\s*\[([^\]]*)\]\s*\(([^)]+)\)\s*\{([^}]*)\}'

    # First pass: collect dimensions for all relative nodes
    for match in re.finditer(rel_pattern, tikz_content):
        options = match.group(1)
        name = match.group(2)
        content = match.group(3)
        if name not in node_dims:
            width, height, is_box = compute_node_dimensions(options, content, styles, text_widths)
            node_dims[name] = (width, height, is_box, content)

    # Multiple passes for chains - now with edge-to-edge positioning
    for _ in range(5):
        for match in re.finditer(rel_pattern, tikz_content):
            options = match.group(1)
            name = match.group(2)
            content = match.group(3)

            if name in node_positions:
                continue

            # Get this node's dimensions
            cur_width, cur_height, is_box, _ = node_dims[name]

            x, y = None, None

            # Simple relative: below=of X
            rel_match = re.search(r'(below|above|left|right)\s*=\s*(?:of\s+)?(\w+)', options)
            if rel_match:
                direction = rel_match.group(1)
                ref_node = rel_match.group(2)
                if ref_node in node_positions and ref_node in node_dims:
                    ref_x, ref_y = node_positions[ref_node]
                    ref_width, ref_height, _, _ = node_dims[ref_node]

                    # Edge-to-edge: add half-heights/widths to convert to center-to-center
                    if direction == 'below':
                        x = ref_x
                        y = ref_y - node_distance - ref_height/2 - cur_height/2
                    elif direction == 'above':
                        x = ref_x
                        y = ref_y + node_distance + ref_height/2 + cur_height/2
                    elif direction == 'left':
                        x = ref_x - node_distance - ref_width/2 - cur_width/2
                        y = ref_y
                    elif direction == 'right':
                        x = ref_x + node_distance + ref_width/2 + cur_width/2
                        y = ref_y

            # Compound: below left=1.5cm and 1cm of X
            compound_match = re.search(
                r'(below|above)\s*(left|right)\s*=\s*([0-9.]+)(?:cm)?\s*and\s*([0-9.]+)(?:cm)?\s*of\s*(\w+)',
                options)
            if compound_match:
                vert = compound_match.group(1)
                horiz = compound_match.group(2)
                vert_dist = float(compound_match.group(3))
                horiz_dist = float(compound_match.group(4))
                ref_node = compound_match.group(5)
                if ref_node in node_positions and ref_node in node_dims:
                    ref_x, ref_y = node_positions[ref_node]
                    ref_width, ref_height, _, _ = node_dims[ref_node]

                    # Edge-to-edge: add half-dimensions
                    horiz_offset = horiz_dist + ref_width/2 + cur_width/2
                    vert_offset = vert_dist + ref_height/2 + cur_height/2

                    x = ref_x + (horiz_offset if horiz == 'right' else -horiz_offset)
                    y = ref_y + (-vert_offset if vert == 'below' else vert_offset)

            if x is None and y is None:
                if not re.search(r'(below|above|left|right)\s*=', options):
                    x, y = 0, 0

            if x is not None and y is not None:
                node_positions[name] = (x, y)
                width, height = cur_width, cur_height

                x_min, x_max = x - width/2, x + width/2
                y_min, y_max = y - height/2, y + height/2

                bbox = BBox(x_min, y_min, x_max, y_max, name, is_box)
                node_boxes[name] = bbox

                if is_box:
                    boxes.append(bbox)
                if content.strip():
                    texts.append(bbox)

    # Extract arrows
    arrows = []
    draw_pattern = r'\\draw\[([^\]]*)\]\s*\(([^)]+)\)\s*--\s*\+\+\(([^)]+)\)\s*(\|-)?\s*\(([^)]+)\)'

    for match in re.finditer(draw_pattern, tikz_content):
        start_ref = match.group(2)
        offset_str = match.group(3)
        connector = match.group(4)
        end_ref = match.group(5)

        start_node = start_ref.split('.')[0]
        start_anchor = start_ref.split('.')[1] if '.' in start_ref else 'center'
        end_node = end_ref.split('.')[0]
        end_anchor = end_ref.split('.')[1] if '.' in end_ref else 'center'

        if start_node not in node_positions or end_node not in node_positions:
            continue

        sx, sy = node_positions[start_node]
        if start_node in node_boxes:
            box = node_boxes[start_node]
            if start_anchor == 'east':
                sx = box.x_max
            elif start_anchor == 'west':
                sx = box.x_min
            sy = (box.y_min + box.y_max) / 2

        offset_parts = offset_str.split(',')
        if len(offset_parts) != 2:
            continue
        try:
            ox = float(offset_parts[0])
            oy = float(offset_parts[1])
        except ValueError:
            continue

        ix, iy = sx + ox, sy + oy

        ex, ey = node_positions[end_node]
        if end_node in node_boxes:
            box = node_boxes[end_node]
            if end_anchor == 'east':
                ex = box.x_max
            elif end_anchor == 'west':
                ex = box.x_min
            ey = (box.y_min + box.y_max) / 2

        if connector == '|-':
            arrows.append(Line(ix, iy, ix, ey, start_node, end_node))
            arrows.append(Line(ix, ey, ex, ey, start_node, end_node))
        else:
            arrows.append(Line(ix, iy, ex, ey, start_node, end_node))

    return texts, boxes, arrows, node_boxes


def check_collisions(texts: list, boxes: list, arrows: list, node_boxes: dict) -> list:
    """
    Check all collision rules:
    1. Text ↔ Text: No overlap
    2. Text ↔ Arrow: Arrow must not pass through text
    3. Text ↔ Box: Text must not cross box border
    4. Arrow ↔ Box: Arrow only enters at endpoints
    5. Box ↔ Box: No overlap unless containment
    """
    issues = []

    # Rule 1: Text ↔ Text - no overlap
    for i, t1 in enumerate(texts):
        for t2 in texts[i+1:]:
            if t1.overlaps(t2):
                issues.append(("text overlap", t1.name, t2.name))

    # Rule 2: Text ↔ Arrow - arrow must not pass through text
    for arrow in arrows:
        for text in texts:
            # Skip if text is at arrow endpoint
            if text.name in (arrow.start_node, arrow.end_node):
                continue
            if arrow.intersects_box(text):
                issues.append(("arrow through text", f"{arrow.start_node}→{arrow.end_node}", text.name))

    # Rule 3: Text ↔ Box - text must not cross box border
    for text in texts:
        for box in boxes:
            if text.name == box.name:
                continue  # Same element
            if text.crosses_border(box):
                issues.append(("text crosses box border", text.name, box.name))

    # Rule 4: Arrow ↔ Box - arrow only enters at endpoints
    for arrow in arrows:
        for box in boxes:
            if box.name in (arrow.start_node, arrow.end_node):
                continue  # Arrow is connected to this box
            # Skip if box contains both endpoints (arrow is inside the box, not passing through)
            start_box = node_boxes.get(arrow.start_node)
            end_box = node_boxes.get(arrow.end_node)
            if start_box and end_box and box.contains(start_box) and box.contains(end_box):
                continue
            if arrow.intersects_box(box):
                issues.append(("arrow through box", f"{arrow.start_node}→{arrow.end_node}", box.name))

    # Rule 5: Box ↔ Box - no overlap unless containment
    for i, b1 in enumerate(boxes):
        for b2 in boxes[i+1:]:
            if b1.overlaps(b2):
                if not (b1.contains(b2) or b2.contains(b1)):
                    issues.append(("box overlap", b1.name, b2.name))

    return issues


def check_file(filepath: str) -> list:
    with open(filepath, 'r') as f:
        content = f.read()

    pictures = extract_tikz_pictures(content)
    preamble = extract_preamble(content)

    # Collect all texts from all figures for batch measurement
    all_texts = []
    for _, _, tikz_content in pictures:
        all_texts.extend(collect_node_texts(tikz_content))
    all_texts = list(set(all_texts))  # deduplicate

    # Measure all text widths via LaTeX
    text_widths = measure_text_widths_latex(all_texts, preamble)

    results = []
    for fig_label, line_num, tikz_content in pictures:
        styles = extract_styles(content, tikz_content)
        texts, boxes, arrows, node_boxes = extract_elements(tikz_content, styles, text_widths)
        issues = check_collisions(texts, boxes, arrows, node_boxes)

        results.append({
            'figure': fig_label,
            'line': line_num,
            'texts': len(texts),
            'boxes': len(boxes),
            'arrows': len(arrows),
            'issues': issues
        })

    return results


def main():
    verbose = False
    filepath = '/Users/kevin/Documents/newstart/claudeCAD/docs/provisional_patent.tex'

    for arg in sys.argv[1:]:
        if arg in ['-h', '--help']:
            print("Usage: check_tikz_collisions.py [-v] [file.tex]")
            print("\nChecks TikZ figures for problematic element interactions:")
            print("  1. Text overlapping text")
            print("  2. Arrows passing through text")
            print("  3. Text crossing box borders")
            print("  4. Arrows passing through unconnected boxes")
            print("  5. Boxes overlapping (without containment)")
            print("\n  -v, --verbose  Show element counts")
            return 0
        elif arg in ['-v', '--verbose']:
            verbose = True
        else:
            filepath = arg

    print(f"Checking: {filepath}\n")
    print("=" * 60)

    results = check_file(filepath)
    total_issues = 0

    for result in results:
        fig = result['figure']
        issues = result['issues']
        issue_count = len(issues)
        total_issues += issue_count

        status = "OK" if issue_count == 0 else f"ISSUES ({issue_count})"
        counts = f"{result['texts']}t/{result['boxes']}b/{result['arrows']}a" if verbose else ""
        print(f"\n{fig} (line {result['line']}) {counts}: {status}")

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
