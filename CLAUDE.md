# SVG Collision Checker

Checks SVG figures for problematic element interactions like overlapping text, text crossing box borders, and overlapping boxes. Also provides AI-powered feedback via Gemini.

## Setup

Requires Python 3.12 and Cairo library:
```bash
brew install cairo
python3.12 -m venv venv
source venv/bin/activate
pip install cairocffi pillow google-genai cairosvg
```

## Usage

### Collision Detection
```bash
./check_svg.sh file.svg [file2.svg ...]
./check_svg.sh -v file.svg              # verbose mode (show element counts)
```

### AI Feedback (Gemini)
```bash
export GEMINI_API_KEY="your-api-key"    # get at https://aistudio.google.com/apikey
./gemini_feedback.sh file.svg           # uses gemini-3-pro-preview
./gemini_feedback.sh file.svg gemini-2.5-flash  # use different model
```

## Collision Rules

1. **Text ↔ Text**: No overlap allowed
2. **Text ↔ Line**: Lines must not pass through text
3. **Text ↔ Box**: Text must be fully inside or fully outside (no border crossing)
4. **Box ↔ Box**: No overlap unless one fully contains the other
5. **Line ↔ Box**: Lines must not pass through boxes (connecting to box edge is OK)
   - Corner touches generate warnings (not errors)

## Element IDs

For better error messages, all SVG elements (rect, line, path, polygon, text) should have `id` attributes. The checker warns about missing IDs with line numbers:

```
<rect> at line 42 has no id, temporarily named 'elem_12'
```

Elements inside `<defs>` (markers, gradients, etc.) are excluded from this check.

## Testing

```bash
source venv/bin/activate
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/cairo/lib
python test_collisions.py
```

16 test cases covering all collision rules with expected issue/warning/clean outcomes.

## Files

- `check_svg_collisions.py` - Main collision detection logic
- `measure_text.py` - Cairo-based text dimension measurement
- `check_svg.sh` - Wrapper script that sets up environment
- `gemini_feedback.py` - Gemini API integration for figure feedback
- `gemini_feedback.sh` - Wrapper script for Gemini feedback
- `test_collisions.py` - Test suite for collision detection
