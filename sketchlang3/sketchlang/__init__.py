"""
SketchLang -- a small compiled language that turns turtle-style drawing
programs into SVG, PostScript or pen-plotter G-code.

    lexer.py          Lexical analysis          source text -> tokens
    parser.py         Syntax analysis           tokens -> AST (procs, if/else, expressions)
    symboltable.py    Symbol table              scope chain (global + call frames)
    semantics.py      Semantic analysis         static checks + constant propagation
    ir.py             IR generation/execution   AST -> flat LINE/MOVE list (run-time checks)
    optimizer.py      Machine-independent opt   4 picture-preserving IR passes
    plotter.py        Machine-DEPENDENT opt     stroke reordering for pen plotters  (novelty)
    codegen.py        Back end 1                SVG
    codegen_ps.py     Back end 2                PostScript
    codegen_gcode.py  Back end 3                G-code for a pen plotter
    compiler.py       Driver                    wires the stages together
    visualize.py      AST / token views         used by the web UI and CLI
"""

from .compiler import CompilationError, compile_source, error_info
from .ir import SketchRuntimeError
from .lexer import LexError
from .parser import ParseError
from .semantics import SemanticError

__all__ = [
    "compile_source",
    "error_info",
    "CompilationError",
    "LexError",
    "ParseError",
    "SemanticError",
    "SketchRuntimeError",
]
