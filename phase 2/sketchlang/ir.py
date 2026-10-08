"""
Intermediate Code Generation
============================
Walks the AST a second time -- this time as a full, iteration-aware
execution -- to produce a flat, three-address-code-like list of drawing
instructions:

    ("LINE", x1, y1, x2, y2, color)   -- draw a straight segment
    ("MOVE", x, y)                    -- reposition the pen without drawing

This pass owns a *live* SymbolTable that is updated every time a "let"
statement executes, including on every pass through a "repeat" loop body.
That is what makes a self-referencing assignment such as

    let step = step + 5

inside a repeat loop behave like a real loop counter (e.g. to draw a
spiral), rather than being fixed at its first value. Semantic validity
(are all variables declared, are colors valid, etc.) has already been
checked once by semantics.check_semantics() before this stage runs.
"""

import math

from .semantics import evaluate_expr
from .symboltable import SymbolTable


class TurtleState:
    """Mutable pen/turtle state threaded through IR generation."""

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.heading = 0.0
        self.color = "black"


def generate_ir(program_node):
    ir = []
    state = TurtleState()
    symtab = SymbolTable()

    def exec_statements(statements):
        for stmt in statements:
            exec_stmt(stmt)

    def exec_stmt(stmt):
        if stmt.kind == "PEN":
            state.color = stmt.args[0]

        elif stmt.kind == "LET":
            name, expr = stmt.args
            symtab.declare(name, evaluate_expr(expr, symtab), stmt.line)

        elif stmt.kind == "FORWARD":
            distance = evaluate_expr(stmt.args[0], symtab)
            rad = math.radians(state.heading)
            new_x = state.x + distance * math.cos(rad)
            new_y = state.y + distance * math.sin(rad)
            ir.append(("LINE", state.x, state.y, new_x, new_y, state.color))
            state.x, state.y = new_x, new_y

        elif stmt.kind == "TURN":
            state.heading = (state.heading + evaluate_expr(stmt.args[0], symtab)) % 360

        elif stmt.kind == "MOVE":
            state.x = evaluate_expr(stmt.args[0], symtab)
            state.y = evaluate_expr(stmt.args[1], symtab)
            ir.append(("MOVE", state.x, state.y))

        elif stmt.kind == "REPEAT":
            count_expr, body = stmt.args
            count = int(evaluate_expr(count_expr, symtab))
            for _ in range(count):
                exec_statements(body)

    exec_statements(program_node.args)
    return ir
