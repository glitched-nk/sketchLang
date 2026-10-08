"""
Semantic Analysis
=================
Walks the AST once, in program order, and:

  1. Evaluates every expression using evaluate_expr(), which is also
     reused by ir.py during code generation.
  2. Checks that every "pen" color is one of the known colors.
  3. Checks that every variable is declared (via "let") before use.
  4. Checks that every "repeat" count evaluates to a positive integer.
  5. Checks for division by zero inside expressions.

This is a *static* check: repeat bodies are visited exactly once (not
once per iteration), which is enough to catch "undefined variable" and
"invalid color" mistakes without fully executing the program. Full,
iteration-aware execution (needed for things like a counter that grows
every loop pass) happens later, in ir.py, using the same evaluate_expr()
helper against a fresh SymbolTable that IS updated on every iteration.
"""

from .symboltable import SymbolTable, UndefinedVariableError

COLORS = {"red", "green", "blue", "black", "orange", "purple", "brown", "pink"}


class SemanticError(Exception):
    """Raised for any static semantic violation (bad color, bad variable, bad repeat count, etc.)."""


def evaluate_expr(node, symtab):
    """Evaluate an expression AST node (NUM / VAR / NEG / BINOP) to a float.

    Shared by the static semantic checker and the IR generator so that
    "what a variable means" is defined in exactly one place.
    """
    if node.kind == "NUM":
        return node.args[0]

    if node.kind == "VAR":
        name = node.args[0]
        try:
            return symtab.lookup(name)
        except UndefinedVariableError:
            raise SemanticError(
                f"Semantic error (line {node.line}): variable '{name}' used before it is declared"
            )

    if node.kind == "NEG":
        return -evaluate_expr(node.args[0], symtab)

    if node.kind == "BINOP":
        op, left_node, right_node = node.args
        left = evaluate_expr(left_node, symtab)
        right = evaluate_expr(right_node, symtab)
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise SemanticError(f"Semantic error (line {node.line}): division by zero")
            return left / right
        raise SemanticError(f"Semantic error (line {node.line}): unknown operator '{op}'")

    raise SemanticError(f"Semantic error (line {node.line}): cannot evaluate node of kind {node.kind}")


def check_semantics(program_node):
    """Run all static checks. Returns the populated SymbolTable on success,
    or raises SemanticError with a line number on the first problem found."""
    symtab = SymbolTable()

    def walk(statements):
        for stmt in statements:
            if stmt.kind == "PEN":
                color = stmt.args[0]
                if color not in COLORS:
                    raise SemanticError(
                        f"Semantic error (line {stmt.line}): unknown color '{color}'. "
                        f"Valid colors: {sorted(COLORS)}"
                    )

            elif stmt.kind == "LET":
                name, expr = stmt.args
                value = evaluate_expr(expr, symtab)
                symtab.declare(name, value, stmt.line)

            elif stmt.kind == "FORWARD":
                evaluate_expr(stmt.args[0], symtab)

            elif stmt.kind == "TURN":
                evaluate_expr(stmt.args[0], symtab)

            elif stmt.kind == "MOVE":
                evaluate_expr(stmt.args[0], symtab)
                evaluate_expr(stmt.args[1], symtab)

            elif stmt.kind == "REPEAT":
                count_expr, body = stmt.args
                count_value = evaluate_expr(count_expr, symtab)
                if count_value <= 0 or count_value != int(count_value):
                    raise SemanticError(
                        f"Semantic error (line {stmt.line}): repeat count must be a positive "
                        f"whole number, got {count_value}"
                    )
                walk(body)

            else:
                raise SemanticError(f"Semantic error (line {stmt.line}): unknown statement '{stmt.kind}'")

    walk(program_node.args)
    return symtab
