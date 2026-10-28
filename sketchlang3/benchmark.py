#!/usr/bin/env python3
"""
Benchmark: compile time per stage, peak memory, and optimisation gain on
programs of increasing size. Usage:  python3 benchmark.py   (writes docs/benchmark_results.json)

Timing = median of RUNS runs (perf_counter). Memory = peak of tracemalloc over one
full compile + plotter plan (tracemalloc slows execution, so it is a separate run).
"""
import json
import statistics
import sys
import time
import tracemalloc

from sketchlang import compile_source

RUNS = 5


def spiral(n):
    return f"let step = 2\npen purple\nrepeat {n} {{\n forward step\n turn 15\n let step = step + 0.05\n}}\n"


KOCH = """proc koch(len, depth) {
  if depth == 0 { forward len } else {
    call koch(len / 3, depth - 1)
    turn -60
    call koch(len / 3, depth - 1)
    turn 120
    call koch(len / 3, depth - 1)
    turn -60
    call koch(len / 3, depth - 1)
  }
}
pen blue
repeat 3 { call koch(300, %d)
 turn 120 }
"""

TREE = """proc branch(len, depth) {
  if depth > 0 {
    forward len
    turn 25
    call branch(len * 0.7, depth - 1)
    turn -50
    call branch(len * 0.7, depth - 1)
    turn 25
    forward -len
  }
}
pen green
turn -90
call branch(60, %d)
"""


def mirror(n):
    return f"""proc box(s) {{ repeat 4 {{ forward s
 turn 90 }} }}
pen black
let i = 0
repeat {n} {{
  move i * 25, 0
  call box(15)
  move {n * 50} - i * 25, 0
  call box(15)
  let i = i + 1
}}
"""


CASES = (
    [("spiral", f"{n} iterations", spiral(n)) for n in (100, 1_000, 10_000, 50_000)]
    + [("koch", f"depth {d}", KOCH % d) for d in (1, 3, 5, 6)]
    + [("tree", f"depth {d}", TREE % d) for d in (4, 8, 11, 13)]
    + [("mirror boxes", f"{n} pairs", mirror(n)) for n in (10, 50, 100, 200)]
)


def one(src):
    t0 = time.perf_counter()
    r = compile_source(src)
    plan = r.plotter_plan()
    total = (time.perf_counter() - t0) * 1000
    return r, plan, total


def main():
    rows = []
    for family, label, src in CASES:
        totals, last = [], None
        for _ in range(RUNS):
            r, plan, total = one(src)
            totals.append(total)
            last = (r, plan)
        r, plan = last
        tracemalloc.start()
        one(src)
        _cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        b, a = len(r.ir_before_optimization), len(r.ir_after_optimization)
        rows.append({
            "family": family, "label": label,
            "source_lines": src.count("\n"),
            "ir_before": b, "ir_after": a,
            "ir_reduction_pct": round(100 * (b - a) / b, 1) if b else 0.0,
            "strokes_before": plan.before["strokes"], "strokes_after": plan.after["strokes"],
            "travel_before": plan.before["travel_distance"], "travel_after": plan.after["travel_distance"],
            "travel_saving_pct": plan.travel_saving_pct,
            "plotter_skipped": plan.info.get("skipped", False),
            "stage_ms": {k: round(v, 3) for k, v in r.timings.items()},
            "total_ms_median": round(statistics.median(totals), 2),
            "peak_mem_kb": round(peak / 1024, 1),
            "calls": r.run_stats["calls"], "max_depth": r.run_stats["max_depth"],
        })
        print(f"{family:13} {label:14} IR {b:>7} -> {a:>7}  travel {plan.before['travel_distance']:>10} -> "
              f"{plan.after['travel_distance']:>10}  total {rows[-1]['total_ms_median']:>9} ms  mem {rows[-1]['peak_mem_kb']:>9} KB")
    with open("docs/benchmark_results.json", "w") as f:
        json.dump({"python": sys.version.split()[0], "runs_per_case": RUNS, "rows": rows}, f, indent=2)


if __name__ == "__main__":
    main()
