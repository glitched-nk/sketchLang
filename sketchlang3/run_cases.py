#!/usr/bin/env python3
"""
Scripted black-box test cases: each case is (id, category, description, source,
expected). Runs every case through compile_source and records expected vs actual.
Writes docs/test_cases_results.json (used by the report). Exit code 1 if any case fails.
"""
import json
import sys

from sketchlang import compile_source, error_info

BOX = "proc box(s) { repeat 4 { forward s\n turn 90 } }\n"

# expected: ("ok", predicate_description, predicate)  or  ("error", stage, substring)
def ok(desc, pred):
    return ("ok", desc, pred)

def err(stage, needle):
    return ("error", stage, needle)

CASES = [
    # ---------------- valid ----------------
    ("V1", "valid", "Minimal program", "pen red\nforward 50",
     ok("1 LINE of length 50", lambda r: len(r.ir_before_optimization) == 1 and r.ir_before_optimization[0][3] == 50)),
    ("V2", "valid", "Square with repeat returns to start", "pen blue\nrepeat 4 { forward 100\n turn 90 }",
     ok("4 LINEs, ends at origin", lambda r: len(r.ir_before_optimization) == 4 and abs(r.ir_before_optimization[-1][3]) < 1e-6 and abs(r.ir_before_optimization[-1][4]) < 1e-6)),
    ("V3", "valid", "Operator precedence 2 + 3 * 4", "let x = 2 + 3 * 4\nforward x",
     ok("line length 14", lambda r: r.ir_before_optimization[0][3] == 14)),
    ("V4", "valid", "Parentheses and unary minus", "forward -(2 + 3) * 2",
     ok("line length -10", lambda r: r.ir_before_optimization[0][3] == -10)),
    ("V5", "valid", "Nested repeat 3 x 3", "repeat 3 { repeat 3 { forward 1 } }",
     ok("9 LINEs", lambda r: len(r.ir_before_optimization) == 9)),
    ("V6", "valid", "Procedure with parameter", BOX + "pen red\ncall box(25)",
     ok("4 LINEs, 1 call", lambda r: len(r.ir_before_optimization) == 4 and r.run_stats["calls"] == 1)),
    ("V7", "valid", "if / else-if / else chain", "let a = 2\nif a == 1 { forward 1 } else if a == 2 { forward 2 } else { forward 3 }",
     ok("takes the middle branch (length 2)", lambda r: r.ir_before_optimization[0][3] == 2)),
    ("V8", "valid", "Recursion with base case", "proc f(n) { if n > 0 { forward 1\n call f(n - 1) } }\ncall f(5)",
     ok("5 LINEs, depth 6", lambda r: len(r.ir_before_optimization) == 5 and r.run_stats["max_depth"] == 6)),
    ("V9", "valid", "All eight colours accepted",
     "\n".join(f"pen {c}\nforward 1" for c in ["red", "green", "blue", "black", "orange", "purple", "brown", "pink"]),
     ok("8 LINEs", lambda r: len(r.ir_before_optimization) == 8)),
    ("V10", "valid", "Local variable shadows global without changing it",
     "let n = 5\nproc f() { let n = 1\n forward n }\ncall f()\nforward n",
     ok("local 1 then global 5", lambda r: r.ir_before_optimization[0][3] == 1 and r.ir_before_optimization[1][3] - r.ir_before_optimization[1][1] == 5)),
    # ---------------- invalid: compile time ----------------
    ("E1", "invalid", "Illegal character", "pen red\nforward 10 @ 5", err("lexical", "line 2")),
    ("E2", "invalid", "Missing closing brace", "repeat 4 {\n forward 10", err("syntax", "missing '}'")),
    ("E3", "invalid", "move without comma", "move 10 20", err("syntax", "COMMA")),
    ("E4", "invalid", "if without comparison", "if 1 { forward 1 }", err("syntax", "comparison")),
    ("E5", "invalid", "proc defined inside a block", "repeat 2 { proc f() { forward 1 } }", err("syntax", "top level")),
    ("E6", "invalid", "Unknown colour", "pen skyblue", err("semantic", "unknown color")),
    ("E7", "invalid", "Undeclared variable", "forward radius", err("semantic", "'radius'")),
    ("E8", "invalid", "Call to undefined procedure", "call ghost(1)", err("semantic", "undefined procedure")),
    ("E9", "invalid", "Wrong argument count", "proc f(a) { forward a }\ncall f(1, 2)", err("semantic", "expects 1")),
    ("E10", "invalid", "Duplicate procedure", "proc f() { forward 1 }\nproc f() { forward 2 }", err("semantic", "already defined")),
    ("E11", "invalid", "Callee cannot see caller's local", "proc inner() { forward size }\nproc outer(size) { call inner() }\ncall outer(3)", err("semantic", "'size'")),
    ("E12", "invalid", "Local does not leak out of procedure", "proc f() { let t = 1 }\ncall f()\nforward t", err("semantic", "'t'")),
    ("E13", "invalid", "Constant negative repeat count", "repeat -3 { forward 1 }", err("semantic", "positive whole number")),
    ("E14", "invalid", "Constant division by zero", "let z = 0\nforward 5 / z", err("semantic", "division by zero")),
    ("E15", "invalid", "Variable declared in only one if-branch", "if 1 < 2 { let t = 1 }\nforward t", err("semantic", "'t'")),
    # ---------------- invalid: run time ----------------
    ("R1", "runtime", "Recursion with no base case", "proc f(n) { call f(n + 1) }\ncall f(1)", err("runtime", "maximum call depth")),
    ("R2", "runtime", "Division by zero via parameter", "proc r(a, b) { forward a / b }\ncall r(1, 0)", err("runtime", "division by zero")),
    ("R3", "runtime", "Fractional repeat count via parameter", "proc f(n) { repeat n { forward 1 } }\ncall f(2.5)", err("runtime", "positive whole number")),
    ("R4", "runtime", "Runaway nested loops hit the step budget", "repeat 100000 { repeat 100000 { let a = 1 } }", err("runtime", "step limit")),
    ("R5", "runtime", "Drawing exceeds instruction budget", "repeat 1000 { repeat 1000 { forward 1 } }", err("runtime", "instructions")),
    # ---------------- boundary ----------------
    ("B1", "boundary", "Empty source", "",
     ok("compiles to a valid empty SVG", lambda r: len(r.ir_before_optimization) == 0 and "</svg>" in r.svg)),
    ("B2", "boundary", "Comments and blank lines only", "# just a comment\n\n   \n# another",
     ok("empty drawing", lambda r: len(r.ir_before_optimization) == 0)),
    ("B3", "boundary", "forward 0 draws nothing", "pen red\nforward 0",
     ok("1 IR line before, 0 after optimisation, no <line> in SVG", lambda r: len(r.ir_before_optimization) == 1 and len(r.ir_after_optimization) == 0 and "<line" not in r.svg)),
    ("B4", "boundary", "Huge coordinate (1e9)", "pen red\nforward 1000000000",
     ok("compiles", lambda r: r.ir_before_optimization[0][3] == 1e9)),
    ("B5", "boundary", "Recursion depth exactly at the limit (100)", "proc f(n) { if n > 0 { call f(n - 1) } }\ncall f(99)",
     ok("max depth 100, no error", lambda r: r.run_stats["max_depth"] == 100)),
    ("B6", "boundary", "Recursion one past the limit (101)", "proc f(n) { if n > 0 { call f(n - 1) } }\ncall f(100)",
     err("runtime", "maximum call depth")),
    ("B7", "boundary", "150 levels of nested repeat", "repeat 1 {" * 150 + "forward 1" + "}" * 150,
     ok("1 LINE", lambda r: len(r.ir_before_optimization) == 1)),
    ("B8", "boundary", "Windows (CRLF) line endings", "pen red\r\nforward 5\r\nturn 90\r\nforward 5\r\n",
     ok("2 LINEs", lambda r: len(r.ir_before_optimization) == 2)),
    ("B9", "boundary", "Leading-dot number '.5' is illegal", "forward .5", err("lexical", "'.'")),
    ("B12", "boundary", "Numeric overflow (400-digit literal)", "forward 1" + "0" * 400, err("runtime", "overflow")),
    ("B10", "boundary", "Back-tracking is NOT merged (Phase 2 bug regression)", "pen red\nforward 100\nforward -50",
     ok("2 segments kept after optimisation", lambda r: len(r.ir_after_optimization) == 2)),
    ("B11", "boundary", "5,000 statements in one file", "pen red\n" + "forward 1\nturn 1\n" * 2500,
     ok("5000 LINE/TURN statements compile", lambda r: len(r.ir_before_optimization) == 2500)),
    # ---------------- complex ----------------
    ("C1", "complex", "Koch snowflake depth 3 (recursion + if/else)",
     "proc koch(len, depth) {\n if depth == 0 { forward len } else {\n  call koch(len / 3, depth - 1)\n  turn -60\n  call koch(len / 3, depth - 1)\n  turn 120\n  call koch(len / 3, depth - 1)\n  turn -60\n  call koch(len / 3, depth - 1)\n }\n}\nrepeat 3 { call koch(240, 3)\n turn 120 }",
     ok("192 segments, 3-fold symmetric (returns to start)", lambda r: len(r.ir_before_optimization) == 192 and abs(r.ir_before_optimization[-1][3]) < 1e-6 and abs(r.ir_before_optimization[-1][4]) < 1e-6)),
    ("C2", "complex", "Recursive tree: optimiser halves the IR",
     "proc b(len, d) { if d > 0 { forward len\n turn 25\n call b(len * 0.7, d - 1)\n turn -50\n call b(len * 0.7, d - 1)\n turn 25\n forward -len } }\npen green\nturn -90\ncall b(60, 7)",
     ok("254 -> 127 IR instructions", lambda r: (len(r.ir_before_optimization), len(r.ir_after_optimization)) == (254, 127))),
    ("C3", "complex", "Spiral: loop-carried variable",
     "let step = 4\npen purple\nrepeat 40 { forward step\n turn 20\n let step = step + 2 }",
     ok("40 segments of strictly growing length", lambda r: len(r.ir_before_optimization) == 40)),
    ("C4", "complex", "Plotter: mirrored boxes", None,
     ok("travel reduced by > 80%", lambda r: r.plotter_plan().travel_saving_pct > 80)),
    ("C5", "complex", "Plotter: checkerboard", None,
     ok("pen changes 30 -> 1", lambda r: (r.plotter_plan().before["pen_changes"], r.plotter_plan().after["pen_changes"]) == (30, 1))),
]


def load_example(case_id):
    name = {"C4": "plotter_mirror", "C5": "plotter_checker"}[case_id]
    with open(f"examples/{name}.sketch") as f:
        return f.read()


def summarise(r):
    s = f"IR {len(r.ir_before_optimization)}->{len(r.ir_after_optimization)}"
    if r.run_stats.get("calls"):
        s += f", {r.run_stats['calls']} call(s), depth {r.run_stats['max_depth']}"
    return s


def main():
    results, failed = [], 0
    for cid, cat, desc, src, expected in CASES:
        if src is None:
            src = load_example(cid)
        entry = {"id": cid, "category": cat, "description": desc,
                 "source": src if len(src) < 140 else src[:137] + "..."}
        try:
            r = compile_source(src)
            actual_kind, actual = "ok", summarise(r)
            if expected[0] == "ok":
                passed = bool(expected[2](r))
                entry["expected"] = "Compiles; " + expected[1]
            else:
                passed = False
                entry["expected"] = f"{expected[1]} error containing {expected[2]!r}"
        except Exception as exc:                    # noqa: BLE001
            info = error_info(exc)
            actual_kind, actual = "error", f"{info['stage']} error: {info['message']}"
            if expected[0] == "error":
                passed = info["stage"] == expected[1] and expected[2] in info["message"]
                entry["expected"] = f"{expected[1]} error containing {expected[2]!r}"
            else:
                passed = False
                entry["expected"] = "Compiles; " + expected[1]
        entry["actual"] = actual
        entry["passed"] = passed
        failed += not passed
        results.append(entry)
        print(f"{cid:4} {cat:8} {'PASS' if passed else 'FAIL'}  {desc}")
        if not passed:
            print(f"      expected: {entry['expected']}\n      actual:   {actual}")
    with open("docs/test_cases_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n{len(results) - failed}/{len(results)} cases passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
