#!/bin/bash
# Get figure improvement suggestions from Gemini
cd "$(dirname "$0")"
source venv/bin/activate
export DYLD_LIBRARY_PATH=/opt/homebrew/opt/cairo/lib
if [ -f .env ]; then
    export $(cat .env | xargs)
fi
python gemini_feedback.py "$@"
