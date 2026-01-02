#!/usr/bin/env python3
"""Measure text dimensions using Cairo."""

import cairocffi as cairo


def measure_text(text: str, font_family: str, font_size: float) -> tuple:
    """
    Measure text width and height using Cairo.
    Returns (width, height, ascent, descent).
    """
    # Create a dummy surface just for measuring
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(surface)

    # Set font
    ctx.select_font_face(font_family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(font_size)

    # Get text extents
    # text_extents returns: (x_bearing, y_bearing, width, height, x_advance, y_advance)
    extents = ctx.text_extents(text)
    # font_extents returns: (ascent, descent, height, max_x_advance, max_y_advance)
    font_extents = ctx.font_extents()

    width = extents[2]  # width
    height = font_extents[2]  # height
    ascent = font_extents[0]  # ascent
    descent = font_extents[1]  # descent

    return width, height, ascent, descent


def measure_text_bbox(text: str, x: float, y: float, font_family: str, font_size: float, anchor: str) -> tuple:
    """
    Get bounding box for text at position (x, y).
    anchor is 'start', 'middle', or 'end' (SVG text-anchor values).
    Returns (x_min, y_min, x_max, y_max).
    """
    width, height, ascent, descent = measure_text(text, font_family, font_size)

    # Adjust x based on anchor
    if anchor == 'middle':
        x_min = x - width / 2
    elif anchor == 'end':
        x_min = x - width
    else:  # 'start' or default
        x_min = x

    x_max = x_min + width

    # y in SVG is the baseline, text extends up (ascent) and down (descent)
    y_min = y - ascent
    y_max = y + descent

    return x_min, y_min, x_max, y_max
