import re
import unittest

from sketchlang.codegen import generate_svg


class TestCodegen(unittest.TestCase):
    def test_emits_one_line_element_per_line_instruction(self):
        ir = [("LINE", 0, 0, 10, 0, "red"), ("LINE", 10, 0, 10, 10, "blue")]
        svg = generate_svg(ir)
        self.assertEqual(svg.count("<line "), 2)
        self.assertIn('stroke="red"', svg)
        self.assertIn('stroke="blue"', svg)

    def test_move_instructions_produce_no_visible_element(self):
        ir = [("MOVE", 5, 5), ("LINE", 5, 5, 15, 5, "black")]
        svg = generate_svg(ir)
        self.assertEqual(svg.count("<line "), 1)

    def test_output_is_well_formed_svg_root(self):
        svg = generate_svg([("LINE", 0, 0, 10, 0, "black")])
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)
        self.assertIn("viewBox=", svg)

    def test_viewbox_grows_to_fit_large_drawings(self):
        small = generate_svg([("LINE", 0, 0, 10, 0, "black")])
        large = generate_svg([("LINE", 0, 0, 500, 500, "black")])

        def width_of(svg):
            return float(re.search(r'width="(\d+)"', svg).group(1))

        self.assertGreater(width_of(large), width_of(small))

    def test_empty_ir_still_produces_valid_svg(self):
        svg = generate_svg([])
        self.assertTrue(svg.startswith("<svg"))
        self.assertEqual(svg.count("<line "), 0)


if __name__ == "__main__":
    unittest.main()
