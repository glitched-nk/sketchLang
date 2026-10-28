#!/usr/bin/env python3
"""
SketchLang CLI
==============
    python3 main.py program.sketch                       -> output.svg
    python3 main.py program.sketch --target gcode -o job.gcode
    python3 main.py program.sketch --target ps    -o art.ps
    python3 main.py program.sketch --show-ast --show-ir --stats
"""

import argparse
import sys

from sketchlang import compile_source, error_info
from sketchlang.visualize import ast_to_text

DEFAULT_OUT = {"svg": "output.svg", "ps": "output.ps", "gcode": "output.gcode"}


def main():
    ap = argparse.ArgumentParser(description="Compile a SketchLang program.")
    ap.add_argument("source", help="path to a .sketch file")
    ap.add_argument("-o", "--output", help="output path (default depends on --target)")
    ap.add_argument("-t", "--target", choices=["svg", "ps", "gcode"], default="svg")
    ap.add_argument("--no-plotter-opt", action="store_true",
                    help="gcode: keep the original stroke order (for before/after comparison)")
    ap.add_argument("--no-color-grouping", action="store_true",
                    help="gcode: only reorder inside runs of one colour")
    ap.add_argument("--show-ast", action="store_true")
    ap.add_argument("--show-ir", action="store_true")
    ap.add_argument("--show-symbols", action="store_true")
    ap.add_argument("--stats", action="store_true", help="print timings and optimisation report")
    args = ap.parse_args()

    with open(args.source) as f:
        source = f.read()

    try:
        result = compile_source(source)
    except Exception as e:                       # noqa: BLE001 - report every stage's error uniformly
        info = error_info(e)
        if info["stage"] == "internal":
            raise
        print(f"Compilation failed ({info['stage']} error): {info['message']}")
        sys.exit(1)

    if args.show_ast:
        print(ast_to_text(result.ast))
    if args.show_ir:
        print(f"Unoptimized IR: {len(result.ir_before_optimization)} instruction(s)")
        for i in result.ir_before_optimization:
            print("  ", i)
        print(f"Optimized IR:   {len(result.ir_after_optimization)} instruction(s)")
        for i in result.ir_after_optimization:
            print("  ", i)
    if args.show_symbols:
        print("Global symbols:", result.symbol_table.as_dict())
        print("Procedures:", {n: p.args[1] for n, p in result.procs.items()})

    out_path = args.output or DEFAULT_OUT[args.target]
    group = not args.no_color_grouping

    if args.target == "svg":
        text = result.svg
    elif args.target == "ps":
        text = result.to_postscript()
    else:
        text, counts = result.to_gcode(group_colors=group, optimise=not args.no_plotter_opt)
        plan = result.plotter_plan(group)
        if args.no_plotter_opt:
            # report what was actually written: the original stroke order
            print(f"Plotter plan: optimisation OFF, program order kept: travel "
                  f"{plan.before['travel_distance']}, pen changes {plan.before['pen_changes']}")
        else:
            print(f"Plotter plan: travel {plan.before['travel_distance']} -> {plan.after['travel_distance']} "
                  f"({plan.travel_saving_pct}% less), pen changes {plan.before['pen_changes']} -> "
                  f"{plan.after['pen_changes']}")
    with open(out_path, "w") as f:
        f.write(text)

    before, after = len(result.ir_before_optimization), len(result.ir_after_optimization)
    print(f"Compiled '{args.source}' -> {out_path}  [{args.target}]")
    print(f"IR optimiser: {before} -> {after} instruction(s)")
    if args.stats:
        for p in result.optimization_report:
            print(f"   pass {p['pass']:<20} {p['before']:>6} -> {p['after']:<6}")
        for stage, ms in result.timings.items():
            print(f"   {stage:<18} {ms:8.3f} ms")


if __name__ == "__main__":
    main()
