#!/usr/bin/env python3
"""
SketchLang CLI
==============
Usage:
    python3 main.py path/to/program.sketch [-o output.svg] [--show-ir]
"""

import argparse
import sys

from sketchlang import compile_source, LexError, ParseError, SemanticError


def main():
    argp = argparse.ArgumentParser(description="Compile a SketchLang program to SVG.")
    argp.add_argument("source", help="path to a .sketch source file")
    argp.add_argument("-o", "--output", default="output.svg", help="output SVG path (default: output.svg)")
    argp.add_argument("--show-ir", action="store_true", help="print the IR before and after optimization")
    argp.add_argument("--show-symbols", action="store_true", help="print the final symbol table")
    args = argp.parse_args()

    with open(args.source) as f:
        source = f.read()

    try:
        result = compile_source(source)
    except (LexError, ParseError, SemanticError) as e:
        print(f"Compilation failed: {e}")
        sys.exit(1)

    if args.show_ir:
        print(f"Unoptimized IR: {len(result.ir_before_optimization)} instruction(s)")
        for instr in result.ir_before_optimization:
            print("  ", instr)
        print(f"Optimized IR:   {len(result.ir_after_optimization)} instruction(s)")
        for instr in result.ir_after_optimization:
            print("  ", instr)

    if args.show_symbols:
        print("Symbol table:", result.symbol_table.as_dict())

    with open(args.output, "w") as f:
        f.write(result.svg)

    before = len(result.ir_before_optimization)
    after = len(result.ir_after_optimization)
    print(f"Compiled '{args.source}' -> {args.output}")
    print(f"Optimizer reduced {before} IR instruction(s) to {after}.")


if __name__ == "__main__":
    main()
