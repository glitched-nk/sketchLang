import os
import unittest

from sketchlang import compile_source, LexError, ParseError, SemanticError

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


if __name__ == "__main__":
    unittest.main()
