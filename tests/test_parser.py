import unittest

from sketchlang.lexer import tokenize
from sketchlang.parser import parse, ParseError, Node


class TestParser(unittest.TestCase):
    def test_pen_statement(self):
        ast = parse(tokenize("pen red"))
        self.assertEqual(ast.kind, "PROGRAM")
        self.assertEqual(len(ast.args), 1)
        self.assertEqual(ast.args[0].kind, "PEN")
        self.assertEqual(ast.args[0].args, ["red"])

    def test_forward_with_arithmetic_expression(self):
        ast = parse(tokenize("forward 2 + 3 * 4"))
        stmt = ast.args[0]
        self.assertEqual(stmt.kind, "FORWARD")
        expr = stmt.args[0]
        # Operator precedence: "2 + 3 * 4" must parse as 2 + (3 * 4), not (2 + 3) * 4
        self.assertEqual(expr.kind, "BINOP")
        self.assertEqual(expr.args[0], "+")
        self.assertEqual(expr.args[1], Node("NUM", [2.0], 0))
        self.assertEqual(expr.args[2].kind, "BINOP")
        self.assertEqual(expr.args[2].args[0], "*")

    def test_parenthesized_expression_overrides_precedence(self):
        ast = parse(tokenize("forward (2 + 3) * 4"))
        expr = ast.args[0].args[0]
        self.assertEqual(expr.kind, "BINOP")
        self.assertEqual(expr.args[0], "*")
        self.assertEqual(expr.args[1].kind, "BINOP")
        self.assertEqual(expr.args[1].args[0], "+")

    def test_unary_minus(self):
        ast = parse(tokenize("turn -90"))
        expr = ast.args[0].args[0]
        self.assertEqual(expr.kind, "NEG")
        self.assertEqual(expr.args[0], Node("NUM", [90.0], 0))

    def test_let_statement(self):
        ast = parse(tokenize("let side = 100"))
        stmt = ast.args[0]
        self.assertEqual(stmt.kind, "LET")
        self.assertEqual(stmt.args[0], "side")
        self.assertEqual(stmt.args[1], Node("NUM", [100.0], 0))

    def test_move_requires_comma(self):
        ast = parse(tokenize("move 10, 20"))
        stmt = ast.args[0]
        self.assertEqual(stmt.kind, "MOVE")
        self.assertEqual(stmt.args[0], Node("NUM", [10.0], 0))
        self.assertEqual(stmt.args[1], Node("NUM", [20.0], 0))

    def test_move_without_comma_is_a_syntax_error(self):
        with self.assertRaises(ParseError):
            parse(tokenize("move 10 20"))

    def test_repeat_block_with_body(self):
        ast = parse(tokenize("repeat 4 {\n forward 10\n turn 90\n}"))
        stmt = ast.args[0]
        self.assertEqual(stmt.kind, "REPEAT")
        count_expr, body = stmt.args
        self.assertEqual(count_expr, Node("NUM", [4.0], 0))
        self.assertEqual([s.kind for s in body], ["FORWARD", "TURN"])

    def test_missing_closing_brace_is_a_syntax_error(self):
        with self.assertRaises(ParseError):
            parse(tokenize("repeat 4 {\n forward 10\n"))

    def test_unexpected_token_is_a_syntax_error(self):
        with self.assertRaises(ParseError):
            parse(tokenize("123 pen red"))


if __name__ == "__main__":
    unittest.main()
