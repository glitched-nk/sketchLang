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

    # ---- Phase 3 additions -------------------------------------------------
    def test_proc_definition(self):
        ast = parse(tokenize("proc sq(n, m) {\n forward n\n}"))
        proc = ast.args[0]
        self.assertEqual(proc.kind, "PROC")
        self.assertEqual(proc.args[0], "sq")
        self.assertEqual(proc.args[1], ["n", "m"])
        self.assertEqual(proc.args[2][0].kind, "FORWARD")

    def test_proc_with_no_parameters(self):
        proc = parse(tokenize("proc go() { forward 1 }")).args[0]
        self.assertEqual(proc.args[1], [])

    def test_call_with_expression_arguments(self):
        call = parse(tokenize("call sq(1 + 2, 3)")).args[0]
        self.assertEqual(call.kind, "CALL")
        self.assertEqual(call.args[0], "sq")
        self.assertEqual(len(call.args[1]), 2)
        self.assertEqual(call.args[1][0].kind, "BINOP")

    def test_call_trailing_comma_is_syntax_error(self):
        with self.assertRaises(ParseError):
            parse(tokenize("call sq(1,)"))

    def test_proc_inside_a_block_is_rejected(self):
        with self.assertRaises(ParseError) as ctx:
            parse(tokenize("repeat 2 {\n proc f() { forward 1 }\n}"))
        self.assertIn("top level", str(ctx.exception))

    def test_if_else(self):
        node = parse(tokenize("if a < 3 { forward 1 } else { forward 2 }")).args[0]
        self.assertEqual(node.kind, "IF")
        cond, then_body, else_body = node.args
        self.assertEqual(cond.args[0], "<")
        self.assertEqual(len(then_body), 1)
        self.assertEqual(len(else_body), 1)

    def test_if_without_else_has_empty_else(self):
        node = parse(tokenize("if 1 == 1 { forward 1 }")).args[0]
        self.assertEqual(node.args[2], [])

    def test_else_if_chain_nests(self):
        node = parse(tokenize("if a == 1 { forward 1 } else if a == 2 { forward 2 } else { forward 3 }")).args[0]
        inner = node.args[2][0]
        self.assertEqual(inner.kind, "IF")
        self.assertEqual(len(inner.args[2]), 1)

    def test_if_requires_comparison_operator(self):
        with self.assertRaises(ParseError) as ctx:
            parse(tokenize("if a { forward 1 }"))
        self.assertIn("comparison", str(ctx.exception))

    def test_missing_brace_message_names_the_construct(self):
        with self.assertRaises(ParseError) as ctx:
            parse(tokenize("proc f() {\n forward 1\n"))
        self.assertIn("proc 'f'", str(ctx.exception))

    def test_deeply_nested_repeats_parse(self):
        depth = 150
        src = "repeat 1 {" * depth + "forward 1" + "}" * depth
        ast = parse(tokenize(src))
        node, levels = ast.args[0], 0
        while node.kind == "REPEAT":
            levels += 1
            node = node.args[1][0]
        self.assertEqual(levels, depth)

    def test_empty_program(self):
        self.assertEqual(parse(tokenize("")).args, [])


if __name__ == "__main__":
    unittest.main()
