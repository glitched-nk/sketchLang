import unittest

from sketchlang.symboltable import SymbolTable, UndefinedVariableError


class TestSymbolTable(unittest.TestCase):
    def test_declare_and_lookup(self):
        t = SymbolTable()
        t.declare("x", 5.0, 1)
        self.assertEqual(t.lookup("x"), 5.0)
        self.assertEqual(t.declaration_line("x"), 1)

    def test_lookup_missing_raises(self):
        with self.assertRaises(UndefinedVariableError):
            SymbolTable().lookup("nope")

    def test_child_sees_parent_but_not_vice_versa(self):
        g = SymbolTable()
        g.declare("g", 1.0, 1)
        f = SymbolTable(parent=g, name="f")
        f.declare("local", 2.0, 2)
        self.assertEqual(f.lookup("g"), 1.0)
        self.assertTrue(f.is_declared("g"))
        self.assertFalse(g.is_declared("local"))

    def test_declare_writes_innermost_scope_only(self):
        g = SymbolTable()
        g.declare("x", 1.0, 1)
        f = SymbolTable(parent=g)
        f.declare("x", 99.0, 2)          # shadows, does not overwrite the global
        self.assertEqual(f.lookup("x"), 99.0)
        self.assertEqual(g.lookup("x"), 1.0)
        self.assertTrue(f.declared_locally("x"))

    def test_snapshot_and_restore(self):
        t = SymbolTable()
        t.declare("a", 1.0, 1)
        snap = t.snapshot()
        t.declare("b", 2.0, 2)
        t.restore(snap)
        self.assertEqual(t.local_names(), {"a"})

    def test_as_dict_is_local_only(self):
        g = SymbolTable()
        g.declare("g", 1.0, 1)
        f = SymbolTable(parent=g)
        f.declare("l", 2.0, 1)
        self.assertEqual(f.as_dict(), {"l": 2.0})
        self.assertIn("g", f)
        self.assertEqual(len(f), 1)


if __name__ == "__main__":
    unittest.main()
