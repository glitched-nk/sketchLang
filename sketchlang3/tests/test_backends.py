import re
import unittest

from sketchlang import compile_source
from sketchlang.codegen import generate_svg
from sketchlang.codegen_gcode import generate_gcode
from sketchlang.codegen_ps import generate_ps
from sketchlang.plotter import Stroke, extract_strokes

SQUARE = "pen red\nrepeat 4 { forward 40\n turn 90 }"


class TestSVGDegenerate(unittest.TestCase):
    def test_zero_length_line_emits_nothing(self):
        svg = generate_svg([("LINE", 3, 3, 3, 3, "red"), ("LINE", 0, 0, 5, 0, "red")])
        self.assertEqual(svg.count("<line "), 1)

    def test_canvas_ignores_moves(self):
        a = generate_svg([("LINE", 0, 0, 10, 0, "red")])
        b = generate_svg([("MOVE", 900, 900), ("LINE", 0, 0, 10, 0, "red")])
        self.assertEqual(a, b)


class TestPostScript(unittest.TestCase):
    def test_structure(self):
        ps = generate_ps(compile_source(SQUARE).ir_after_optimization)
        self.assertTrue(ps.startswith("%!PS-Adobe-3.0"))
        self.assertIn("%%BoundingBox: 0 0 80 80", ps)
        self.assertEqual(ps.count("moveto"), 1)
        self.assertEqual(ps.count("lineto"), 4)
        self.assertIn("1.000 0.000 0.000 setrgbcolor", ps)
        self.assertTrue(ps.rstrip().endswith("%%EOF"))
        self.assertIn("showpage", ps)

    def test_round_trip_geometry_matches_ir(self):
        """Parse the PostScript path back and compare it to the IR strokes (y is flipped)."""
        result = compile_source("pen blue\nforward 30\nturn 90\nforward 20\nmove 50, 50\npen red\nforward 10")
        ps = generate_ps(result.ir_after_optimization)
        height = float(re.search(r"%%BoundingBox: 0 0 \d+ (\d+)", ps).group(1))
        pts = [(float(x), float(y)) for x, y, op in re.findall(r"([-\d.]+) ([-\d.]+) (moveto|lineto)", ps)]
        strokes = extract_strokes(result.ir_after_optimization)
        expected = sum(len(s.points) for s in strokes)
        self.assertEqual(len(pts), expected)
        # relative geometry survives the y flip
        flat = [p for s in strokes for p in s.points]
        ps_dx = pts[1][0] - pts[0][0]
        ir_dx = flat[1][0] - flat[0][0]
        self.assertAlmostEqual(ps_dx, ir_dx, places=1)
        ps_dy = pts[2][1] - pts[1][1]
        ir_dy = flat[2][1] - flat[1][1]
        self.assertAlmostEqual(ps_dy, -ir_dy, places=1)       # flipped axis
        self.assertGreater(height, 0)

    def test_empty_drawing(self):
        ps = generate_ps([])
        self.assertIn("showpage", ps)


class TestGCode(unittest.TestCase):
    def test_header_and_footer(self):
        text, _ = generate_gcode([Stroke("red", [(0, 0), (10, 0)])])
        lines = text.splitlines()
        self.assertIn("G21 ; millimetres", lines)
        self.assertIn("G90 ; absolute coordinates", lines)
        self.assertTrue(lines[-1].startswith("M2"))

    def test_pen_swap_pause_per_colour_change(self):
        strokes = [Stroke("red", [(0, 0), (1, 0)]), Stroke("blue", [(1, 0), (2, 0)]), Stroke("red", [(2, 0), (3, 0)])]
        text, counts = generate_gcode(strokes)
        self.assertEqual(counts["pen_swaps"], 3)         # initial load + 2 changes
        self.assertEqual(text.count("M0 ;"), 3)

    def test_connected_strokes_do_not_lift_the_pen(self):
        strokes = [Stroke("red", [(0, 0), (5, 0)]), Stroke("red", [(5, 0), (5, 5)])]
        text, counts = generate_gcode(strokes)
        self.assertEqual(counts["travel_moves"], 0)
        self.assertEqual(text.count("G1 Z0.00"), 1)      # pen goes down once

    def test_gap_lifts_pen_and_travels(self):
        strokes = [Stroke("red", [(0, 0), (5, 0)]), Stroke("red", [(9, 9), (9, 12)])]
        text, counts = generate_gcode(strokes)
        self.assertEqual(counts["travel_moves"], 1)
        self.assertIn("G0 X9.000 Y-9.000", text)         # y flipped

    def test_no_negative_zero(self):
        text, _ = generate_gcode([Stroke("red", [(0, 0), (5, 0), (5, 5), (0, 5), (0, 1e-12)])])
        self.assertNotIn("-0.000", text)

    def test_empty_strokes(self):
        text, counts = generate_gcode([])
        self.assertEqual(counts["draw_moves"], 0)
        self.assertTrue(text.rstrip().endswith("M2 ; end of program"))

    def test_optimised_gcode_travels_less_but_draws_the_same(self):
        with open("examples/plotter_mirror.sketch") as f:
            r = compile_source(f.read())
        _, opt = r.to_gcode(optimise=True)
        _, raw = r.to_gcode(optimise=False)
        plan = r.plotter_plan()
        self.assertLess(plan.after["travel_distance"], plan.before["travel_distance"])
        self.assertEqual(opt["draw_moves"], raw["draw_moves"])      # same ink
        self.assertEqual(opt["travel_moves"], raw["travel_moves"])  # same number of pen lifts, shorter jumps


if __name__ == "__main__":
    unittest.main()
