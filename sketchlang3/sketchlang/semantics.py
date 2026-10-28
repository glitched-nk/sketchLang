"""
Semantic Analysis
=================
A static pass over the AST, run BEFORE any code is generated. It checks:

  1. every 'pen' colour is a known colour;
  2. every variable is declared ('let' or procedure parameter) before use,
     using the scope chain from symboltable.py;
  3. every 'call' names a defined procedure and passes the right number of
     arguments (procedures are collected first, so a call may appear
     before the definition);
  4. no procedure is defined twice and no parameter name repeats;
  5. a procedure body may only read globals that were declared BEFORE the
     procedure's definition;
  6. constant-propagated checks: a 'repeat' count or a divisor whose value is
     known at compile time must be valid (positive whole number / non-zero).

Constant propagation
--------------------
The checker tracks, for each variable, either a number (known at compile time)
or None (unknown). Parameters are unknown, and so is any variable that is
reassigned inside a 'repeat' or 'if' body (its value depends on how many
iterations / which branch runs). Anything computed from an unknown is unknown.
Checks that need a number (repeat count, division by zero) are performed here
when the number is known and deferred to the executor (ir.py) when it is not.
That is why  `repeat -3 { ... }` is a compile-time error but
`call f(-3)` with `repeat n` inside f is a run-time error.
"""

from .colors import COLOR_RGB
from .symboltable import SymbolTable

COLORS = set(COLOR_RGB)

UNKNOWN = None


class SemanticError(Exception):
    """Raised for any static semantic violation."""


# ---------------------------------------------------------------------------
# expressions
# ---------------------------------------------------------------------------

def static_eval(node, symtab):
    """Return the compile-time value of an expression node, or None if unknown.
    Raises SemanticError for undeclared variables and known division by zero."""
    if node.kind == "NUM":
        return node.args[0]

    if node.kind == "VAR":
        name = node.args[0]
        if not symtab.is_declared(name):
            raise SemanticError(
                f"Semantic error (line {node.line}): variable '{name}' used before it is declared"
            )
        return symtab.lookup(name)

    if node.kind == "NEG":
        value = static_eval(node.args[0], symtab)
        return None if value is None else -value

    if node.kind == "BINOP":
        op, left_node, right_node = node.args
        left = static_eval(left_node, symtab)
        right = static_eval(right_node, symtab)
        if op == "/" and right is not None and right == 0:
            raise SemanticError(f"Semantic error (line {node.line}): division by zero")
        if left is None or right is None:
            return None
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return left / right
        raise SemanticError(f"Semantic error (line {node.line}): unknown operator '{op}'")

    raise SemanticError(f"Semantic error (line {node.line}): cannot evaluate node of kind {node.kind}")


def _assigned_names(statements):
    """Names assigned by 'let' anywhere inside these statements (nested blocks included)."""
    names = set()
    for stmt in statements:
        if stmt.kind == "LET":
            names.add(stmt.args[0])
        elif stmt.kind == "REPEAT":
            names |= _assigned_names(stmt.args[1])
        elif stmt.kind == "IF":
            names |= _assigned_names(stmt.args[1])
            names |= _assigned_names(stmt.args[2])
    return names


def _forget_values(tab, names, line):
    """Mark already-visible variables as 'unknown' (value depends on control flow)."""
    for name in names:
        if tab.is_declared(name):
            tab.declare(name, UNKNOWN, line)


# ---------------------------------------------------------------------------
# statements
# ---------------------------------------------------------------------------

def analyze(program_node):
    """Run all static checks. Returns (global SymbolTable, {proc name: PROC node})."""
    procs = {}
    for stmt in program_node.args:
        if stmt.kind != "PROC":
            continue
        name, params, _body = stmt.args
        if name in procs:
            raise SemanticError(
                f"Semantic error (line {stmt.line}): procedure '{name}' is already defined "
                f"on line {procs[name].line}"
            )
        seen = set()
        for p in params:
            if p in seen:
                raise SemanticError(
                    f"Semantic error (line {stmt.line}): duplicate parameter '{p}' in procedure '{name}'"
                )
            seen.add(p)
        procs[name] = stmt

    global_tab = SymbolTable()

    def walk(statements, tab):
        for stmt in statements:
            check(stmt, tab)

    def check(stmt, tab):
        kind = stmt.kind

        if kind == "PROC":
            name, params, body = stmt.args
            frame = SymbolTable(parent=tab, name=name)   # sees only globals declared so far
            for p in params:
                frame.declare(p, UNKNOWN, stmt.line)
            walk(body, frame)

        elif kind == "PEN":
            color = stmt.args[0]
            if color not in COLORS:
                raise SemanticError(
                    f"Semantic error (line {stmt.line}): unknown color '{color}'. "
                    f"Valid colors: {sorted(COLORS)}"
                )

        elif kind == "LET":
            name, expr = stmt.args
            tab.declare(name, static_eval(expr, tab), stmt.line)

        elif kind in ("FORWARD", "TURN"):
            static_eval(stmt.args[0], tab)

        elif kind == "MOVE":
            static_eval(stmt.args[0], tab)
            static_eval(stmt.args[1], tab)

        elif kind == "REPEAT":
            count_expr, body = stmt.args
            count = static_eval(count_expr, tab)
            if count is not None and (count <= 0 or count != int(count)):
                raise SemanticError(
                    f"Semantic error (line {stmt.line}): repeat count must be a positive "
                    f"whole number, got {count}"
                )
            _forget_values(tab, _assigned_names(body), stmt.line)
            walk(body, tab)

        elif kind == "IF":
            cond, then_body, else_body = stmt.args
            static_eval(cond.args[1], tab)
            static_eval(cond.args[2], tab)
            _forget_values(tab, _assigned_names(then_body) | _assigned_names(else_body), stmt.line)
            before = tab.snapshot()
            walk(then_body, tab)
            declared_then = tab.local_names() - set(before)
            tab.restore(before)
            walk(else_body, tab)
            declared_else = tab.local_names() - set(before)
            tab.restore(before)
            # definite assignment: a NEW variable exists after the 'if' only if
            # every path (both branches) declared it
            for name in declared_then & declared_else:
                tab.declare(name, UNKNOWN, stmt.line)

        elif kind == "CALL":
            name, args = stmt.args
            if name not in procs:
                raise SemanticError(f"Semantic error (line {stmt.line}): call to undefined procedure '{name}'")
            expected = len(procs[name].args[1])
            if len(args) != expected:
                raise SemanticError(
                    f"Semantic error (line {stmt.line}): procedure '{name}' expects {expected} "
                    f"argument(s) but {len(args)} given"
                )
            for a in args:
                static_eval(a, tab)

        else:
            raise SemanticError(f"Semantic error (line {stmt.line}): unknown statement '{kind}'")

    walk(program_node.args, global_tab)
    return global_tab, procs


def check_semantics(program_node):
    """Back-compatible wrapper: run the checks, return the global SymbolTable."""
    return analyze(program_node)[0]
