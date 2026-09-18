"""
SketchLang - a tiny Domain-Specific Language that compiles simple turtle-style
drawing commands into an SVG image.

Grammar (EBNF):
    program    := statement*
    statement  := pen_stmt | forward_stmt | turn_stmt | move_stmt | repeat_stmt
    pen_stmt   := "pen" COLOR
    forward_stmt := "forward" NUMBER
    turn_stmt  := "turn" NUMBER
    move_stmt  := "move" NUMBER NUMBER
    repeat_stmt := "repeat" NUMBER "{" statement* "}"

Pipeline implemented below (Phase-1 prototype -- scaled up in Phase 2/3):
    source text -> Lexer -> tokens -> Parser -> AST -> Semantic Analyzer
        -> IR generator -> Optimizer -> SVG Code Generator -> output.svg
"""

import math
import re
import sys

# ----------------------------------------------------------------------
# 1. LEXICAL ANALYSIS
# ----------------------------------------------------------------------

KEYWORDS = {"pen", "forward", "turn", "move", "repeat"}
COLORS = {"red", "green", "blue", "black", "orange", "purple", "brown", "pink"}

TOKEN_SPEC = [
    ("NUMBER",  r"-?\d+(\.\d+)?"),
    ("LBRACE",  r"\{"),
    ("RBRACE",  r"\}"),
    ("IDENT",   r"[A-Za-z_][A-Za-z0-9_]*"),
    ("SKIP",    r"[ \t]+"),
    ("NEWLINE", r"\n"),
    ("COMMENT", r"#.*"),
    ("MISMATCH", r"."),
]
MASTER_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC))


class Token:
    def __init__(self, kind, value, line):
        self.kind, self.value, self.line = kind, value, line

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, line={self.line})"


class LexError(Exception):
    pass


def tokenize(source):
    tokens = []
    line = 1
    for m in MASTER_RE.finditer(source):
        kind = m.lastgroup
        value = m.group()
        if kind == "NEWLINE":
            line += 1
            continue
        if kind in ("SKIP", "COMMENT"):
            continue
        if kind == "MISMATCH":
            raise LexError(f"Lexical error: unexpected character {value!r} on line {line}")
        if kind == "IDENT" and value in KEYWORDS:
            kind = value.upper()
        tokens.append(Token(kind, value, line))
    tokens.append(Token("EOF", None, line))
    return tokens


# ----------------------------------------------------------------------
# 2. SYNTAX ANALYSIS (recursive-descent parser -> AST)
# ----------------------------------------------------------------------

class ParseError(Exception):
    pass


class Node:
    """Generic AST node: kind + args + line (for error messages)."""

    def __init__(self, kind, args, line):
        self.kind, self.args, self.line = kind, args, line

    def __repr__(self):
        return f"Node({self.kind}, {self.args})"


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind):
        tok = self.peek()
        if tok.kind != kind:
            raise ParseError(f"Syntax error: expected {kind} but got {tok.kind} on line {tok.line}")
        return self.advance()

    def parse_program(self):
        statements = []
        while self.peek().kind != "EOF":
            statements.append(self.parse_statement())
        return Node("PROGRAM", statements, 0)

    def parse_statement(self):
        tok = self.peek()
        if tok.kind == "PEN":
            self.advance()
            color_tok = self.expect("IDENT")
            return Node("PEN", [color_tok.value], tok.line)
        if tok.kind == "FORWARD":
            self.advance()
            n = self.expect("NUMBER")
            return Node("FORWARD", [float(n.value)], tok.line)
        if tok.kind == "TURN":
            self.advance()
            n = self.expect("NUMBER")
            return Node("TURN", [float(n.value)], tok.line)
        if tok.kind == "MOVE":
            self.advance()
            x = self.expect("NUMBER")
            y = self.expect("NUMBER")
            return Node("MOVE", [float(x.value), float(y.value)], tok.line)
        if tok.kind == "REPEAT":
            self.advance()
            n = self.expect("NUMBER")
            self.expect("LBRACE")
            body = []
            while self.peek().kind != "RBRACE":
                if self.peek().kind == "EOF":
                    raise ParseError(f"Syntax error: missing '}}' for repeat opened near line {tok.line}")
                body.append(self.parse_statement())
            self.expect("RBRACE")
            return Node("REPEAT", [int(float(n.value)), body], tok.line)
        raise ParseError(f"Syntax error: unexpected token {tok.kind} on line {tok.line}")


# ----------------------------------------------------------------------
# 3. SEMANTIC ANALYSIS
# ----------------------------------------------------------------------

class SemanticError(Exception):
    pass


def check_semantics(program_node):
    """Simple semantic checks: valid colors, positive repeat counts."""

    def walk(statements):
        for stmt in statements:
            if stmt.kind == "PEN":
                color = stmt.args[0]
                if color not in COLORS:
                    raise SemanticError(
                        f"Semantic error (line {stmt.line}): unknown color '{color}'. "
                        f"Valid colors: {sorted(COLORS)}"
                    )
            elif stmt.kind == "REPEAT":
                count, body = stmt.args
                if count <= 0:
                    raise SemanticError(
                        f"Semantic error (line {stmt.line}): repeat count must be positive, got {count}"
                    )
                walk(body)
    walk(program_node.args)


# ----------------------------------------------------------------------
# 4. INTERMEDIATE REPRESENTATION (a flat "three-address-code"-like list)
# ----------------------------------------------------------------------
# Each IR instruction is a tuple:
#   ("LINE", x1, y1, x2, y2, color)   -- draw a segment
#   ("MOVE", x, y)                    -- reposition pen without drawing

def generate_ir(program_node):
    ir = []
    state = {"x": 0.0, "y": 0.0, "heading": 0.0, "color": "black"}

    def exec_stmt(stmt):
        if stmt.kind == "PEN":
            state["color"] = stmt.args[0]
        elif stmt.kind == "FORWARD":
            dist = stmt.args[0]
            rad = math.radians(state["heading"])
            nx = state["x"] + dist * math.cos(rad)
            ny = state["y"] + dist * math.sin(rad)
            ir.append(("LINE", state["x"], state["y"], nx, ny, state["color"]))
            state["x"], state["y"] = nx, ny
        elif stmt.kind == "TURN":
            state["heading"] = (state["heading"] + stmt.args[0]) % 360
        elif stmt.kind == "MOVE":
            state["x"], state["y"] = stmt.args
            ir.append(("MOVE", state["x"], state["y"]))
        elif stmt.kind == "REPEAT":
            count, body = stmt.args
            for _ in range(count):
                for s in body:
                    exec_stmt(s)

    for stmt in program_node.args:
        exec_stmt(stmt)
    return ir


# ----------------------------------------------------------------------
# 5. OPTIMIZATION
# ----------------------------------------------------------------------
# Merge consecutive LINE instructions that are collinear and share a color
# into a single instruction, reducing the number of emitted SVG elements.

def optimize_ir(ir):
    if not ir:
        return ir
    optimized = [ir[0]]
    for instr in ir[1:]:
        prev = optimized[-1]
        if (
            instr[0] == "LINE"
            and prev[0] == "LINE"
            and instr[5] == prev[5]          # same color
            and (prev[3], prev[4]) == (instr[1], instr[2])  # prev end == this start
            and _collinear(prev[1], prev[2], prev[3], prev[4], instr[3], instr[4])
        ):
            optimized[-1] = ("LINE", prev[1], prev[2], instr[3], instr[4], prev[5])
        else:
            optimized.append(instr)
    return optimized


def _collinear(x1, y1, x2, y2, x3, y3, eps=1e-6):
    # cross product of (p2-p1) and (p3-p1) close to zero => collinear
    cross = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
    return abs(cross) < eps


# ----------------------------------------------------------------------
# 6. TARGET CODE GENERATION (emit SVG)
# ----------------------------------------------------------------------

def generate_svg(ir, width=400, height=400, margin=200):
    lines = []
    for instr in ir:
        if instr[0] == "LINE":
            _, x1, y1, x2, y2, color = instr
            lines.append(
                f'<line x1="{x1+margin:.2f}" y1="{y1+margin:.2f}" '
                f'x2="{x2+margin:.2f}" y2="{y2+margin:.2f}" '
                f'stroke="{color}" stroke-width="2" />'
            )
    body = "\n  ".join(lines)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="white" />
  {body}
</svg>"""
    return svg


# ----------------------------------------------------------------------
# DRIVER
# ----------------------------------------------------------------------

def compile_source(source, out_path="output.svg", show_ir=False):
    tokens = tokenize(source)
    ast = Parser(tokens).parse_program()
    check_semantics(ast)
    ir = generate_ir(ast)
    if show_ir:
        print(f"Unoptimized IR: {len(ir)} instructions")
        for instr in ir:
            print("  ", instr)
    opt_ir = optimize_ir(ir)
    if show_ir:
        print(f"Optimized IR:   {len(opt_ir)} instructions")
        for instr in opt_ir:
            print("  ", instr)
    svg = generate_svg(opt_ir)
    with open(out_path, "w") as f:
        f.write(svg)
    return out_path, len(ir), len(opt_ir)


if __name__ == "__main__":
    src_path = sys.argv[1] if len(sys.argv) > 1 else "examples/square.sketch"
    with open(src_path) as f:
        source = f.read()
    try:
        out, before, after = compile_source(source, "output.svg", show_ir=True)
        print(f"\nCompiled '{src_path}' -> {out}")
        print(f"Optimizer reduced {before} IR instructions to {after}.")
    except (LexError, ParseError, SemanticError) as e:
        print(f"Compilation failed: {e}")
        sys.exit(1)
