import unittest

from sketchlang.lexer import tokenize
from sketchlang.parser import parse
from sketchlang.semantics import check_semantics, SemanticError


def check(source):
    return check_semantics(parse(tokenize(source)))


class TestSemantics(unittest.TestCase):
    def test_valid_program_passes(self):
        symtab = check("let side = 50\npen blue\nrepeat 4 {\n forward side\n turn 90\n}")
        self.assertEqual(symtab.lookup("side"), 50.0)

    def test_unknown_color_is_rejected(self):
        with self.assertRaises(SemanticError) as ctx:
            check("pen skyblue\nforward 10")
        self.assertIn("unknown color", str(ctx.exception))

    def test_undefined_variable_is_rejected(self):
        with self.assertRaises(SemanticError) as ctx:
            check("pen red\nforward radius")
        self.assertIn("used before it is declared", str(ctx.exception))

    def test_variable_usable_after_declaration(self):
        symtab = check("let radius = 20\npen red\nforward radius")
        self.assertEqual(symtab.lookup("radius"), 20.0)

    def test_repeat_count_must_be_positive(self):
        with self.assertRaises(SemanticError) as ctx:
            check("repeat -3 {\n forward 10\n}")
        self.assertIn("positive whole number", str(ctx.exception))

    def test_repeat_count_must_be_whole_number(self):
        with self.assertRaises(SemanticError):
            check("repeat 2.5 {\n forward 10\n}")

    def test_division_by_zero_is_rejected(self):
        with self.assertRaises(SemanticError) as ctx:
            check("let a = 10\nlet b = 0\nforward a / b")
        self.assertIn("division by zero", str(ctx.exception))

    def test_expression_evaluated_correctly(self):
        symtab = check("let x = 2 + 3 * 4\nforward x")
        self.assertEqual(symtab.lookup("x"), 14.0)

    def test_variable_can_be_reassigned(self):
        symtab = check("let step = 4\nlet step = step + 6\nforward step")
        self.assertEqual(symtab.lookup("step"), 10.0)


if __name__ == "__main__":
    unittest.main()
