import math
import unittest

from sketchlang.lexer import tokenize
from sketchlang.parser import parse
from sketchlang.ir import generate_ir


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


if __name__ == "__main__":
    unittest.main()
