"""Run-time evaluation of every comparison operator (if-conditions), including the
floating-point tolerance rules in ir.compare()."""
import unittest

from sketchlang import compile_source
from sketchlang.ir import SketchRuntimeError, compare, generate_ir
from sketchlang.lexer import tokenize
from sketchlang.parser import parse


def branch_taken(a, op, b):
    """Compile `if a OP b { forward 1 } else { forward 2 }` and report which branch ran."""
    r = compile_source(f"let a = {a}\nlet b = {b}\nif a {op} b {{ forward 1 }} else {{ forward 2 }}")
    first = r.ir_before_optimization[0]
    return "then" if abs(first[3] - first[1]) == 1 else "else"


class TestEveryOperatorAtRunTime(unittest.TestCase):
    CASES = [
        # (a, op, b, expected branch)
        (2, "==", 2, "then"), (2, "==", 3, "else"),
        (2, "!=", 3, "then"), (2, "!=", 2, "else"),
        (2, "<", 3, "then"), (3, "<", 2, "else"), (2, "<", 2, "else"),
        (3, ">", 2, "then"), (2, ">", 3, "else"), (2, ">", 2, "else"),
        (2, "<=", 3, "then"), (2, "<=", 2, "then"), (3, "<=", 2, "else"),
        (3, ">=", 2, "then"), (2, ">=", 2, "then"), (2, ">=", 3, "else"),
    ]

    def test_all_operators(self):
        for a, op, b, expected in self.CASES:
            with self.subTest(expr=f"{a} {op} {b}"):
                self.assertEqual(branch_taken(a, op, b), expected)

    def test_negative_and_fractional_operands(self):
        self.assertEqual(branch_taken(-2, "<", -1), "then")
        self.assertEqual(branch_taken(0.5, ">=", 0.25), "then")

    def test_unknown_operator_is_a_runtime_error(self):
        with self.assertRaises(SketchRuntimeError):
            compare("??", 1, 2)


class TestFloatingPointTolerance(unittest.TestCase):
    A, B = 0.3, 0.1 + 0.2          # differ by about 5.5e-17

    def test_nearly_equal_numbers_are_equal(self):
        self.assertTrue(compare("==", self.A, self.B))
        self.assertFalse(compare("!=", self.A, self.B))

    def test_nearly_equal_numbers_are_not_strictly_ordered(self):
        # Phase 3 regression: '<' used to be exact, so 0.3 == 0.1+0.2 AND 0.3 < 0.1+0.2.
        self.assertFalse(compare("<", self.A, self.B))
        self.assertFalse(compare(">", self.A, self.B))
        self.assertFalse(compare("<", self.B, self.A))
        self.assertFalse(compare(">", self.B, self.A))

    def test_non_strict_operators_accept_nearly_equal(self):
        self.assertTrue(compare("<=", self.A, self.B))
        self.assertTrue(compare(">=", self.A, self.B))

    def test_exactly_one_of_less_equal_greater_holds(self):
        values = [0, 1, -1, 0.3, 0.1 + 0.2, 1e-10, 2e-9, 1e9, 1e9 + 1e-7]
        for x in values:
            for y in values:
                with self.subTest(x=x, y=y):
                    holds = [compare("<", x, y), compare("==", x, y), compare(">", x, y)]
                    self.assertEqual(sum(holds), 1)

    def test_accumulated_loop_value_compares_equal(self):
        # 0.1 added ten times is 0.9999999999999999, not 1.0; the program should still see 1.
        src = "let x = 0\nrepeat 10 { let x = x + 0.1 }\nif x == 1 { forward 1 } else { forward 2 }"
        r = compile_source(src)
        self.assertEqual(r.ir_before_optimization[0][3], 1.0)


class TestRuntimeUndefinedVariable(unittest.TestCase):
    def test_executor_rejects_an_undeclared_variable_even_if_semantic_analysis_was_skipped(self):
        ast = parse(tokenize("forward ghost"))      # deliberately not analysed
        with self.assertRaises(SketchRuntimeError) as ctx:
            generate_ir(ast)
        self.assertIn("'ghost'", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
