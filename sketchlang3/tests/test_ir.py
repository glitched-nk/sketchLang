import math
import os
import unittest

from sketchlang.lexer import tokenize
from sketchlang.parser import parse
from sketchlang.ir import generate_ir


EX = os.path.join(os.path.dirname(__file__), '..', 'examples')


def ir_for(source):
    return generate_ir(parse(tokenize(source)))


class TestIRGeneration(unittest.TestCase):
    def test_single_forward_produces_one_line(self):
        ir = ir_for("pen red\nforward 100")
        self.assertEqual(ir, [("LINE", 0.0, 0.0, 100.0, 0.0, "red")])

    def test_turn_changes_direction_of_next_forward(self):
        ir = ir_for("pen black\nforward 10\nturn 90\nforward 10")
        self.assertEqual(len(ir), 2)
        _, x1, y1, x2, y2, _ = ir[1]
        # after turning 90 degrees the second segment should be roughly vertical
        self.assertAlmostEqual(x2 - x1, 0.0, places=6)
        self.assertAlmostEqual(y2 - y1, 10.0, places=6)

    def test_move_emits_move_instruction_without_drawing(self):
        ir = ir_for("move 5, 5\npen red\nforward 10")
        self.assertEqual(ir[0], ("MOVE", 5.0, 5.0))
        self.assertEqual(ir[1][:3], ("LINE", 5.0, 5.0))

    def test_repeat_expands_body_n_times(self):
        ir = ir_for("pen blue\nrepeat 4 {\n forward 10\n turn 90\n}")
        self.assertEqual(len(ir), 4)

    def test_variable_used_in_forward_distance(self):
        ir = ir_for("let side = 30\npen red\nforward side")
        self.assertEqual(ir, [("LINE", 0.0, 0.0, 30.0, 0.0, "red")])

    def test_variable_reassigned_each_loop_iteration(self):
        # "step" grows by 1 every iteration -- this only works if the IR
        # generator's symbol table is live across iterations, not static.
        ir = ir_for("let step = 1\npen black\nrepeat 3 {\n forward step\n let step = step + 1\n}")
        lengths = [math.hypot(x2 - x1, y2 - y1) for (_, x1, y1, x2, y2, _c) in ir]
        self.assertEqual([round(l) for l in lengths], [1, 2, 3])

    def test_square_returns_to_origin(self):
        ir = ir_for("pen blue\nrepeat 4 {\n forward 100\n turn 90\n}")
        last = ir[-1]
        self.assertAlmostEqual(last[3], 0.0, places=6)
        self.assertAlmostEqual(last[4], 0.0, places=6)


from sketchlang.ir import SketchRuntimeError, MAX_CALL_DEPTH


class TestProceduresAtRuntime(unittest.TestCase):
    def test_call_binds_parameters(self):
        ir = ir_for("pen red\nproc f(n) { forward n }\ncall f(25)")
        self.assertEqual(ir, [("LINE", 0.0, 0.0, 25.0, 0.0, "red")])

    def test_arguments_evaluated_in_callers_scope(self):
        ir = ir_for("proc f(n) { forward n }\nlet a = 4\ncall f(a * 2)")
        self.assertEqual(ir[0][3], 8.0)

    def test_procedure_changes_turtle_state_like_logo(self):
        ir = ir_for("proc step() { forward 10\n turn 90 }\ncall step()\ncall step()")
        self.assertAlmostEqual(ir[1][3], 10.0, places=6)
        self.assertAlmostEqual(ir[1][4], 10.0, places=6)

    def test_local_let_does_not_modify_global(self):
        ir = ir_for("let n = 5\nproc f() { let n = 1\n forward n }\ncall f()\nforward n")
        self.assertEqual(ir[0][3], 1.0)     # the local n
        self.assertEqual(ir[1][3] - ir[1][1], 5.0)   # global n untouched

    def test_nested_calls(self):
        ir = ir_for("proc a() { forward 1 }\nproc b() { call a()\n call a() }\ncall b()")
        self.assertEqual(len(ir), 2)

    def test_if_else_picks_branch(self):
        ir = ir_for("let a = 3\nif a > 2 { forward 10 } else { forward 20 }")
        self.assertEqual(ir[0][3], 10.0)
        ir = ir_for("let a = 1\nif a > 2 { forward 10 } else { forward 20 }")
        self.assertEqual(ir[0][3], 20.0)

    def test_recursion_with_base_case_terminates(self):
        stats = {}
        ir = ir_for_stats("proc f(n) { if n > 0 { forward 1\n call f(n - 1) } }\ncall f(5)", stats)
        self.assertEqual(len(ir), 5)
        self.assertEqual(stats["max_depth"], 6)
        self.assertEqual(stats["calls"], 6)

    def test_koch_segment_count(self):
        with open(os.path.join(EX, "koch.sketch")) as f:
            src = f.read()
        # 3 sides x 4^3 segments
        self.assertEqual(len(ir_for(src)), 3 * 4 ** 3)

    def test_infinite_recursion_hits_call_depth_limit(self):
        with self.assertRaises(SketchRuntimeError) as ctx:
            ir_for("proc f(n) { call f(n) }\ncall f(1)")
        self.assertIn("maximum call depth", str(ctx.exception))
        self.assertIn(str(MAX_CALL_DEPTH), str(ctx.exception))

    def test_recursion_exactly_at_limit_is_ok(self):
        ir_for("proc f(n) { if n > 0 { call f(n - 1) } }\ncall f(%d)" % (MAX_CALL_DEPTH - 1))

    def test_runtime_division_by_zero(self):
        with self.assertRaises(SketchRuntimeError) as ctx:
            ir_for("proc r(a, b) { forward a / b }\ncall r(1, 0)")
        self.assertIn("division by zero", str(ctx.exception))

    def test_runtime_repeat_count_check(self):
        with self.assertRaises(SketchRuntimeError):
            ir_for("proc f(n) { repeat n { forward 1 } }\ncall f(2.5)")
        with self.assertRaises(SketchRuntimeError):
            ir_for("proc f(n) { repeat n { forward 1 } }\ncall f(0)")

    def test_step_limit_stops_endless_looking_programs(self):
        with self.assertRaises(SketchRuntimeError) as ctx:
            ir_for("repeat 100000 { repeat 100000 { let a = 1 } }")
        self.assertIn("step limit", str(ctx.exception))

    def test_instruction_limit(self):
        with self.assertRaises(SketchRuntimeError) as ctx:
            ir_for("repeat 1000 { repeat 1000 { forward 1 } }")
        self.assertIn("instructions", str(ctx.exception))

    def test_numeric_overflow_is_a_runtime_error_not_inf(self):
        with self.assertRaises(SketchRuntimeError) as ctx:
            ir_for("forward 1" + "0" * 400)
        self.assertIn("overflow", str(ctx.exception))
        with self.assertRaises(SketchRuntimeError):
            ir_for("let a = 1" + "0" * 200 + "\nlet b = a * a * a * a\nforward b")

    def test_large_coordinates_do_not_crash(self):
        ir = ir_for("pen red\nforward 1000000000")
        self.assertEqual(ir[0][3], 1e9)


def ir_for_stats(source, stats):
    return generate_ir(parse(tokenize(source)), stats)


if __name__ == "__main__":
    unittest.main()
