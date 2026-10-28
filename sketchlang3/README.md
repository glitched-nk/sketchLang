# SketchLang (Phase 3)

A compiler for a turtle-graphics drawing language, with a plotter-aware back-end optimizer
and a web "Pipeline Inspector". Python 3 only; no packages needed.

## Run the web UI (for the demo)
    python3 server.py            # then open http://127.0.0.1:8000
    python3 server.py --port 9000

## Command line
    python3 main.py examples/procedures.sketch                      # -> output.svg
    python3 main.py examples/tree.sketch --stats
    python3 main.py examples/plotter_checker.sketch -t gcode -o job.gcode
    python3 main.py examples/koch.sketch -t ps -o koch.ps
    options: --no-plotter-opt  --no-color-grouping  --show-ast --show-ir --show-symbols

## Tests
    python3 -m unittest discover -s tests     # 222 tests (cairosvg optional for one test)
    python3 run_cases.py                      # 47 black-box cases
    python3 benchmark.py                      # benchmark

## Layout
sketchlang/ compiler, tests/, examples/, web/index.html, server.py, main.py, docs/ (results, screenshots)

The G-code was generated and inspected but not run on a physical plotter.
