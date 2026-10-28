"""
Code Optimization (machine-independent)
=======================================
Four small passes over the flat IR list. Each one is *geometry-preserving*:
the set of pixels that receive ink is identical to what the unoptimised IR
gives (verified by rasterising both for every example, see test_integration).
The one visible side effect is anti-aliasing: a retraced edge was composited
twice, so after removing the duplicate its semi-transparent edge pixels are
slightly lighter (at most ~25% in our measurements). Zero-length lines are
defined to draw nothing in every back end.

1. remove_zero_length_lines   ("forward 0" draws nothing)
2. eliminate_duplicate_segments
      A LINE that exactly retraces an earlier same-colour segment (in either
      direction) adds no ink. Safe only if nothing of a DIFFERENT colour was
      drawn in between (otherwise repainting would change which colour is on
      top at a crossing), so the "seen" set is cleared whenever the colour
      changes.
3. eliminate_dead_moves       (a MOVE immediately overwritten by another MOVE)
4. merge_collinear_lines
      Two consecutive same-colour LINEs that share an endpoint, lie on one
      straight line AND continue in the SAME direction become one LINE.
      (Phase 2 omitted the direction test, so  forward 100 / forward -50
      was wrongly merged into a 50-unit line; found during Phase 3 boundary
      testing and fixed here -- see test_optimizer.py.)

optimize_ir_with_report() also returns, per pass, the instruction count before
and after so the UI / report can show what each pass achieved.
"""

EPS = 1e-6


def remove_zero_length_lines(ir):
    return [i for i in ir if not (i[0] == "LINE" and abs(i[3] - i[1]) < EPS and abs(i[4] - i[2]) < EPS)]


def _segment_key(x1, y1, x2, y2, color):
    a = (round(x1, 6) + 0.0, round(y1, 6) + 0.0)   # '+ 0.0' normalises -0.0
    b = (round(x2, 6) + 0.0, round(y2, 6) + 0.0)
    return (min(a, b), max(a, b), color)


def eliminate_duplicate_segments(ir):
    out, seen, last_color = [], set(), None
    for instr in ir:
        if instr[0] != "LINE":
            out.append(instr)
            continue
        _, x1, y1, x2, y2, color = instr
        if color != last_color:
            seen.clear()
            last_color = color
        key = _segment_key(x1, y1, x2, y2, color)
        if key in seen:
            continue
        seen.add(key)
        out.append(instr)
    return out


def eliminate_dead_moves(ir):
    """Drop a MOVE that is immediately overwritten by a later MOVE."""
    if not ir:
        return ir
    optimized = [ir[0]]
    for instr in ir[1:]:
        if instr[0] == "MOVE" and optimized[-1][0] == "MOVE":
            optimized[-1] = instr
        else:
            optimized.append(instr)
    return optimized


def _collinear(x1, y1, x2, y2, x3, y3, eps=1e-6):
    cross = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
    return abs(cross) < eps


def _same_direction(x1, y1, x2, y2, x3, y3):
    """True if p1->p2 and p2->p3 point the same way (dot product > 0)."""
    return (x2 - x1) * (x3 - x2) + (y2 - y1) * (y3 - y2) > 0


def merge_collinear_lines(ir):
    if not ir:
        return ir
    optimized = [ir[0]]
    for instr in ir[1:]:
        prev = optimized[-1]
        if (
            instr[0] == "LINE"
            and prev[0] == "LINE"
            and instr[5] == prev[5]
            and abs(prev[3] - instr[1]) < EPS and abs(prev[4] - instr[2]) < EPS
            and _collinear(prev[1], prev[2], prev[3], prev[4], instr[3], instr[4])
            and _same_direction(prev[1], prev[2], prev[3], prev[4], instr[3], instr[4])
        ):
            optimized[-1] = ("LINE", prev[1], prev[2], instr[3], instr[4], prev[5])
        else:
            optimized.append(instr)
    return optimized


PASSES = [
    ("zero-length lines", remove_zero_length_lines),
    ("duplicate segments", eliminate_duplicate_segments),
    ("dead moves", eliminate_dead_moves),
    ("collinear merge", merge_collinear_lines),
]


def optimize_ir_with_report(ir):
    """Run every pass in order. Returns (optimized_ir, [{pass, before, after}, ...])."""
    report = []
    for name, fn in PASSES:
        before = len(ir)
        ir = fn(ir)
        report.append({"pass": name, "before": before, "after": len(ir)})
    return ir, report


def optimize_ir(ir):
    return optimize_ir_with_report(ir)[0]
