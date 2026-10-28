"""In-process tests for visualize.py (the AST/token views used by the web UI and --show-ast)."""
import unittest

from sketchlang.lexer import tokenize
from sketchlang.parser import parse
from sketchlang.visualize import ast_to_dict, ast_to_text, tokens_to_list


def ast_of(src):
    return parse(tokenize(src))


def find(d, label):
    """Depth-first search for the first node whose label starts with `label`."""
    if d["label"].startswith(label):
        return d
    for c in d["children"]:
        hit = find(c, label)
        if hit:
            return hit
    return None


class TestAstDict(unittest.TestCase):
    def test_root_and_structure(self):
        d = ast_to_dict(ast_of("pen red\nforward 10"))
        self.assertEqual(d["label"], "PROGRAM")
        self.assertEqual([c["label"] for c in d["children"]], ["PEN red", "FORWARD"])

    def test_expression_tree_respects_precedence(self):
        d = ast_to_dict(ast_of("forward 2 + 3 * 4"))
        plus = find(d, "BINOP +")
        self.assertIsNotNone(plus)
        self.assertEqual([c["label"] for c in plus["children"]][0], "NUM 2")
        self.assertEqual(plus["children"][1]["label"], "BINOP *")

    def test_every_statement_kind_has_a_label(self):
        src = (
            "proc f(a, b) { forward a }\n"
            "let n = -2\n"
            "move 1, 2\n"
            "repeat 2 { turn 90 }\n"
            "if n < 1 { forward 1 } else { forward 2 }\n"
            "call f(1, 2)\n"
        )
        d = ast_to_dict(ast_of(src))
        for label in ("PROC f(a, b)", "LET n", "NEG", "MOVE", "REPEAT", "IF", "COND <", "CALL f", "THEN", "ELSE"):
            self.assertIsNotNone(find(d, label), label)

    def test_if_without_else_has_no_else_group(self):
        d = ast_to_dict(ast_of("if 1 < 2 { forward 1 }"))
        self.assertIsNotNone(find(d, "THEN"))
        self.assertIsNone(find(d, "ELSE"))

    def test_dict_input_is_returned_unchanged(self):
        d = {"label": "X", "children": []}
        self.assertIs(ast_to_dict(d), d)

    def test_line_numbers_carried_through(self):
        d = ast_to_dict(ast_of("pen red\n\nforward 5"))
        self.assertEqual([c["line"] for c in d["children"]], [1, 3])


class TestAstText(unittest.TestCase):
    def test_indented_dump(self):
        text = ast_to_text(ast_of("repeat 2 { forward 1 }"))
        lines = text.splitlines()
        self.assertEqual(lines[0], "PROGRAM")
        self.assertEqual(lines[1], "  REPEAT")
        self.assertIn("    NUM 2", lines)
        self.assertIn("    FORWARD", lines)

    def test_base_indent(self):
        self.assertTrue(ast_to_text(ast_of("pen red"), indent=2).startswith("    PROGRAM"))


class TestTokensToList(unittest.TestCase):
    def test_eof_is_dropped_and_fields_present(self):
        toks = tokens_to_list(tokenize("pen red"))
        self.assertEqual(toks, [
            {"kind": "PEN", "value": "pen", "line": 1},
            {"kind": "IDENT", "value": "red", "line": 1},
        ])

    def test_empty_source(self):
        self.assertEqual(tokens_to_list(tokenize("")), [])


if __name__ == "__main__":
    unittest.main()
