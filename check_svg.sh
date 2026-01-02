#!/bin/bash
# Run SVG collision checker with proper environment
cd "$(dirname "$0")"
source venv/bin/activate
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/cairo/lib
python check_svg_collisions.py "$@"
