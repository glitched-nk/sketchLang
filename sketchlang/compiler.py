"""
Compiler Driver
===============
compile_source() runs a SketchLang source string through the full
pipeline and returns a CompilationResult with everything a caller (the
CLI, a test, or a future GUI) might want to inspect: the token list, the
AST, both the unoptimized and optimized IR, the final symbol table, and
the generated SVG.

Any failure in an earlier stage raises immediately with a specific
exception type (LexError, ParseError, SemanticError), and later stages
never run -- mirroring how a real compiler stops at the first stage that
fails rather than producing output from a program known to be invalid.
"""

from dataclasses import dataclass, field
from typing import Any, List

from .lexer import tokenize, LexError
from .parser import parse, ParseError
from .semantics import check_semantics, SemanticError
from .ir import generate_ir
from .optimizer import optimize_ir
from .codegen import generate_svg


class CompilationError(Exception):
    """Base class for any compile_source() failure (see .__cause__ for the specific stage error)."""


@dataclass
class CompilationResult:
    tokens: List[Any]
    ast: Any
    symbol_table: Any
    ir_before_optimization: List[Any]
    ir_after_optimization: List[Any]
    svg: str
    warnings: List[str] = field(default_factory=list)


def compile_source(source):
    """Run the full SketchLang pipeline on `source` (str).

    Returns a CompilationResult on success. Raises LexError, ParseError,
    or SemanticError (all importable from the `sketchlang` package) on
    the first stage that rejects the program.
    """
    tokens = tokenize(source)
    ast = parse(tokens)
    symbol_table = check_semantics(ast)
    ir_before = generate_ir(ast)
    ir_after = optimize_ir(ir_before)
    svg = generate_svg(ir_after)

    return CompilationResult(
        tokens=tokens,
        ast=ast,
        symbol_table=symbol_table,
        ir_before_optimization=ir_before,
        ir_after_optimization=ir_after,
        svg=svg,
    )
