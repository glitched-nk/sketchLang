import glob
import io
import os
import unittest

from sketchlang import compile_source, error_info, LexError, ParseError, SemanticError, SketchRuntimeError

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")


def read_example(name):
    with open(os.path.join(EXAMPLES_DIR, name)) as f:
        return f.read()


class TestFullPipelineOnExamplePrograms(unittest.TestCase):
    def test_square_compiles_and_returns_to_start(self):
        result = compile_source(read_example("square.sketch"))
        self.assertIn("<svg", result.svg)
        self.assertGreater(len(result.ir_after_optimization), 0)

    def test_variables_example_uses_symbol_table(self):
        result = compile_source(read_example("variables.sketch"))
        self.assertEqual(result.symbol_table.lookup("side"), 80.0)
        self.assertEqual(result.symbol_table.lookup("bigSide"), 160.0)

    def test_spiral_example_grows_each_iteration(self):
        result = compile_source(read_example("spiral.sketch"))
        # 40 repeat iterations, one LINE instruction each, none collinear
        # enough with a changing turn to be merged away.
        self.assertEqual(len(result.ir_before_optimization), 40)

    def test_dead_code_demo_is_actually_optimized(self):
        result = compile_source(read_example("dead_code_demo.sketch"))
        self.assertLess(len(result.ir_after_optimization), len(result.ir_before_optimization))

    def test_undefined_variable_example_raises_semantic_error(self):
        with self.assertRaises(SemanticError):
            compile_source(read_example("error_undefined_var.sketch"))

    def test_bad_repeat_example_raises_semantic_error(self):
        with self.assertRaises(SemanticError):
            compile_source(read_example("error_bad_repeat.sketch"))

    def test_div_zero_example_raises_semantic_error(self):
        with self.assertRaises(SemanticError):
            compile_source(read_example("error_div_zero.sketch"))


class TestErrorPropagation(unittest.TestCase):
    def test_lexical_error_stops_the_pipeline(self):
        with self.assertRaises(LexError):
            compile_source("pen red\nforward @@10")

    def test_syntax_error_stops_the_pipeline(self):
        with self.assertRaises(ParseError):
            compile_source("move 10 20")  # missing comma

    def test_semantic_error_prevents_ir_generation(self):
        # A program that is syntactically valid but semantically invalid
        # must fail before any SVG is produced.
        with self.assertRaises(SemanticError):
            compile_source("pen notacolor\nforward 10")


# --------------------------------------------------------------------------
# Phase 3 additions
# --------------------------------------------------------------------------

ERROR_EXAMPLES = {
    "error_lex_char.sketch": (LexError, "lexical"),
    "error_syntax_brace.sketch": (ParseError, "syntax"),
    "error_undefined_var.sketch": (SemanticError, "semantic"),
    "error_bad_repeat.sketch": (SemanticError, "semantic"),
    "error_div_zero.sketch": (SemanticError, "semantic"),
    "error_undefined_proc.sketch": (SemanticError, "semantic"),
    "error_arg_count.sketch": (SemanticError, "semantic"),
    "error_scope.sketch": (SemanticError, "semantic"),
    "error_runtime_recursion.sketch": (SketchRuntimeError, "runtime"),
    "error_runtime_div.sketch": (SketchRuntimeError, "runtime"),
}


class TestErrorExampleMatrix(unittest.TestCase):
    def test_every_error_example_fails_in_the_expected_stage(self):
        for name, (exc_type, stage) in ERROR_EXAMPLES.items():
            with self.subTest(example=name):
                with self.assertRaises(exc_type) as ctx:
                    compile_source(read_example(name))
                info = error_info(ctx.exception)
                self.assertEqual(info["stage"], stage)
                self.assertIsNotNone(info["line"], "error message should name a line")

    def test_error_examples_directory_is_fully_covered(self):
        on_disk = {os.path.basename(p) for p in glob.glob(os.path.join(EXAMPLES_DIR, "error_*.sketch"))}
        self.assertEqual(on_disk, set(ERROR_EXAMPLES))


class TestNewValidExamples(unittest.TestCase):
    def test_procedures_flower(self):
        r = compile_source(read_example("procedures.sketch"))
        self.assertEqual(r.run_stats["calls"], 12 * 3)          # petal + 2 arc_side per petal
        self.assertEqual(len(r.ir_before_optimization), 12 * 12)

    def test_koch_uses_recursion_depth_4(self):
        r = compile_source(read_example("koch.sketch"))
        self.assertEqual(r.run_stats["max_depth"], 4)

    def test_tree_retrace_is_removed_by_optimiser(self):
        r = compile_source(read_example("tree.sketch"))
        self.assertEqual(len(r.ir_after_optimization) * 2, len(r.ir_before_optimization))

    def test_plotter_mirror_saves_travel(self):
        plan = compile_source(read_example("plotter_mirror.sketch")).plotter_plan()
        self.assertGreater(plan.travel_saving_pct, 80)

    def test_plotter_checker_collapses_pen_changes(self):
        plan = compile_source(read_example("plotter_checker.sketch")).plotter_plan()
        self.assertEqual(plan.after["pen_changes"], 1)
        self.assertGreaterEqual(plan.before["pen_changes"], 30)


class TestEveryExampleThroughEveryBackend(unittest.TestCase):
    def test_all_valid_examples_compile_to_svg_ps_gcode(self):
        for path in sorted(glob.glob(os.path.join(EXAMPLES_DIR, "*.sketch"))):
            name = os.path.basename(path)
            if name.startswith("error_"):
                continue
            with self.subTest(example=name):
                r = compile_source(read_example(name))
                self.assertIn("</svg>", r.svg)
                self.assertIn("showpage", r.to_postscript())
                text, _ = r.to_gcode()
                self.assertTrue(text.rstrip().endswith("M2 ; end of program"))

    def test_plotter_reordering_preserves_drawn_segments_on_every_example(self):
        from test_plotter import segs
        for path in sorted(glob.glob(os.path.join(EXAMPLES_DIR, "*.sketch"))):
            name = os.path.basename(path)
            if name.startswith("error_"):
                continue
            with self.subTest(example=name):
                plan = compile_source(read_example(name)).plotter_plan()
                self.assertEqual(segs(plan.strokes_before), segs(plan.strokes_after))


try:
    import cairosvg
    from PIL import Image
except ImportError:                                      # pragma: no cover
    cairosvg = None


@unittest.skipIf(cairosvg is None, "cairosvg/Pillow not installed")
class TestOptimiserPreservesGeometry(unittest.TestCase):
    """Rasterise the unoptimised and optimised IR and compare WHICH pixels get ink."""

    @staticmethod
    def ink_mask(ir):
        from sketchlang.codegen import generate_svg
        png = cairosvg.svg2png(bytestring=generate_svg(ir).encode(), output_width=500)
        img = Image.open(io.BytesIO(png)).convert("RGB")
        return [px != (255, 255, 255) for px in img.getdata()], img.size

    def test_ink_mask_identical_for_every_example(self):
        for path in sorted(glob.glob(os.path.join(EXAMPLES_DIR, "*.sketch"))):
            name = os.path.basename(path)
            if name.startswith("error_"):
                continue
            with self.subTest(example=name):
                r = compile_source(read_example(name))
                before, size_b = self.ink_mask(r.ir_before_optimization)
                after, size_a = self.ink_mask(r.ir_after_optimization)
                self.assertEqual(size_b, size_a)
                self.assertEqual(before, after)

    def test_regression_backtracking_keeps_both_halves_of_the_stroke(self):
        # Phase 2 bug: "forward 100; forward -50" was merged into a 50-unit line.
        r = compile_source("pen red\nforward 100\nforward -50")
        self.assertEqual(len(r.ir_after_optimization), 2)
        mask, _ = self.ink_mask(r.ir_after_optimization)
        self.assertGreater(sum(mask), 0)


if __name__ == "__main__":
    unittest.main()
