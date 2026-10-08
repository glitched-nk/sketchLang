"""
SketchLang -- a small compiled language that turns turtle-style drawing
commands into an SVG image.

Phase 2 restructures the Phase 1 single-file prototype into proper modules:

    lexer.py        Lexical analysis        (source text -> tokens)
    parser.py       Syntax analysis         (tokens -> AST)
    symboltable.py  Symbol table            (name -> value, with declaration line)
    semantics.py    Semantic analysis       (AST -> static checks, expression evaluation)
    ir.py           Intermediate code gen   (AST -> flat IR instruction list)
    optimizer.py    Code optimization       (IR -> smaller/equal IR)
    codegen.py      Target code generation  (IR -> SVG text)
    compiler.py     Driver that wires the stages above together
"""

from .compiler import compile_source, CompilationError
from .lexer import LexError
from .parser import ParseError
from .semantics import SemanticError

__all__ = [
    "compile_source",
    "CompilationError",
    "LexError",
    "ParseError",
    "SemanticError",
]
