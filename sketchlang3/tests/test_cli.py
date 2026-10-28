import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
MAIN = os.path.join(ROOT, "main.py")


def run(*args):
    return subprocess.run([sys.executable, MAIN, *args], capture_output=True, text=True, cwd=ROOT)


class TestCLI(unittest.TestCase):
    def test_svg_default(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "o.svg")
            r = run("examples/square.sketch", "-o", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out) as f:
                self.assertIn("<svg", f.read())

    def test_gcode_target_reports_plan(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "o.gcode")
            r = run("examples/plotter_mirror.sketch", "-t", "gcode", "-o", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Plotter plan", r.stdout)
            with open(out) as f:
                self.assertIn("G21", f.read())

    def test_no_plotter_opt_message_matches_the_file_written(self):
        """Regression: --no-plotter-opt used to still print the OPTIMISED plan's savings,
        although the G-code written kept the original stroke order."""
        with tempfile.TemporaryDirectory() as d:
            plain, opt = os.path.join(d, "a.gcode"), os.path.join(d, "b.gcode")
            r1 = run("examples/plotter_checker.sketch", "-t", "gcode", "--no-plotter-opt", "-o", plain)
            r2 = run("examples/plotter_checker.sketch", "-t", "gcode", "-o", opt)
            self.assertIn("optimisation OFF", r1.stdout)
            self.assertNotIn("% less", r1.stdout)
            self.assertIn("% less", r2.stdout)
            with open(plain) as f1, open(opt) as f2:
                pauses = lambda f: sum(1 for line in f if line.startswith("M0"))
                self.assertEqual((pauses(f1), pauses(f2)), (31, 2))   # 30 colour changes + first pen load, vs 1 + 1

    def test_ps_target(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "o.ps")
            self.assertEqual(run("examples/koch.sketch", "-t", "ps", "-o", out).returncode, 0)
            with open(out) as f:
                self.assertTrue(f.read().startswith("%!PS"))

    def test_error_exit_code_and_message(self):
        r = run("examples/error_scope.sketch")
        self.assertEqual(r.returncode, 1)
        self.assertIn("semantic error", r.stdout)
        self.assertIn("size", r.stdout)

    def test_runtime_error_is_reported_not_a_traceback(self):
        r = run("examples/error_runtime_recursion.sketch")
        self.assertEqual(r.returncode, 1)
        self.assertIn("runtime error", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_show_ast_flag(self):
        r = run("examples/procedures.sketch", "--show-ast", "-o", os.devnull)
        self.assertIn("PROC petal(len)", r.stdout)


if __name__ == "__main__":
    unittest.main()
