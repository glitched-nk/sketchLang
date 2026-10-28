#!/usr/bin/env python3
"""
SketchLang web UI server (standard library only -- nothing to install).

    python3 server.py              # http://127.0.0.1:8000
    python3 server.py --port 9000

Endpoints
    GET  /                 the single-page UI (web/index.html)
    GET  /api/examples     the programs in examples/
    POST /api/compile      {source, group_colors}  -> every compiler stage's output as JSON
    POST /api/export       {source, target, group_colors, optimise} -> the full output file

The server only listens on localhost. It runs the same compile_source() as the
CLI and the tests; there is no separate "web version" of the compiler.
"""

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sketchlang import compile_source, error_info
from sketchlang.ir import MAX_CALL_DEPTH, MAX_IR_INSTRUCTIONS, MAX_STEPS

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
EXAMPLES = os.path.join(ROOT, "examples")

MAX_BODY = 1_000_000            # bytes of source accepted
PREVIEW_CHARS = 60_000          # output-code preview size sent to the browser
MAX_PLOT_POINTS = 30_000        # above this the plotter view is not drawn

FAILED_STRIP_INDEX = {"lexical": 0, "syntax": 1, "semantic": 2, "runtime": 3}
STRIP = ["lexer", "parser", "semantics", "ir_generation", "optimizer", "svg_codegen"]

EXAMPLE_TITLES = {
    "square": "Square, star and corner",
    "variables": "Variables and arithmetic",
    "spiral": "Spiral (loop-carried variable)",
    "dead_code_demo": "Dead moves removed",
    "procedures": "Flower from procedures",
    "koch": "Koch snowflake (recursion)",
    "tree": "Recursive tree (retrace removed)",
    "plotter_mirror": "Plotter: mirrored boxes",
    "plotter_checker": "Plotter: two-colour checkerboard",
}
ERROR_TITLES = {
    "error_lex_char": "Lexical: illegal character",
    "error_syntax_brace": "Syntax: missing brace",
    "error_undefined_var": "Semantic: undeclared variable",
    "error_bad_repeat": "Semantic: negative repeat count",
    "error_div_zero": "Semantic: division by zero",
    "error_undefined_proc": "Semantic: undefined procedure",
    "error_arg_count": "Semantic: wrong argument count",
    "error_scope": "Semantic: callee cannot see caller's variable",
    "error_runtime_recursion": "Runtime: infinite recursion",
    "error_runtime_div": "Runtime: division by zero",
}


def list_examples():
    out = []
    for fn in sorted(os.listdir(EXAMPLES)):
        if not fn.endswith(".sketch"):
            continue
        key = fn[:-7]
        with open(os.path.join(EXAMPLES, fn)) as f:
            src = f.read()
        if key in ERROR_TITLES:
            out.append({"key": key, "title": ERROR_TITLES[key], "group": "Errors", "source": src})
        else:
            out.append({"key": key, "title": EXAMPLE_TITLES.get(key, key), "group": "Programs", "source": src})
    out.sort(key=lambda e: (e["group"] != "Programs", list(EXAMPLE_TITLES).index(e["key"]) if e["key"] in EXAMPLE_TITLES
                            else list(ERROR_TITLES).index(e["key"]) if e["key"] in ERROR_TITLES else 99))
    return out


def symbols_json(result):
    tab = result.symbol_table
    return [{"name": n, "value": v, "line": tab.declaration_line(n)} for n, v in tab.as_dict().items()]


def procs_json(result):
    return [{"name": n, "params": p.args[1], "line": p.line, "statements": len(p.args[2])}
            for n, p in result.procs.items()]


def strokes_json(strokes):
    return [{"color": s.color, "points": [[round(x, 3), round(y, 3)] for x, y in s.points]} for s in strokes]


def compile_payload(source, group_colors=True):
    t0 = time.perf_counter()
    try:
        r = compile_source(source)
    except Exception as exc:                                  # noqa: BLE001
        info = error_info(exc)
        if info["stage"] == "internal":
            raise
        return {"ok": False, "error": info, "failed_strip_index": FAILED_STRIP_INDEX[info["stage"]],
                "strip": STRIP, "total_ms": round((time.perf_counter() - t0) * 1000, 2)}

    plan = r.plotter_plan(group_colors)
    gcode, gcounts = r.to_gcode(group_colors=group_colors, optimise=True)
    ps = r.to_postscript()

    points = sum(len(s.points) for s in plan.strokes_before) * 2
    plot = {"summary": plan.summary(), "drawn": points <= MAX_PLOT_POINTS}
    if plot["drawn"]:
        plot["before"] = strokes_json(plan.strokes_before)
        plot["after"] = strokes_json(plan.strokes_after)

    def preview(text):
        return {"text": text[:PREVIEW_CHARS], "truncated": len(text) > PREVIEW_CHARS, "chars": len(text)}

    return {
        "ok": True,
        "strip": STRIP,
        "timings": {k: round(v, 3) for k, v in r.timings.items()},
        "total_ms": round((time.perf_counter() - t0) * 1000, 2),
        "tokens": r.token_list()[:3000],
        "token_count": len(r.token_list()),
        "ast": r.ast_dict(),
        "symbols": symbols_json(r),
        "procs": procs_json(r),
        "ir_before": [list(i) for i in r.ir_before_optimization[:600]],
        "ir_after": [list(i) for i in r.ir_after_optimization[:600]],
        "ir_before_count": len(r.ir_before_optimization),
        "ir_after_count": len(r.ir_after_optimization),
        "passes": r.optimization_report,
        "run_stats": r.run_stats,
        "svg": r.svg,
        "plotter": plot,
        "gcode_counts": gcounts,
        "code": {"svg": preview(r.svg), "ps": preview(ps), "gcode": preview(gcode)},
        "limits": {"call_depth": MAX_CALL_DEPTH, "steps": MAX_STEPS, "ir": MAX_IR_INSTRUCTIONS},
    }


def export_payload(source, target, group_colors, optimise):
    r = compile_source(source)
    if target == "svg":
        return r.svg, "image/svg+xml", "sketch.svg"
    if target == "ps":
        return r.to_postscript(), "application/postscript", "sketch.ps"
    if target == "gcode":
        return r.to_gcode(group_colors=group_colors, optimise=optimise)[0], "text/plain", "sketch.gcode"
    raise ValueError("unknown target")


class Handler(BaseHTTPRequestHandler):
    server_version = "SketchLangUI/1.0"

    def log_message(self, fmt, *args):                        # quieter console during a demo
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, code, body, ctype, extra=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj), "application/json; charset=utf-8")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(WEB, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/api/examples":
            return self._json(list_examples())
        self._send(404, "Not found", "text/plain")

    def do_POST(self):
        path = self.path.split("?")[0]
        if path not in ("/api/compile", "/api/export"):
            return self._send(404, "Not found", "text/plain")
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY:
            return self._json({"ok": False, "error": {"stage": "input", "message": "Source is larger than 1 MB.", "line": None}}, 413)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            source = str(body.get("source", ""))
            group = bool(body.get("group_colors", True))
            if path == "/api/compile":
                return self._json(compile_payload(source, group))
            text, ctype, filename = export_payload(source, body.get("target", "svg"), group, bool(body.get("optimise", True)))
            return self._send(200, text, ctype + "; charset=utf-8",
                              {"Content-Disposition": f'attachment; filename="{filename}"'})
        except (ValueError, KeyError) as exc:
            return self._json({"ok": False, "error": {"stage": "input", "message": f"Bad request: {exc}", "line": None}}, 400)
        except Exception as exc:                              # noqa: BLE001 - never leak a traceback to the page
            sys.stderr.write(f"internal error: {exc!r}\n")
            return self._json({"ok": False, "error": {"stage": "internal", "message": f"Internal compiler error: {exc}", "line": None}}, 500)


def main():
    ap = argparse.ArgumentParser(description="SketchLang web UI")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"SketchLang UI running at http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
