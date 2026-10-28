import unittest

from sketchlang.lexer import tokenize
from sketchlang.parser import parse
from sketchlang.semantics import check_semantics, SemanticError


def check(source):
    return check_semantics(parse(tokenize(source)))


class TestSemantics(unittest.TestCase):
    def test_valid_program_passes(self):
        symtab = check("let side = 50\npen blue\nrepeat 4 {\n forward side\n turn 90\n}")
        self.assertEqual(symtab.lookup("side"), 50.0)

    def test_unknown_color_is_rejected(self):
        with self.assertRaises(SemanticError) as ctx:
            check("pen skyblue\nforward 10")
        self.assertIn("unknown color", str(ctx.exception))

    def test_undefined_variable_is_rejected(self):
        with self.assertRaises(SemanticError) as ctx:
            check("pen red\nforward radius")
        self.assertIn("used before it is declared", str(ctx.exception))

    def test_variable_usable_after_declaration(self):
        symtab = check("let radius = 20\npen red\nforward radius")
        self.assertEqual(symtab.lookup("radius"), 20.0)

    def test_repeat_count_must_be_positive(self):
        with self.assertRaises(SemanticError) as ctx:
            check("repeat -3 {\n forward 10\n}")
        self.assertIn("positive whole number", str(ctx.exception))

    def test_repeat_count_must_be_whole_number(self):
        with self.assertRaises(SemanticError):
            check("repeat 2.5 {\n forward 10\n}")

    def test_division_by_zero_is_rejected(self):
        with self.assertRaises(SemanticError) as ctx:
            check("let a = 10\nlet b = 0\nforward a / b")
        self.assertIn("division by zero", str(ctx.exception))

    def test_expression_evaluated_correctly(self):
        symtab = check("let x = 2 + 3 * 4\nforward x")
        self.assertEqual(symtab.lookup("x"), 14.0)

    def test_variable_can_be_reassigned(self):
        symtab = check("let step = 4\nlet step = step + 6\nforward step")
        self.assertEqual(symtab.lookup("step"), 10.0)

    # ---- Phase 3 additions: procedures, scope, constant propagation ----------
    def test_call_before_definition_is_allowed(self):
        check("call f(1)\nproc f(n) { forward n }")

    def test_undefined_procedure(self):
        with self.assertRaises(SemanticError) as ctx:
            check("call nothing(1)")
        self.assertIn("undefined procedure", str(ctx.exception))

    def test_wrong_argument_count(self):
        with self.assertRaises(SemanticError) as ctx:
            check("proc f(a, b) { forward a }\ncall f(1)")
        self.assertIn("expects 2", str(ctx.exception))

    def test_duplicate_procedure(self):
        with self.assertRaises(SemanticError) as ctx:
            check("proc f() { forward 1 }\nproc f() { forward 2 }")
        self.assertIn("already defined", str(ctx.exception))

    def test_duplicate_parameter(self):
        with self.assertRaises(SemanticError):
            check("proc f(a, a) { forward a }")

    def test_parameters_are_visible_inside_body(self):
        check("proc f(n) { forward n * 2 }")

    def test_parameter_not_visible_outside_procedure(self):
        with self.assertRaises(SemanticError):
            check("proc f(n) { forward n }\nforward n")

    def test_callee_cannot_see_callers_locals(self):
        with self.assertRaises(SemanticError):
            check("proc inner() { forward size }\nproc outer(size) { call inner() }")

    def test_procedure_can_read_earlier_global(self):
        check("let g = 5\nproc f() { forward g }")

    def test_procedure_cannot_read_global_declared_after_it(self):
        with self.assertRaises(SemanticError):
            check("proc f() { forward g }\nlet g = 5")

    def test_let_inside_proc_does_not_leak_to_global(self):
        with self.assertRaises(SemanticError):
            check("proc f() { let t = 1 }\ncall f()\nforward t")

    def test_let_inside_proc_does_not_change_global_symbol(self):
        tab = check("let g = 5\nproc f() { let g = 9 }\ncall f()")
        self.assertEqual(tab.lookup("g"), 5.0)

    def test_loop_assigned_variable_becomes_unknown(self):
        tab = check("let step = 1\nrepeat 3 {\n let step = step + 1\n}")
        self.assertIsNone(tab.lookup("step"))       # not the stale value 2

    def test_variable_untouched_by_loop_stays_known(self):
        tab = check("let side = 7\nrepeat 3 { forward side }")
        self.assertEqual(tab.lookup("side"), 7.0)

    def test_known_repeat_count_checked_at_compile_time(self):
        with self.assertRaises(SemanticError):
            check("let n = 0 - 2\nrepeat n { forward 1 }")

    def test_parameter_repeat_count_is_deferred_to_runtime(self):
        check("proc f(n) { repeat n { forward 1 } }\ncall f(-3)")   # compiles; fails when run

    def test_parameter_division_is_deferred_to_runtime(self):
        check("proc f(a, b) { forward a / b }\ncall f(1, 0)")

    def test_known_zero_divisor_through_expression(self):
        with self.assertRaises(SemanticError):
            check("let z = 3 - 3\nforward 5 / z")

    def test_new_variable_declared_in_both_branches_is_defined_after_if(self):
        check("if 1 < 2 { let t = 1 } else { let t = 2 }\nforward t")

    def test_new_variable_declared_in_one_branch_is_not_defined_after_if(self):
        with self.assertRaises(SemanticError):
            check("if 1 < 2 { let t = 1 }\nforward t")

    def test_condition_operands_are_checked(self):
        with self.assertRaises(SemanticError):
            check("if ghost > 1 { forward 1 }")

    def test_body_of_unused_procedure_is_still_checked(self):
        with self.assertRaises(SemanticError):
            check("proc never_called() { pen notacolor }")

    def test_recursion_is_allowed_statically(self):
        check("proc f(n) { if n > 0 { call f(n - 1) } }\ncall f(3)")


if __name__ == "__main__":
    unittest.main()
