"""
Target Code Generation
=======================
Emits SVG (the "target machine code" of this compiler) from the
optimized IR. The viewBox is computed automatically from the bounding
box of every point the program actually draws, with a fixed margin, so
that programs of very different sizes (a small square vs. a large
spiral) are always framed sensibly without the user having to guess a
canvas size up front.
"""

MARGIN = 20


def _bounding_box(ir):
    xs, ys = [0.0], [0.0]  # always include the origin, the pen's start point
    for instr in ir:
        if instr[0] == "LINE":
            _, x1, y1, x2, y2, _color = instr
            xs.extend([x1, x2])
            ys.extend([y1, y2])
        elif instr[0] == "MOVE":
            _, x, y = instr
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def generate_svg(ir, background="white", stroke_width=2):
    min_x, min_y, max_x, max_y = _bounding_box(ir)
    width = (max_x - min_x) + 2 * MARGIN
    height = (max_y - min_y) + 2 * MARGIN
    # Shift every coordinate so the drawing sits fully inside the viewBox.
    offset_x = MARGIN - min_x
    offset_y = MARGIN - min_y

    segments = []
    for instr in ir:
        if instr[0] == "LINE":
            _, x1, y1, x2, y2, color = instr
            segments.append(
                f'<line x1="{x1 + offset_x:.2f}" y1="{y1 + offset_y:.2f}" '
                f'x2="{x2 + offset_x:.2f}" y2="{y2 + offset_y:.2f}" '
                f'stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" />'
            )

    body = "\n  ".join(segments)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}">\n'
        f'  <rect width="100%" height="100%" fill="{background}" />\n'
        f'  {body}\n'
        f'</svg>'
    )
