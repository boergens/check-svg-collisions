#!/usr/bin/env python3
"""Get figure improvement suggestions from Gemini."""

import os
import sys
import base64
import cairosvg
from google import genai


def svg_to_png(svg_path: str, png_path: str) -> bytes:
    """Convert SVG file to PNG and save it."""
    png_bytes = cairosvg.svg2png(url=svg_path, scale=2.0)
    with open(png_path, 'wb') as f:
        f.write(png_bytes)
    return png_bytes


def get_feedback(svg_path: str, api_key: str, model: str = "gemini-3-pro-preview") -> str:
    """
    Send SVG figure to Gemini and get improvement suggestions.

    Args:
        svg_path: Path to SVG file
        api_key: Gemini API key
        model: Model to use (default: gemini-3-pro-preview)

    Returns:
        Feedback text from Gemini
    """
    client = genai.Client(api_key=api_key)

    # Convert SVG to PNG for vision input
    png_path = svg_path.rsplit('.', 1)[0] + '.png'
    png_bytes = svg_to_png(svg_path, png_path)
    print(f"Created {os.path.basename(png_path)}")

    prompt = "Give me frank feedback on this technical drawing."

    # Base64 encode the PNG for the API
    png_base64 = base64.b64encode(png_bytes).decode('utf-8')

    response = client.models.generate_content(
        model=model,
        contents=[
            {
                "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": png_base64}},
                    {"text": prompt}
                ]
            }
        ]
    )

    return response.text


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        print("Get an API key at: https://aistudio.google.com/apikey")
        return 1

    if len(sys.argv) < 2:
        print("Usage: gemini_feedback.py <svg_file> [model]")
        print("\nModels: gemini-3-pro-preview (default), gemini-2.5-pro, gemini-2.5-flash")
        return 1

    svg_path = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "gemini-3-pro-preview"

    if not os.path.exists(svg_path):
        print(f"Error: File not found: {svg_path}")
        return 1

    print(f"Analyzing {os.path.basename(svg_path)} with {model}...\n")

    feedback = get_feedback(svg_path, api_key, model)
    print(feedback)

    return 0


if __name__ == "__main__":
    sys.exit(main())
