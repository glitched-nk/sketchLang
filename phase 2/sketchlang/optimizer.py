"""
Code Optimization
=================
Two small, independent peephole-style passes over the flat IR list.
Both are safe: neither changes the picture the program produces, only
how many instructions it takes to produce it.

1. eliminate_dead_moves
   A MOVE instruction that is immediately followed by another MOVE is
   dead code -- only the pen's final position before the next LINE
   matters, so the earlier MOVE can be dropped.

2. merge_collinear_lines
   Two consecutive LINE instructions of the same color, where the first
   segment's endpoint is the second segment's start point, and all three
   points are collinear, are really one longer straight segment. They are
   merged into a single LINE instruction.

optimize_ir() runs dead-move elimination first (it can only reduce the
instruction count) and then collinear-line merging.
"""


def eliminate_dead_moves(ir):
    """Drop a MOVE that is immediately overwritten by a later MOVE."""
    if not ir:
        return ir
    optimized = [ir[0]]
    for instr in ir[1:]:
        if instr[0] == "MOVE" and optimized[-1][0] == "MOVE":
            optimized[-1] = instr  # the earlier MOVE never mattered
        else:
            optimized.append(instr)
    return optimized


def _collinear(x1, y1, x2, y2, x3, y3, eps=1e-6):
    cross = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
    return abs(cross) < eps


def merge_collinear_lines(ir):
    """Merge consecutive same-color, collinear, end-to-start LINE instructions."""
    if not ir:
        return ir
    optimized = [ir[0]]
    for instr in ir[1:]:
        prev = optimized[-1]
        if (
            instr[0] == "LINE"
            and prev[0] == "LINE"
            and instr[5] == prev[5]                              # same color
            and (prev[3], prev[4]) == (instr[1], instr[2])       # prev end == this start
            and _collinear(prev[1], prev[2], prev[3], prev[4], instr[3], instr[4])
        ):
            optimized[-1] = ("LINE", prev[1], prev[2], instr[3], instr[4], prev[5])
        else:
            optimized.append(instr)
    return optimized


def optimize_ir(ir):
    return merge_collinear_lines(eliminate_dead_moves(ir))
