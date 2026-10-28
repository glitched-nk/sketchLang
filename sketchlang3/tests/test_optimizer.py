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

from sketchlang.optimizer import (
    remove_zero_length_lines, eliminate_duplicate_segments, optimize_ir_with_report,
)


class TestPhase3Optimizer(unittest.TestCase):
    # regression for the Phase 2 bug found during boundary testing
    def test_backtracking_segments_are_not_merged(self):
        ir = [("LINE", 0, 0, 100, 0, "red"), ("LINE", 100, 0, 50, 0, "red")]
        self.assertEqual(merge_collinear_lines(ir), ir)

    def test_same_direction_still_merges(self):
        ir = [("LINE", 0, 0, 10, 0, "red"), ("LINE", 10, 0, 30, 0, "red")]
        self.assertEqual(merge_collinear_lines(ir), [("LINE", 0, 0, 30, 0, "red")])

    def test_zero_length_lines_removed(self):
        ir = [("LINE", 5, 5, 5, 5, "red"), ("LINE", 5, 5, 9, 5, "red")]
        self.assertEqual(remove_zero_length_lines(ir), [("LINE", 5, 5, 9, 5, "red")])

    def test_exact_retrace_is_removed(self):
        ir = [("LINE", 0, 0, 10, 0, "red"), ("LINE", 10, 0, 0, 0, "red")]
        self.assertEqual(eliminate_duplicate_segments(ir), [("LINE", 0, 0, 10, 0, "red")])

    def test_same_direction_repeat_is_also_a_duplicate(self):
        ir = [("LINE", 0, 0, 10, 0, "red"), ("LINE", 0, 0, 10, 0, "red")]
        self.assertEqual(len(eliminate_duplicate_segments(ir)), 1)

    def test_retrace_after_other_colour_is_kept(self):
        # a blue line crosses between the two red draws: removing the second red
        # would change which colour is on top at the crossing
        ir = [("LINE", 0, 0, 10, 0, "red"), ("LINE", 5, -5, 5, 5, "blue"), ("LINE", 10, 0, 0, 0, "red")]
        self.assertEqual(eliminate_duplicate_segments(ir), ir)

    def test_partial_overlap_is_not_a_duplicate(self):
        ir = [("LINE", 0, 0, 10, 0, "red"), ("LINE", 0, 0, 5, 0, "red")]
        self.assertEqual(len(eliminate_duplicate_segments(ir)), 2)

    def test_negative_zero_does_not_defeat_duplicate_detection(self):
        ir = [("LINE", 0.0, 0.0, 10.0, -0.0, "red"), ("LINE", 10.0, 0.0, -0.0, 0.0, "red")]
        self.assertEqual(len(eliminate_duplicate_segments(ir)), 1)

    def test_report_lists_every_pass_and_counts_drop(self):
        ir = [("MOVE", 1, 1), ("MOVE", 2, 2), ("LINE", 2, 2, 2, 2, "red"), ("LINE", 2, 2, 9, 2, "red")]
        out, report = optimize_ir_with_report(ir)
        self.assertEqual([r["pass"] for r in report],
                         ["zero-length lines", "duplicate segments", "dead moves", "collinear merge"])
        self.assertEqual(report[0]["before"], 4)
        self.assertEqual(report[-1]["after"], len(out))
        self.assertEqual(out, [("MOVE", 2, 2), ("LINE", 2, 2, 9, 2, "red")])

    def test_optimizer_is_idempotent(self):
        ir = [("LINE", 0, 0, 10, 0, "red"), ("LINE", 10, 0, 0, 0, "red"), ("LINE", 0, 0, 0, 7, "red")]
        once = optimize_ir(ir)
        self.assertEqual(optimize_ir(once), once)


if __name__ == "__main__":
    unittest.main()
