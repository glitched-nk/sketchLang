"""
Lexical Analysis
================
Converts SketchLang source text into a flat list of Token objects.

SketchLang tokens:
    Keywords    : pen forward turn move repeat let
    Identifiers : color names (red, blue, ...) and variable names
    Numbers     : integer or decimal literals (unsigned -- unary minus is
                  handled by the parser, not the lexer)
    Operators   : + - * / =
    Punctuation : { }
    Comments    : '#' to end of line (ignored)
"""

import re

KEYWORDS = {"pen", "forward", "turn", "move", "repeat", "let"}

# Order matters: longer/more specific patterns first.
TOKEN_SPEC = [
    ("NUMBER",  r"\d+(\.\d+)?"),
    ("PLUS",    r"\+"),
    ("MINUS",   r"-"),
    ("STAR",    r"\*"),
    ("SLASH",   r"/"),
    ("EQUALS",  r"="),
    ("COMMA",   r","),
    ("LPAREN",  r"\("),
    ("RPAREN",  r"\)"),
    ("LBRACE",  r"\{"),
    ("RBRACE",  r"\}"),
    ("IDENT",   r"[A-Za-z_][A-Za-z0-9_]*"),
    ("SKIP",    r"[ \t]+"),
    ("NEWLINE", r"\n"),
    ("COMMENT", r"#.*"),
    ("MISMATCH", r"."),
]
MASTER_RE = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))


class LexError(Exception):
    """Raised when the source text contains a character sequence with no valid token."""


class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind, value, line):
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, line={self.line})"

    def __eq__(self, other):
        return (self.kind, self.value) == (other.kind, other.value)


def tokenize(source):
    """Convert `source` (str) into a list[Token], terminated by an EOF token."""
    tokens = []
    line = 1
    for match in MASTER_RE.finditer(source):
        kind = match.lastgroup
        text = match.group()

        if kind == "NEWLINE":
            line += 1
            continue
        if kind in ("SKIP", "COMMENT"):
            continue
        if kind == "MISMATCH":
            raise LexError(f"Lexical error: unexpected character {text!r} on line {line}")
        if kind == "IDENT" and text in KEYWORDS:
            kind = text.upper()

        tokens.append(Token(kind, text, line))

    tokens.append(Token("EOF", None, line))
    return tokens
