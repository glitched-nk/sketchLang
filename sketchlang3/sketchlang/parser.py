"""
Syntax Analysis
===============
A hand-written recursive-descent parser that turns the token stream from
lexer.py into an Abstract Syntax Tree (AST) of Node objects.

Grammar (EBNF)
--------------
    program     := (proc_def | statement)*
    proc_def    := "proc" IDENT "(" [IDENT ("," IDENT)*] ")" block      (top level only)
    statement   := pen_stmt | forward_stmt | turn_stmt | move_stmt
                 | repeat_stmt | let_stmt | call_stmt | if_stmt
    pen_stmt    := "pen" IDENT
    forward_stmt:= "forward" expr
    turn_stmt   := "turn" expr
    move_stmt   := "move" expr "," expr
    repeat_stmt := "repeat" expr block
    let_stmt    := "let" IDENT "=" expr
    call_stmt   := "call" IDENT "(" [expr ("," expr)*] ")"
    if_stmt     := "if" cond block ["else" (block | if_stmt)]
    block       := "{" statement* "}"
    cond        := expr ("==" | "!=" | "<" | ">" | "<=" | ">=") expr

    expr        := term (("+" | "-") term)*
    term        := factor (("*" | "/") factor)*
    factor      := NUMBER | IDENT | "(" expr ")" | "-" factor
"""


class ParseError(Exception):
    """Raised on a token sequence that does not match the SketchLang grammar."""


class Node:
    """Generic AST node identified by `kind`, carrying `args` and a source `line`."""

    def __init__(self, kind, args, line):
        self.kind = kind
        self.args = args
        self.line = line

    def __repr__(self):
        return f"Node({self.kind}, {self.args})"

    def __eq__(self, other):
        return isinstance(other, Node) and (self.kind, self.args) == (other.kind, other.args)


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # -- token stream helpers -------------------------------------------------
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

    # -- grammar rules ----------------------------------------------------------
    def parse_program(self):
        statements = []
        while self.peek().kind != "EOF":
            if self.peek().kind == "PROC":
                statements.append(self.parse_proc())
            else:
                statements.append(self.parse_statement())
        return Node("PROGRAM", statements, 0)

    def parse_block(self, opener, line):
        """Parse '{' statement* '}' and return the list of statements."""
        self.expect("LBRACE")
        body = []
        while self.peek().kind != "RBRACE":
            if self.peek().kind == "EOF":
                raise ParseError(f"Syntax error: missing '}}' for {opener} opened on line {line}")
            body.append(self.parse_statement())
        self.expect("RBRACE")
        return body

    def parse_proc(self):
        tok = self.expect("PROC")
        name = self.expect("IDENT")
        self.expect("LPAREN")
        params = []
        if self.peek().kind != "RPAREN":
            params.append(self.expect("IDENT").value)
            while self.peek().kind == "COMMA":
                self.advance()
                params.append(self.expect("IDENT").value)
        self.expect("RPAREN")
        body = self.parse_block(f"proc '{name.value}'", tok.line)
        return Node("PROC", [name.value, params, body], tok.line)

    def parse_condition(self):
        left = self.parse_expr()
        op = self.peek()
        if op.kind not in ("EQEQ", "NEQ", "LT", "GT", "LE", "GE"):
            raise ParseError(
                f"Syntax error: expected a comparison operator (==, !=, <, >, <=, >=) "
                f"but got {op.kind} on line {op.line}"
            )
        self.advance()
        right = self.parse_expr()
        return Node("COND", [op.value, left, right], op.line)

    def parse_statement(self):
        tok = self.peek()

        if tok.kind == "PEN":
            self.advance()
            color = self.expect("IDENT")
            return Node("PEN", [color.value], tok.line)

        if tok.kind == "FORWARD":
            self.advance()
            return Node("FORWARD", [self.parse_expr()], tok.line)

        if tok.kind == "TURN":
            self.advance()
            return Node("TURN", [self.parse_expr()], tok.line)

        if tok.kind == "MOVE":
            # "move" takes two expressions separated by a comma. The comma is
            # required (not just cosmetic): without it, "move -5 -5" would be
            # ambiguous between "two negative numbers" and "one subtraction
            # expression (-5) - 5", since expr already consumes a trailing
            # "- term" as subtraction.
            self.advance()
            x = self.parse_expr()
            self.expect("COMMA")
            y = self.parse_expr()
            return Node("MOVE", [x, y], tok.line)

        if tok.kind == "REPEAT":
            self.advance()
            count_expr = self.parse_expr()
            body = self.parse_block("repeat", tok.line)
            return Node("REPEAT", [count_expr, body], tok.line)

        if tok.kind == "IF":
            self.advance()
            cond = self.parse_condition()
            then_body = self.parse_block("if", tok.line)
            else_body = []
            if self.peek().kind == "ELSE":
                else_tok = self.advance()
                if self.peek().kind == "IF":          # 'else if' chains nest naturally
                    else_body = [self.parse_statement()]
                else:
                    else_body = self.parse_block("else", else_tok.line)
            return Node("IF", [cond, then_body, else_body], tok.line)

        if tok.kind == "CALL":
            self.advance()
            name = self.expect("IDENT")
            self.expect("LPAREN")
            args = []
            if self.peek().kind != "RPAREN":
                args.append(self.parse_expr())
                while self.peek().kind == "COMMA":
                    self.advance()
                    args.append(self.parse_expr())
            self.expect("RPAREN")
            return Node("CALL", [name.value, args], tok.line)

        if tok.kind == "PROC":
            raise ParseError(
                f"Syntax error: 'proc' definitions are only allowed at the top level "
                f"(found inside a block on line {tok.line})"
            )

        if tok.kind == "LET":
            self.advance()
            name = self.expect("IDENT")
            self.expect("EQUALS")
            value_expr = self.parse_expr()
            return Node("LET", [name.value, value_expr], tok.line)

        raise ParseError(f"Syntax error: unexpected token {tok.kind} on line {tok.line}")

    # -- expression grammar (precedence climbing) --------------------------------
    def parse_expr(self):
        node = self.parse_term()
        while self.peek().kind in ("PLUS", "MINUS"):
            op = self.advance()
            rhs = self.parse_term()
            node = Node("BINOP", [op.value, node, rhs], op.line)
        return node

    def parse_term(self):
        node = self.parse_factor()
        while self.peek().kind in ("STAR", "SLASH"):
            op = self.advance()
            rhs = self.parse_factor()
            node = Node("BINOP", [op.value, node, rhs], op.line)
        return node

    def parse_factor(self):
        tok = self.peek()

        if tok.kind == "MINUS":
            self.advance()
            operand = self.parse_factor()
            return Node("NEG", [operand], tok.line)

        if tok.kind == "NUMBER":
            self.advance()
            return Node("NUM", [float(tok.value)], tok.line)

        if tok.kind == "IDENT":
            self.advance()
            return Node("VAR", [tok.value], tok.line)

        if tok.kind == "LPAREN":
            self.advance()
            node = self.parse_expr()
            self.expect("RPAREN")
            return node

        raise ParseError(f"Syntax error: expected a number, variable or '(' but got {tok.kind} on line {tok.line}")


def parse(tokens):
    """Convenience wrapper: tokens -> AST root Node."""
    return Parser(tokens).parse_program()
