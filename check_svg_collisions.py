#!/usr/bin/env python3
"""
SVG Collision Checker - Detects problematic element interactions in SVG figures.

Collision rules:
1. Text - Text: No overlap
2. Text - Line: Line must not pass through text
3. Text - Box: Text must be fully inside or outside (no border crossing)
4. Box - Box: No overlap unless one fully contains the other
5. Line - Box: Lines must not pass through boxes
6. Line - Marker: Lines must not pass through rendered markers
"""

import sys
import os

from svg_parser import extract_elements
from collision_rules import check_collisions


def check_file(svg_path: str) -> dict:
    """Check a single SVG file for collisions."""
    texts, rects, lines, polygons, rendered_markers, markers, missing_ids = extract_elements(svg_path)
    issues, warnings = check_collisions(texts, rects, lines, polygons, rendered_markers, markers)

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
            print("  3. Text crossing box borders")
            print("  4. Boxes overlapping (without containment)")
            print("  5. Lines passing through boxes")
            print("\n  -v, --verbose  Show element counts")
            return 0
        elif arg in ['-v', '--verbose']:
            verbose = True
        else:
            files.append(arg)

    if not files:
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
