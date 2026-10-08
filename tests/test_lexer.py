import unittest

from sketchlang.lexer import tokenize, LexError


class TestLexer(unittest.TestCase):
    def test_simple_pen_statement(self):
        tokens = tokenize("pen red")
        kinds = [t.kind for t in tokens]
        self.assertEqual(kinds, ["PEN", "IDENT", "EOF"])

    def test_number_and_arithmetic_tokens(self):
        tokens = tokenize("forward 2 + 3 * 4")
        kinds = [t.kind for t in tokens]
        self.assertEqual(kinds, ["FORWARD", "NUMBER", "PLUS", "NUMBER", "STAR", "NUMBER", "EOF"])

    def test_decimal_number(self):
        tokens = tokenize("forward 12.5")
        self.assertEqual(tokens[1].kind, "NUMBER")
        self.assertEqual(tokens[1].value, "12.5")

    def test_keywords_recognized(self):
        tokens = tokenize("let x = 5")
        kinds = [t.kind for t in tokens]
        self.assertEqual(kinds, ["LET", "IDENT", "EQUALS", "NUMBER", "EOF"])

    def test_repeat_block_tokens(self):
        tokens = tokenize("repeat 4 {\n  forward 10\n}")
        kinds = [t.kind for t in tokens]
        self.assertEqual(kinds, ["REPEAT", "NUMBER", "LBRACE", "FORWARD", "NUMBER", "RBRACE", "EOF"])

    def test_comments_and_whitespace_ignored(self):
        tokens = tokenize("  # a full-line comment\n  pen blue  # trailing comment\n")
        kinds = [t.kind for t in tokens]
        self.assertEqual(kinds, ["PEN", "IDENT", "EOF"])

    def test_line_numbers_tracked(self):
        tokens = tokenize("pen red\nforward 10\nturn 90")
        lines = [t.line for t in tokens if t.kind != "EOF"]
        self.assertEqual(lines, [1, 1, 2, 2, 3, 3])

    def test_comma_and_parens(self):
        tokens = tokenize("move (1 + 2), 3")
        kinds = [t.kind for t in tokens]
        self.assertEqual(
            kinds,
            ["MOVE", "LPAREN", "NUMBER", "PLUS", "NUMBER", "RPAREN", "COMMA", "NUMBER", "EOF"],
        )

    def test_unexpected_character_raises_lex_error(self):
        with self.assertRaises(LexError) as ctx:
            tokenize("pen red\nforward @@10")
        self.assertIn("line 2", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
