import unittest

from sketchlang.optimizer import eliminate_dead_moves, merge_collinear_lines, optimize_ir


class TestEliminateDeadMoves(unittest.TestCase):
    def test_consecutive_moves_collapse_to_last(self):
        ir = [("MOVE", 1, 1), ("MOVE", 2, 2), ("MOVE", 3, 3)]
        self.assertEqual(eliminate_dead_moves(ir), [("MOVE", 3, 3)])

    def test_move_before_line_is_kept(self):
        ir = [("MOVE", 1, 1), ("LINE", 1, 1, 5, 1, "red")]
        self.assertEqual(eliminate_dead_moves(ir), ir)

    def test_empty_ir_is_unchanged(self):
        self.assertEqual(eliminate_dead_moves([]), [])


class TestMergeCollinearLines(unittest.TestCase):
    def test_two_collinear_same_color_segments_merge(self):
        ir = [("LINE", 0, 0, 40, 0, "purple"), ("LINE", 40, 0, 100, 0, "purple")]
        self.assertEqual(merge_collinear_lines(ir), [("LINE", 0, 0, 100, 0, "purple")])

    def test_non_collinear_segments_do_not_merge(self):
        ir = [("LINE", 0, 0, 10, 0, "red"), ("LINE", 10, 0, 10, 10, "red")]
        self.assertEqual(merge_collinear_lines(ir), ir)

    def test_different_colors_do_not_merge(self):
        ir = [("LINE", 0, 0, 10, 0, "red"), ("LINE", 10, 0, 20, 0, "blue")]
        self.assertEqual(merge_collinear_lines(ir), ir)

    def test_disconnected_segments_do_not_merge(self):
        ir = [("LINE", 0, 0, 10, 0, "red"), ("LINE", 20, 0, 30, 0, "red")]
        self.assertEqual(merge_collinear_lines(ir), ir)


class TestOptimizeIR(unittest.TestCase):
    def test_full_pipeline_on_dead_move_example(self):
        ir = [("MOVE", 10, 10), ("MOVE", 50, 50), ("MOVE", 100, 100), ("LINE", 100, 100, 140, 100, "black")]
        self.assertEqual(optimize_ir(ir), [("MOVE", 100, 100), ("LINE", 100, 100, 140, 100, "black")])

    def test_optimization_never_increases_instruction_count(self):
        ir = [
            ("LINE", 0, 0, 40, 0, "red"),
            ("LINE", 40, 0, 100, 0, "red"),
            ("MOVE", 5, 5),
            ("MOVE", 10, 10),
        ]
        self.assertLessEqual(len(optimize_ir(ir)), len(ir))


if __name__ == "__main__":
    unittest.main()
