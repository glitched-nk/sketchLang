"""
Intermediate Code Generation + Execution
========================================
Walks the AST as a full, iteration-aware execution (the "run" of a
turtle program) and emits a flat, three-address-code-like instruction list:

    ("LINE", x1, y1, x2, y2, color)   -- draw a straight segment
    ("MOVE", x, y)                    -- reposition the pen without drawing

Execution model
---------------
  * One global SymbolTable. A 'call' creates a NEW frame whose parent is the
    global table (lexical scoping), binds the parameters, runs the body,
    and discards the frame.
  * The turtle (x, y, heading, colour) is global state shared by every
    procedure, exactly as in Logo.
  * Static analysis cannot know everything (procedure arguments, loop-carried
    variables), so this stage re-checks run-time conditions and raises
    SketchRuntimeError: division by zero, bad repeat count, call depth,
    instruction budget and step budget (the last three stop runaway
    recursion / endless loops instead of hanging the compiler).
"""

import math

from .symboltable import SymbolTable, UndefinedVariableError

MAX_CALL_DEPTH = 100
MAX_STEPS = 2_000_000          # statements executed
MAX_IR_INSTRUCTIONS = 200_000


class SketchRuntimeError(Exception):
    """Raised for errors that can only be detected while executing the program."""


class TurtleState:
    """Mutable pen/turtle state threaded through IR generation."""

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.heading = 0.0
        self.color = "black"


def evaluate(node, symtab):
    """Evaluate an expression node with real values (run-time semantics)."""
    kind = node.kind
    if kind == "NUM":
        return node.args[0]
    if kind == "VAR":
        try:
            return symtab.lookup(node.args[0])
        except UndefinedVariableError:
            raise SketchRuntimeError(
                f"Runtime error (line {node.line}): variable '{node.args[0]}' is not defined here"
            )
    if kind == "NEG":
        return -evaluate(node.args[0], symtab)
    if kind == "BINOP":
        op, left_node, right_node = node.args
        left = evaluate(left_node, symtab)
        right = evaluate(right_node, symtab)
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise SketchRuntimeError(f"Runtime error (line {node.line}): division by zero")
            return left / right
    raise SketchRuntimeError(f"Runtime error (line {node.line}): cannot evaluate node {kind}")


def compare(op, left, right):
    """Compare two numbers with a small tolerance, because loop-carried values such as
    `let x = x + 0.1` accumulate floating-point error. Every operator uses the same
    tolerance, so for any pair exactly one of  <  ==  >  is true (0.3 and 0.1+0.2 are
    equal, and neither is less than the other). Phase 3 fix: `<` and `>` used to be
    exact, which let `==` and `<` both hold for the same pair."""
    eps = 1e-9
    if op == "==":
        return abs(left - right) < eps
    if op == "!=":
        return abs(left - right) >= eps
    if op == "<":
        return left < right - eps
    if op == ">":
        return left > right + eps
    if op == "<=":
        return left <= right + eps
    if op == ">=":
        return left >= right - eps
    raise SketchRuntimeError(f"Runtime error: unknown comparison '{op}'")


def _finite(value, line):
    if not math.isfinite(value):
        raise SketchRuntimeError(
            f"Runtime error (line {line}): numeric overflow -- a value became infinite or undefined"
        )
    return value


def generate_ir(program_node, stats=None):
    """Execute `program_node`, return the IR list. If `stats` (a dict) is given
    it is filled with: steps, calls, max_depth, lines, moves."""
    ir = []
    state = TurtleState()
    global_tab = SymbolTable()
    procs = {s.args[0]: s for s in program_node.args if s.kind == "PROC"}
    counters = {"steps": 0, "calls": 0, "max_depth": 0}

    def exec_statements(statements, tab, depth):
        for stmt in statements:
            exec_stmt(stmt, tab, depth)

    def exec_stmt(stmt, tab, depth):
        counters["steps"] += 1
        if counters["steps"] > MAX_STEPS:
            raise SketchRuntimeError(
                f"Runtime error (line {stmt.line}): step limit of {MAX_STEPS:,} statements "
                f"exceeded (endless or extremely long loop?)"
            )
        kind = stmt.kind

        if kind == "PEN":
            state.color = stmt.args[0]

        elif kind == "LET":
            name, expr = stmt.args
            tab.declare(name, _finite(evaluate(expr, tab), stmt.line), stmt.line)

        elif kind == "FORWARD":
            distance = evaluate(stmt.args[0], tab)
            rad = math.radians(state.heading)
            new_x = _finite(state.x + distance * math.cos(rad), stmt.line)
            new_y = _finite(state.y + distance * math.sin(rad), stmt.line)
            ir.append(("LINE", state.x, state.y, new_x, new_y, state.color))
            if len(ir) > MAX_IR_INSTRUCTIONS:
                raise SketchRuntimeError(
                    f"Runtime error (line {stmt.line}): drawing exceeds {MAX_IR_INSTRUCTIONS:,} "
                    f"instructions"
                )
            state.x, state.y = new_x, new_y

        elif kind == "TURN":
            state.heading = (state.heading + evaluate(stmt.args[0], tab)) % 360

        elif kind == "MOVE":
            state.x = _finite(evaluate(stmt.args[0], tab), stmt.line)
            state.y = _finite(evaluate(stmt.args[1], tab), stmt.line)
            ir.append(("MOVE", state.x, state.y))

        elif kind == "REPEAT":
            count_expr, body = stmt.args
            count = evaluate(count_expr, tab)
            if count <= 0 or count != int(count):
                raise SketchRuntimeError(
                    f"Runtime error (line {stmt.line}): repeat count must be a positive "
                    f"whole number, got {count:g}"
                )
            for _ in range(int(count)):
                exec_statements(body, tab, depth)

        elif kind == "IF":
            cond, then_body, else_body = stmt.args
            op, left_node, right_node = cond.args
            if compare(op, evaluate(left_node, tab), evaluate(right_node, tab)):
                exec_statements(then_body, tab, depth)
            else:
                exec_statements(else_body, tab, depth)

        elif kind == "CALL":
            name, arg_nodes = stmt.args
            if depth + 1 > MAX_CALL_DEPTH:
                raise SketchRuntimeError(
                    f"Runtime error (line {stmt.line}): maximum call depth of {MAX_CALL_DEPTH} "
                    f"exceeded while calling '{name}' (infinite recursion?)"
                )
            _name, params, body = procs[name].args
            values = [evaluate(a, tab) for a in arg_nodes]      # evaluated in the CALLER's scope
            frame = SymbolTable(parent=global_tab, name=name)   # lexical scope: parent is global
            for param, value in zip(params, values):
                frame.declare(param, value, stmt.line)
            counters["calls"] += 1
            counters["max_depth"] = max(counters["max_depth"], depth + 1)
            exec_statements(body, frame, depth + 1)

        # PROC definitions are not executed; they only register a procedure.

    exec_statements([s for s in program_node.args if s.kind != "PROC"], global_tab, 0)

    if stats is not None:
        stats.update(counters)
        stats["lines"] = sum(1 for i in ir if i[0] == "LINE")
        stats["moves"] = sum(1 for i in ir if i[0] == "MOVE")
    return ir
