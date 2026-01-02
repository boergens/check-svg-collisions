# SVG Collision Checker

Checks SVG figures for problematic element interactions like overlapping text, text crossing box borders, and overlapping boxes.

## Setup

Requires Python 3.12 and Cairo library:
```bash
brew install cairo
python3.12 -m venv venv
source venv/bin/activate
pip install cairocffi pillow
```

## Usage

```bash
./check_svg.sh file.svg [file2.svg ...]
./check_svg.sh -v file.svg              # verbose mode (show element counts)
```

## Collision Rules

1. **Text ↔ Text**: No overlap allowed
2. **Text ↔ Box**: Text must be fully inside or fully outside (no border crossing)
3. **Box ↔ Box**: No overlap unless one fully contains the other

## Files

- `check_svg_collisions.py` - Main collision detection logic
- `measure_text.py` - Cairo-based text dimension measurement
- `check_svg.sh` - Wrapper script that sets up environment
