"""
Symbol Table Management
========================
SketchLang has a single flat scope (no functions/blocks with their own
scope in Phase 2), so the symbol table is a simple name -> (value, line)
map. It is used two ways:

  * semantics.py makes a static pass over the program, in program order,
    to catch references to undeclared variables before any code is
    generated.
  * ir.py walks the AST a second time to actually *execute* it (so that
    "repeat" loops and variable re-assignment inside a loop behave the
    way a programmer would expect, e.g. a spiral whose step size grows
    every iteration).

Both passes share the same evaluate_expr() logic in semantics.py; each
just carries its own SymbolTable instance.
"""


class UndefinedVariableError(KeyError):
    pass


class SymbolTable:
    def __init__(self):
        self._table = {}  # name -> (value, decl_line)

    def declare(self, name, value, line):
        """Insert or update a variable's value (SketchLang allows re-assignment)."""
        self._table[name] = (value, line)

    def is_declared(self, name):
        return name in self._table

    def lookup(self, name):
        if name not in self._table:
            raise UndefinedVariableError(name)
        return self._table[name][0]

    def declaration_line(self, name):
        return self._table[name][1]

    def as_dict(self):
        """Return a plain {name: value} snapshot, mainly for tests/debugging."""
        return {name: value for name, (value, _line) in self._table.items()}

    def __contains__(self, name):
        return self.is_declared(name)

    def __len__(self):
        return len(self._table)
