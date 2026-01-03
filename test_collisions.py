#!/usr/bin/env python3
"""Tests for SVG collision detection."""

import tempfile
import os
from check_svg_collisions import check_file


def write_svg(content: str) -> str:
    """Write SVG content to a temp file and return path."""
    fd, path = tempfile.mkstemp(suffix='.svg')
    with os.fdopen(fd, 'w') as f:
        f.write(f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
{content}
</svg>''')
    return path


def test_case(name: str, svg_content: str, expected: str):
    """Run a test case and print result.

    expected: 'issues', 'warnings', or 'clean'
    """
    path = write_svg(svg_content)
    result = check_file(path)
    os.unlink(path)

    has_issues = len(result['issues']) > 0
    has_warnings = len(result['warnings']) > 0

    if expected == 'issues':
        passed = has_issues
    elif expected == 'warnings':
        passed = has_warnings and not has_issues
    else:  # clean
        passed = not has_issues and not has_warnings

    status = "PASS" if passed else "FAIL"
    counts = []
    if has_issues:
        counts.append(f"{len(result['issues'])} issues")
    if has_warnings:
        counts.append(f"{len(result['warnings'])} warnings")
    count_str = f" ({', '.join(counts)})" if counts else ""

    print(f"  {status}: {name} - expected {expected}{count_str}")
    if not passed:
        for issue in result['issues']:
            print(f"        issue: {issue}")
        for warning in result['warnings']:
            print(f"        warning: {warning}")
    return passed


def main():
    passed = 0
    failed = 0

    print("\n=== Text ↔ Text ===")

    # Should trigger: overlapping text
    if test_case("overlapping text",
        '''<text x="50" y="50" font-size="20">Hello</text>
           <text x="60" y="50" font-size="20">World</text>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: separate text
    if test_case("separate text",
        '''<text x="10" y="50" font-size="12">Hello</text>
           <text x="100" y="50" font-size="12">World</text>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    print("\n=== Text ↔ Line ===")

    # Should trigger: line through text
    if test_case("line through text",
        '''<text x="50" y="50" font-size="20">Hello</text>
           <line x1="0" y1="50" x2="200" y2="50" stroke="black"/>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: line misses text
    if test_case("line misses text",
        '''<text x="50" y="50" font-size="12">Hello</text>
           <line x1="0" y1="100" x2="200" y2="100" stroke="black"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    print("\n=== Text ↔ Box ===")

    # Should trigger: text crosses box border
    if test_case("text crosses box border",
        '''<rect x="50" y="30" width="50" height="50"/>
           <text x="40" y="50" font-size="20">Hello</text>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: text fully inside box
    if test_case("text inside box",
        '''<rect x="10" y="10" width="180" height="180"/>
           <text x="50" y="100" font-size="12">Hello</text>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: text fully outside box
    if test_case("text outside box",
        '''<rect x="100" y="100" width="50" height="50"/>
           <text x="10" y="50" font-size="12">Hello</text>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should trigger: text too close to box edge (less than en-dash width)
    # Text "Hello" ends around x=38, box starts at x=40, gap ~2px < 6.7px en-dash
    if test_case("text too close to box",
        '''<rect x="40" y="10" width="100" height="100"/>
           <text x="10" y="60" font-size="12">Hello</text>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: text far enough from box edge
    # Text "Hello" ends around x=38, box starts at x=50, gap ~12px > 6.7px en-dash
    if test_case("text adequate distance from box",
        '''<rect x="50" y="10" width="100" height="100"/>
           <text x="10" y="60" font-size="12">Hello</text>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    print("\n=== Box ↔ Box ===")

    # Should trigger: overlapping boxes (no containment)
    if test_case("overlapping boxes",
        '''<rect x="10" y="10" width="80" height="80"/>
           <rect x="50" y="50" width="80" height="80"/>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: one box contains other
    if test_case("nested boxes (containment)",
        '''<rect x="10" y="10" width="180" height="180"/>
           <rect x="50" y="50" width="50" height="50"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: separate boxes
    if test_case("separate boxes",
        '''<rect x="10" y="10" width="40" height="40"/>
           <rect x="100" y="100" width="40" height="40"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    print("\n=== Line ↔ Box ===")

    # Should trigger: line passes through box (both endpoints outside)
    if test_case("line passes through box",
        '''<rect x="50" y="50" width="50" height="50"/>
           <line x1="0" y1="75" x2="200" y2="75" stroke="black"/>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: line misses box
    if test_case("line misses box",
        '''<rect x="50" y="50" width="50" height="50"/>
           <line x1="0" y1="10" x2="200" y2="10" stroke="black"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: line connects to box edge
    if test_case("line connects to box edge",
        '''<rect x="50" y="50" width="50" height="50"/>
           <line x1="0" y1="75" x2="50" y2="75" stroke="black"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: line fully contained inside box (e.g., legend samples)
    if test_case("line inside box",
        '''<rect x="10" y="10" width="180" height="180"/>
           <line x1="50" y1="100" x2="150" y2="100" stroke="black"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: diagonal line misses box (bounding boxes overlap but line doesn't intersect)
    # This was causing false positives in fig1 - line from (160,230) to (110,280) vs box at (150,280)
    if test_case("diagonal line misses box (bbox overlap)",
        '''<rect x="150" y="280" width="100" height="50"/>
           <line x1="160" y1="230" x2="110" y2="280" stroke="black"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should trigger warning: line grazes box corner without entering interior
    # Line from (0,100) to (100,0) passes through corner (50,50) but stays outside
    if test_case("line grazes box corner",
        '''<rect x="50" y="50" width="50" height="50"/>
           <line x1="0" y1="100" x2="100" y2="0" stroke="black"/>''',
        expected='warnings'):
        passed += 1
    else:
        failed += 1

    # Should trigger: diagonal from corner to corner passes through interior
    if test_case("diagonal corner-to-corner through interior",
        '''<rect x="50" y="50" width="50" height="50"/>
           <line x1="25" y1="25" x2="125" y2="125" stroke="black"/>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should trigger: diagonal line through box interior
    if test_case("diagonal line through box interior",
        '''<rect x="50" y="50" width="50" height="50"/>
           <line x1="0" y1="60" x2="120" y2="90" stroke="black"/>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should trigger: path crosses box via edge nodes (enters left edge, exits right edge)
    # This tests that even with nodes exactly on the edges, crossing through is detected
    if test_case("path crosses box via edge nodes",
        '''<rect x="50" y="50" width="50" height="50"/>
           <path d="M 25 75 L 50 75 L 100 75 L 125 75" stroke="black" fill="none"/>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    print("\n=== Defs Handling ===")

    # Should NOT trigger: elements inside <defs> should be ignored
    # This was causing false positives - arrowhead markers were being checked for collisions
    if test_case("elements in defs are ignored",
        '''<defs>
             <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
               <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
             </marker>
           </defs>
           <line x1="0" y1="3" x2="100" y2="3" stroke="black"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    print("\n=== Short Marker Segments ===")

    # Should trigger: arrow segment too short for marker
    if test_case("short marker segment",
        '''<defs>
             <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
               <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
             </marker>
           </defs>
           <line id="arrow1" x1="0" y1="50" x2="15" y2="50" stroke="black" marker-end="url(#arrowhead)"/>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: arrow segment long enough
    if test_case("adequate marker segment",
        '''<defs>
             <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
               <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
             </marker>
           </defs>
           <line id="arrow1" x1="0" y1="50" x2="25" y2="50" stroke="black" marker-end="url(#arrowhead)"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    print("\n=== Marker Collisions ===")

    # Should trigger: line passes through rendered arrowhead marker
    # Line 1 ends at (100, 50) with arrowhead, Line 2 crosses through that arrowhead
    if test_case("line through arrowhead marker",
        '''<defs>
             <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
               <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
             </marker>
           </defs>
           <line id="arrow1" x1="0" y1="50" x2="100" y2="50" stroke="black" marker-end="url(#arrowhead)"/>
           <line id="line2" x1="100" y1="0" x2="100" y2="100" stroke="black"/>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: line misses arrowhead marker
    if test_case("line misses arrowhead marker",
        '''<defs>
             <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
               <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
             </marker>
           </defs>
           <line id="arrow1" x1="0" y1="50" x2="100" y2="50" stroke="black" marker-end="url(#arrowhead)"/>
           <line id="line2" x1="50" y1="0" x2="50" y2="100" stroke="black"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: arrow pointing into a box (marker overlaps target box intentionally)
    if test_case("arrow into box is OK",
        '''<defs>
             <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
               <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
             </marker>
           </defs>
           <rect id="target-box" x="100" y="25" width="80" height="50"/>
           <line id="arrow1" x1="0" y1="50" x2="100" y2="50" stroke="black" marker-end="url(#arrowhead)"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    print("\n=== Parallel Lines ===")

    # Should trigger: two parallel lines too close (1px apart, need 3px min for stroke-width 1)
    if test_case("parallel lines too close",
        '''<line id="line1" x1="10" y1="50" x2="100" y2="50" stroke="black" stroke-width="1"/>
           <line id="line2" x1="10" y1="51" x2="100" y2="51" stroke="black" stroke-width="1"/>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: parallel lines far enough apart (5px apart, 3px min)
    if test_case("parallel lines adequate distance",
        '''<line id="line1" x1="10" y1="50" x2="100" y2="50" stroke="black" stroke-width="1"/>
           <line id="line2" x1="10" y1="55" x2="100" y2="55" stroke="black" stroke-width="1"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: parallel lines don't overlap in projection
    if test_case("parallel lines non-overlapping range",
        '''<line id="line1" x1="10" y1="50" x2="50" y2="50" stroke="black" stroke-width="1"/>
           <line id="line2" x1="60" y1="51" x2="100" y2="51" stroke="black" stroke-width="1"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: non-parallel lines close together
    if test_case("non-parallel lines close",
        '''<line id="line1" x1="10" y1="50" x2="100" y2="50" stroke="black"/>
           <line id="line2" x1="10" y1="51" x2="100" y2="60" stroke="black"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    print("\n=== Line to Box Edge ===")

    # Should trigger: horizontal line too close to box edge (1px gap, need 3px for stroke-width 1)
    if test_case("line too close to box edge",
        '''<rect id="box1" x="50" y="50" width="100" height="50"/>
           <line id="line1" x1="60" y1="49" x2="140" y2="49" stroke="black" stroke-width="1"/>''',
        expected='issues'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: line far enough from box edge (5px gap)
    if test_case("line adequate distance from box edge",
        '''<rect id="box1" x="50" y="50" width="100" height="50"/>
           <line id="line1" x1="60" y1="45" x2="140" y2="45" stroke="black" stroke-width="1"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: diagonal line near box (not parallel to edge)
    if test_case("diagonal line near box edge",
        '''<rect id="box1" x="50" y="50" width="100" height="50"/>
           <line id="line1" x1="60" y1="45" x2="140" y2="48" stroke="black"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: line doesn't overlap box in projection
    if test_case("line outside box range",
        '''<rect id="box1" x="50" y="50" width="100" height="50"/>
           <line id="line1" x1="10" y1="49" x2="40" y2="49" stroke="black" stroke-width="1"/>''',
        expected='clean'):
        passed += 1
    else:
        failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
