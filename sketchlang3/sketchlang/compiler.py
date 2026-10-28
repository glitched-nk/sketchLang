"""
Compiler Driver
===============
compile_source() runs a SketchLang source string through the full pipeline

    source -> Lexer -> Parser -> Semantic analysis -> IR generation/execution
           -> IR optimiser -> SVG code generator
                     \\-> (on demand) plotter optimiser -> G-code / PostScript

and returns a CompilationResult holding every intermediate product, so the
CLI, the tests, the benchmark and the web UI all read from the same place.
Each stage's wall-clock time is recorded in result.timings (milliseconds).

A failure in any stage raises that stage's exception (LexError, ParseError,
SemanticError, SketchRuntimeError) and later stages never run.
"""

import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .codegen import generate_svg
from .codegen_gcode import generate_gcode
from .codegen_ps import generate_ps
from .ir import SketchRuntimeError, generate_ir
from .lexer import LexError, tokenize
from .optimizer import optimize_ir_with_report
from .parser import ParseError, parse
from .plotter import plan_plotter
from .semantics import SemanticError, analyze
from .visualize import ast_to_dict, tokens_to_list


class CompilationError(Exception):
    """Base class kept for API compatibility."""


STAGE_OF = {
    LexError: "lexical",
    ParseError: "syntax",
    SemanticError: "semantic",
    SketchRuntimeError: "runtime",
}


def error_info(exc):
    """Structured view of a compile failure: {stage, message, line}."""
    stage = next((s for cls, s in STAGE_OF.items() if isinstance(exc, cls)), "internal")
    m = re.search(r"line (\d+)", str(exc))
    return {"stage": stage, "message": str(exc), "line": int(m.group(1)) if m else None}


@dataclass
class CompilationResult:
    tokens: List[Any]
    ast: Any
    symbol_table: Any
    procs: Dict[str, Any]
    ir_before_optimization: List[Any]
    ir_after_optimization: List[Any]
    optimization_report: List[Dict[str, Any]]
    svg: str
    run_stats: Dict[str, Any]
    timings: Dict[str, float]
    warnings: List[str] = field(default_factory=list)
    _plans: Dict[bool, Any] = field(default_factory=dict, repr=False)

    # -- on-demand back ends ------------------------------------------------------
    def plotter_plan(self, group_colors=True):
        if group_colors not in self._plans:
            t0 = time.perf_counter()
            self._plans[group_colors] = plan_plotter(self.ir_after_optimization, group_colors)
            self.timings["plotter_optimise"] = (time.perf_counter() - t0) * 1000
        return self._plans[group_colors]

    def to_gcode(self, group_colors=True, optimise=True):
        plan = self.plotter_plan(group_colors)
        strokes = plan.strokes_after if optimise else plan.strokes_before
        t0 = time.perf_counter()
        text, counts = generate_gcode(strokes)
        self.timings["gcode"] = (time.perf_counter() - t0) * 1000
        return text, counts

    def to_postscript(self):
        t0 = time.perf_counter()
        text = generate_ps(self.ir_after_optimization)
        self.timings["postscript"] = (time.perf_counter() - t0) * 1000
        return text

    def ast_dict(self):
        return ast_to_dict(self.ast)

    def token_list(self):
        return tokens_to_list(self.tokens)


def compile_source(source):
    """Run the full SketchLang pipeline on `source` (str) and return a CompilationResult."""
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))   # deep nesting / call depth
    timings = {}

    def timed(name, fn, *args):
        t0 = time.perf_counter()
        value = fn(*args)
        timings[name] = (time.perf_counter() - t0) * 1000
        return value

    tokens = timed("lexer", tokenize, source)
    ast = timed("parser", parse, tokens)
    symbol_table, procs = timed("semantics", analyze, ast)
    run_stats = {}
    ir_before = timed("ir_generation", generate_ir, ast, run_stats)
    ir_after, report = timed("optimizer", optimize_ir_with_report, ir_before)
    svg = timed("svg_codegen", generate_svg, ir_after)

    return CompilationResult(
        tokens=tokens,
        ast=ast,
        symbol_table=symbol_table,
        procs=procs,
        ir_before_optimization=ir_before,
        ir_after_optimization=ir_after,
        optimization_report=report,
        svg=svg,
        run_stats=run_stats,
        timings=timings,
    )
