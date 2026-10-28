"""
Target Code Generation #2: PostScript
=====================================
Second back end for the same IR (the first is SVG), demonstrating that the
IR is genuinely target-independent. Output is a one-page PostScript file
sized to the drawing's bounding box. PostScript's y axis points UP while
SketchLang/SVG's points DOWN, so every y is flipped.
"""

from .codegen import MARGIN, _bounding_box
from .colors import COLOR_RGB
from .plotter import extract_strokes


def generate_ps(ir, stroke_width=2):
    min_x, min_y, max_x, max_y = _bounding_box(ir)
    width = (max_x - min_x) + 2 * MARGIN
    height = (max_y - min_y) + 2 * MARGIN
    ox, oy = MARGIN - min_x, MARGIN - min_y

    def px(x):
        return f"{x + ox:.2f}"

    def py(y):
        return f"{height - (y + oy):.2f}"

    out = [
        "%!PS-Adobe-3.0",
        f"%%BoundingBox: 0 0 {width:.0f} {height:.0f}",
        "%%Title: SketchLang output",
        "%%Creator: SketchLang compiler (PostScript back end)",
        "%%EndComments",
        "1 setlinecap 1 setlinejoin",
        f"{stroke_width} setlinewidth",
        f"1 setgray 0 0 {width:.0f} {height:.0f} rectfill",
    ]
    for s in extract_strokes(ir):
        r, g, b = COLOR_RGB[s.color]
        out.append(f"{r:.3f} {g:.3f} {b:.3f} setrgbcolor")
        out.append("newpath")
        x0, y0 = s.points[0]
        out.append(f"{px(x0)} {py(y0)} moveto")
        for x, y in s.points[1:]:
            out.append(f"{px(x)} {py(y)} lineto")
        out.append("stroke")
    out.append("showpage")
    out.append("%%EOF")
    return "\n".join(out) + "\n"
