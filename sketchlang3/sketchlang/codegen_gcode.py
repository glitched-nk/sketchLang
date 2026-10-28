"""
Target Code Generation #3: G-code for a pen plotter
===================================================
Emits a generic G-code program (RS-274 style, as used by GRBL/Marlin-type
controllers) for a Z-axis pen plotter:

    G21 / G90         millimetres, absolute coordinates
    G0 Z<up>          pen up            G1 Z<down> F<f>   pen down
    G0 X Y            rapid travel (pen up)
    G1 X Y F<feed>    draw
    M0 (...)          pause so the operator can swap the pen colour

1 SketchLang unit = 1 mm. G-code's Y axis points UP, SketchLang's points DOWN,
so Y is negated. The pen is only lifted when the next stroke does not start
exactly where the pen already is, so a good stroke order (see plotter.py)
directly removes G0 moves from this file.
"""

import math

EPS = 1e-6


def generate_gcode(strokes, feed_draw=1500, feed_travel=6000, pen_up=3.0, pen_down=0.0):
    lines = [
        "; SketchLang -> G-code (generic Z-axis pen plotter)",
        "; 1 unit = 1 mm, Y axis flipped relative to the SVG preview",
        "G21 ; millimetres",
        "G90 ; absolute coordinates",
        f"G0 Z{pen_up:.2f} ; pen up",
        "G0 X0.000 Y0.000",
    ]
    pos, pen_is_down, color = (0.0, 0.0), False, None
    counts = {"travel_moves": 0, "draw_moves": 0, "pen_swaps": 0}

    def xy(p):
        # round first and add 0.0 so that tiny negatives never print as "-0.000"
        return f"X{round(p[0], 3) + 0.0:.3f} Y{round(-p[1], 3) + 0.0:.3f}"

    for s in strokes:
        if s.color != color:
            if pen_is_down:
                lines.append(f"G0 Z{pen_up:.2f}")
                pen_is_down = False
            lines.append(f"M0 ; change pen -> {s.color}")
            counts["pen_swaps"] += 1
            color = s.color
        if math.dist(pos, s.start) > EPS:
            if pen_is_down:
                lines.append(f"G0 Z{pen_up:.2f}")
                pen_is_down = False
            lines.append(f"G0 {xy(s.start)} F{feed_travel}")
            counts["travel_moves"] += 1
            pos = s.start
        if not pen_is_down:
            lines.append(f"G1 Z{pen_down:.2f} F500")
            pen_is_down = True
        for p in s.points[1:]:
            lines.append(f"G1 {xy(p)} F{feed_draw}")
            counts["draw_moves"] += 1
        pos = s.end
    if pen_is_down:
        lines.append(f"G0 Z{pen_up:.2f}")
    lines.append("G0 X0.000 Y0.000 ; home")
    lines.append("M2 ; end of program")
    return "\n".join(lines) + "\n", counts
