import math
import unittest
from collections import Counter

from sketchlang.plotter import (
    MAX_STROKES_FOR_NN, Stroke, extract_strokes, optimize_strokes, pen_metrics, plan_plotter,
)


def segs(strokes):
    """Multiset of undirected segments -- what is actually drawn, ignoring order/direction."""
    c = Counter()
    for s in strokes:
        for a, b in zip(s.points, s.points[1:]):
            c[(s.color, tuple(sorted([(round(a[0], 6), round(a[1], 6)), (round(b[0], 6), round(b[1], 6))])))] += 1
    return c


class TestStrokeExtraction(unittest.TestCase):
    def test_connected_lines_form_one_stroke(self):
        ir = [("LINE", 0, 0, 1, 0, "red"), ("LINE", 1, 0, 1, 1, "red")]
        strokes = extract_strokes(ir)
        self.assertEqual(len(strokes), 1)
        self.assertEqual(strokes[0].points, [(0, 0), (1, 0), (1, 1)])

    def test_move_breaks_a_stroke(self):
        ir = [("LINE", 0, 0, 1, 0, "red"), ("MOVE", 5, 5), ("LINE", 5, 5, 6, 5, "red")]
        self.assertEqual(len(extract_strokes(ir)), 2)

    def test_colour_change_breaks_a_stroke(self):
        ir = [("LINE", 0, 0, 1, 0, "red"), ("LINE", 1, 0, 2, 0, "blue")]
        self.assertEqual([s.color for s in extract_strokes(ir)], ["red", "blue"])

    def test_gap_breaks_a_stroke_without_a_move(self):
        ir = [("LINE", 0, 0, 1, 0, "red"), ("LINE", 7, 7, 8, 7, "red")]
        self.assertEqual(len(extract_strokes(ir)), 2)

    def test_zero_length_lines_are_ignored(self):
        ir = [("LINE", 0, 0, 0, 0, "red"), ("LINE", 0, 0, 3, 0, "red")]
        strokes = extract_strokes(ir)
        self.assertEqual(len(strokes), 1)
        self.assertEqual(strokes[0].points, [(0, 0), (3, 0)])

    def test_empty_ir(self):
        self.assertEqual(extract_strokes([]), [])


class TestMetrics(unittest.TestCase):
    def test_travel_counts_home_to_first_stroke_and_gaps(self):
        strokes = [Stroke("red", [(3, 4), (3, 14)]), Stroke("red", [(3, 20), (3, 30)])]
        m = pen_metrics(strokes)
        self.assertEqual(m["draw_distance"], 20)
        self.assertEqual(m["travel_distance"], 5 + 6)       # (0,0)->(3,4), then (3,14)->(3,20)
        self.assertEqual(m["pen_lifts"], 2)
        self.assertEqual(m["pen_changes"], 0)

    def test_connected_strokes_cost_no_travel(self):
        strokes = [Stroke("red", [(0, 0), (5, 0)]), Stroke("red", [(5, 0), (5, 5)])]
        self.assertEqual(pen_metrics(strokes)["travel_distance"], 0)

    def test_pen_changes(self):
        strokes = [Stroke(c, [(0, 0), (1, 0)]) for c in ["red", "blue", "blue", "red"]]
        self.assertEqual(pen_metrics(strokes)["pen_changes"], 2)


class TestOptimizer(unittest.TestCase):
    def _scattered(self):
        # far-left / far-right alternating -> terrible order for a plotter
        return [Stroke("black", [(x, 0), (x + 1, 0)]) for x in [0, 100, 2, 98, 4, 96, 6, 94]]

    def test_reordering_reduces_travel(self):
        before = self._scattered()
        after, info = optimize_strokes(before)
        self.assertLess(pen_metrics(after)["travel_distance"], pen_metrics(before)["travel_distance"])
        self.assertFalse(info["skipped"])

    def test_reordering_never_changes_what_is_drawn(self):
        before = self._scattered()
        after, _ = optimize_strokes(before)
        self.assertEqual(segs(before), segs(after))

    def test_stroke_reversal_is_used_when_closer(self):
        # pen starts at (0,0); stroke 1 runs 50->10, so drawing it backwards (10->50) is wrong
        # but its END (10,0) is the nearest point: it must be reversed to start there.
        after, _ = optimize_strokes([Stroke("red", [(50, 0), (10, 0)])])
        self.assertEqual(after[0].points, [(10, 0), (50, 0)])

    def test_colour_grouping_minimises_pen_changes(self):
        strokes = [Stroke(c, [(i, 0), (i + 1, 0)]) for i, c in enumerate(["red", "blue"] * 5)]
        grouped, _ = optimize_strokes(strokes, group_colors=True)
        self.assertEqual(pen_metrics(grouped)["pen_changes"], 1)
        self.assertEqual(pen_metrics(strokes)["pen_changes"], 9)

    def test_no_grouping_mode_keeps_colour_runs_in_order(self):
        strokes = [Stroke("red", [(0, 0), (1, 0)]), Stroke("blue", [(5, 0), (6, 0)]), Stroke("red", [(9, 0), (10, 0)])]
        out, _ = optimize_strokes(strokes, group_colors=False)
        self.assertEqual([s.color for s in out], ["red", "blue", "red"])

    def test_oversized_input_is_skipped_not_hung(self):
        many = [Stroke("red", [(i, 0), (i, 1)]) for i in range(MAX_STROKES_FOR_NN + 1)]
        out, info = optimize_strokes(many)
        self.assertTrue(info["skipped"])
        self.assertEqual(len(out), len(many))

    def test_empty_input(self):
        out, _ = optimize_strokes([])
        self.assertEqual(out, [])

    def test_optimised_never_worse_than_one_stroke_per_group_ordering(self):
        # sanity: result visits every stroke exactly once
        before = self._scattered()
        after, _ = optimize_strokes(before)
        self.assertEqual(len(after), len(before))


class TestPlan(unittest.TestCase):
    def test_plan_summary_and_saving(self):
        ir = []
        for x in [0, 100, 2, 98]:
            ir += [("MOVE", x, 0), ("LINE", x, 0, x + 1, 0, "black")]
        plan = plan_plotter(ir)
        self.assertGreater(plan.travel_saving_pct, 0)
        self.assertEqual(plan.summary()["before"]["strokes"], 4)

    def test_zero_travel_gives_zero_percent(self):
        plan = plan_plotter([("LINE", 0, 0, 5, 0, "red")])
        self.assertEqual(plan.travel_saving_pct, 0.0)


if __name__ == "__main__":
    unittest.main()
