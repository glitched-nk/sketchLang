"""
Plotter-aware optimisation  (machine-DEPENDENT optimisation)
============================================================
Why this exists
---------------
Every optimisation in optimizer.py is machine-independent: it shrinks the IR
without changing the picture. But SketchLang's real "target machine" can also be
a physical pen plotter, where the order in which strokes are drawn matters a lot
even though it never shows in the finished image:

    * pen-UP travel      -- time spent moving between strokes without drawing
    * pen CHANGES        -- every colour switch is a manual pen swap
    * pen-DOWN distance  -- ink drawn (retraced lines are wasted)

This module is the compiler's back-end optimiser for that target. It is the
analogue of instruction scheduling / register allocation in a conventional
compiler: it never changes *what* is drawn, only the *order and direction*
in which the machine does it, and it reports the measured improvement.

Pipeline
--------
    IR --extract_strokes--> strokes --optimize_strokes--> reordered strokes
                                 |                              |
                                 +---------- pen_metrics -------+  (before / after)

A *stroke* is a maximal chain of consecutive same-colour LINEs where each
starts where the previous one ended (i.e. the pen never lifts). MOVE
instructions and colour changes end a stroke.

optimize_strokes():
    1. group strokes by colour (first-appearance order)   -> fewer pen swaps
    2. inside a group, greedy nearest-neighbour ordering   -> shorter travel
       with STROKE REVERSAL (a stroke may be drawn backwards if its far end
       is closer to the pen)
Nearest-neighbour is a classic heuristic for the travelling-salesman
problem (Rosenkrantz, Stearns & Lewis, 1977); it is O(n^2) and not optimal,
which the report states openly.

Caveat: grouping by colour can change which colour ends up on top where
differently-coloured strokes cross. SVG/PostScript output is therefore never
reordered; only the plotter (G-code) target uses this pass, and
group_colors=False limits reordering to runs of one colour.
"""

import math
from dataclasses import dataclass, field

EPS = 1e-6
MAX_STROKES_FOR_NN = 4000      # nearest-neighbour is O(n^2); above this we skip it


@dataclass
class Stroke:
    color: str
    points: list                # [(x, y), ...] with len >= 2

    @property
    def start(self):
        return self.points[0]

    @property
    def end(self):
        return self.points[-1]

    def reversed(self):
        return Stroke(self.color, list(reversed(self.points)))

    def length(self):
        return sum(math.dist(a, b) for a, b in zip(self.points, self.points[1:]))


def extract_strokes(ir):
    """Group IR LINE instructions into pen-down strokes."""
    strokes, current = [], None
    for instr in ir:
        if instr[0] == "MOVE":
            current = None
            continue
        _, x1, y1, x2, y2, color = instr
        if abs(x2 - x1) < EPS and abs(y2 - y1) < EPS:
            continue                          # zero-length line: draws nothing
        if (
            current is not None
            and current.color == color
            and abs(current.end[0] - x1) < EPS
            and abs(current.end[1] - y1) < EPS
        ):
            current.points.append((x2, y2))
        else:
            current = Stroke(color, [(x1, y1), (x2, y2)])
            strokes.append(current)
    return strokes


def pen_metrics(strokes, home=(0.0, 0.0)):
    """Machine-level cost of drawing `strokes` in the given order, starting at `home`."""
    draw = sum(s.length() for s in strokes)
    travel, pos, lifts = 0.0, home, 0
    for s in strokes:
        gap = math.dist(pos, s.start)
        travel += gap
        if gap > EPS:
            lifts += 1
        pos = s.end
    changes = sum(1 for a, b in zip(strokes, strokes[1:]) if a.color != b.color)
    return {
        "strokes": len(strokes),
        "draw_distance": round(draw, 3),
        "travel_distance": round(travel, 3),
        "pen_lifts": lifts,
        "pen_changes": changes,
    }


def _nearest_neighbour(strokes, start):
    remaining = list(strokes)
    ordered, pos = [], start
    while remaining:
        best_i, best_d, best_rev = 0, float("inf"), False
        for i, s in enumerate(remaining):
            d_start = math.dist(pos, s.start)
            d_end = math.dist(pos, s.end)
            if d_start < best_d:
                best_i, best_d, best_rev = i, d_start, False
            if d_end < best_d:
                best_i, best_d, best_rev = i, d_end, True
        s = remaining.pop(best_i)
        s = s.reversed() if best_rev else s
        ordered.append(s)
        pos = s.end
    return ordered


def optimize_strokes(strokes, group_colors=True, home=(0.0, 0.0)):
    """Return (reordered strokes, info dict). Never changes which segments are drawn."""
    info = {"skipped": False, "group_colors": group_colors}
    if len(strokes) > MAX_STROKES_FOR_NN:
        info["skipped"] = True
        return list(strokes), info

    groups = []                       # list of (color, [strokes])
    if group_colors:
        index = {}
        for s in strokes:
            if s.color not in index:
                index[s.color] = len(groups)
                groups.append((s.color, []))
            groups[index[s.color]][1].append(s)
    else:
        for s in strokes:
            if groups and groups[-1][0] == s.color:
                groups[-1][1].append(s)
            else:
                groups.append((s.color, [s]))

    result, pos = [], home
    for _color, members in groups:
        ordered = _nearest_neighbour(members, pos)
        result.extend(ordered)
        if ordered:
            pos = ordered[-1].end
    return result, info


@dataclass
class PlotterPlan:
    strokes_before: list
    strokes_after: list
    before: dict
    after: dict
    info: dict = field(default_factory=dict)

    @property
    def travel_saving_pct(self):
        b = self.before["travel_distance"]
        return 0.0 if b <= EPS else round(100.0 * (b - self.after["travel_distance"]) / b, 1)

    @property
    def pen_change_saving(self):
        return self.before["pen_changes"] - self.after["pen_changes"]

    def summary(self):
        return {
            "before": self.before,
            "after": self.after,
            "travel_saving_pct": self.travel_saving_pct,
            "pen_change_saving": self.pen_change_saving,
            "skipped": self.info.get("skipped", False),
            "group_colors": self.info.get("group_colors", True),
        }


def plan_plotter(ir, group_colors=True):
    before = extract_strokes(ir)
    after, info = optimize_strokes(before, group_colors=group_colors)
    return PlotterPlan(before, after, pen_metrics(before), pen_metrics(after), info)
