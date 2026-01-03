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


def test_case(name: str, svg_content: str, should_have_issues: bool):
    """Run a test case and print result."""
    path = write_svg(svg_content)
    result = check_file(path)
    os.unlink(path)

    has_issues = len(result['issues']) > 0
    passed = has_issues == should_have_issues

    status = "PASS" if passed else "FAIL"
    issue_str = f" ({len(result['issues'])} issues)" if has_issues else ""
    expected = "issues" if should_have_issues else "no issues"

    print(f"  {status}: {name} - expected {expected}{issue_str}")
    if not passed:
        for issue in result['issues']:
            print(f"        {issue}")
    return passed


def main():
    passed = 0
    failed = 0

    print("\n=== Text ↔ Text ===")

    # Should trigger: overlapping text
    if test_case("overlapping text",
        '''<text x="50" y="50" font-size="20">Hello</text>
           <text x="60" y="50" font-size="20">World</text>''',
        should_have_issues=True):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: separate text
    if test_case("separate text",
        '''<text x="10" y="50" font-size="12">Hello</text>
           <text x="100" y="50" font-size="12">World</text>''',
        should_have_issues=False):
        passed += 1
    else:
        failed += 1

    print("\n=== Text ↔ Line ===")

    # Should trigger: line through text
    if test_case("line through text",
        '''<text x="50" y="50" font-size="20">Hello</text>
           <line x1="0" y1="50" x2="200" y2="50" stroke="black"/>''',
        should_have_issues=True):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: line misses text
    if test_case("line misses text",
        '''<text x="50" y="50" font-size="12">Hello</text>
           <line x1="0" y1="100" x2="200" y2="100" stroke="black"/>''',
        should_have_issues=False):
        passed += 1
    else:
        failed += 1

    print("\n=== Text ↔ Box ===")

    # Should trigger: text crosses box border
    if test_case("text crosses box border",
        '''<rect x="50" y="30" width="50" height="50"/>
           <text x="40" y="50" font-size="20">Hello</text>''',
        should_have_issues=True):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: text fully inside box
    if test_case("text inside box",
        '''<rect x="10" y="10" width="180" height="180"/>
           <text x="50" y="100" font-size="12">Hello</text>''',
        should_have_issues=False):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: text fully outside box
    if test_case("text outside box",
        '''<rect x="100" y="100" width="50" height="50"/>
           <text x="10" y="50" font-size="12">Hello</text>''',
        should_have_issues=False):
        passed += 1
    else:
        failed += 1

    print("\n=== Box ↔ Box ===")

    # Should trigger: overlapping boxes (no containment)
    if test_case("overlapping boxes",
        '''<rect x="10" y="10" width="80" height="80"/>
           <rect x="50" y="50" width="80" height="80"/>''',
        should_have_issues=True):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: one box contains other
    if test_case("nested boxes (containment)",
        '''<rect x="10" y="10" width="180" height="180"/>
           <rect x="50" y="50" width="50" height="50"/>''',
        should_have_issues=False):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: separate boxes
    if test_case("separate boxes",
        '''<rect x="10" y="10" width="40" height="40"/>
           <rect x="100" y="100" width="40" height="40"/>''',
        should_have_issues=False):
        passed += 1
    else:
        failed += 1

    print("\n=== Line ↔ Box ===")

    # Should trigger: line passes through box (both endpoints outside)
    if test_case("line passes through box",
        '''<rect x="50" y="50" width="50" height="50"/>
           <line x1="0" y1="75" x2="200" y2="75" stroke="black"/>''',
        should_have_issues=True):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: line misses box
    if test_case("line misses box",
        '''<rect x="50" y="50" width="50" height="50"/>
           <line x1="0" y1="10" x2="200" y2="10" stroke="black"/>''',
        should_have_issues=False):
        passed += 1
    else:
        failed += 1

    # Should NOT trigger: line connects to box edge
    if test_case("line connects to box edge",
        '''<rect x="50" y="50" width="50" height="50"/>
           <line x1="0" y1="75" x2="50" y2="75" stroke="black"/>''',
        should_have_issues=False):
        passed += 1
    else:
        failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
