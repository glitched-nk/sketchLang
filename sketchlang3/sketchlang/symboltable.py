"""
Symbol Table Management
=======================
A SymbolTable is one *scope*: a name -> (value, declaration line) map with an
optional parent scope. Scopes form a chain:

    global scope  <--  call frame of proc 'square'  <--  (frame of a nested call is
                                                          also parented to *global*,
                                                          not to the caller)

That last point is lexical scoping: a procedure sees its own parameters and
locals plus the global variables, never the variables of whoever called it.

Rules used by both the static checker (semantics.py) and the executor (ir.py):

  * lookup(name)  walks the chain from the innermost scope outwards.
  * declare(name) always writes to the *innermost* scope, so a 'let' inside a
    procedure creates/updates a local and can never overwrite a global.
  * repeat / if blocks do not open a scope; only procedure calls do.

In the static checker a value of None means "unknown at compile time"
(constant propagation); the executor always stores real numbers.
"""


class UndefinedVariableError(KeyError):
    pass


class SymbolTable:
    def __init__(self, parent=None, name="global"):
        self._table = {}          # name -> (value, decl_line)
        self.parent = parent
        self.name = name

    # -- writing ---------------------------------------------------------------
    def declare(self, name, value, line):
        """Insert or update `name` in THIS scope (re-assignment is allowed)."""
        self._table[name] = (value, line)

    # -- reading ---------------------------------------------------------------
    def declared_locally(self, name):
        return name in self._table

    def is_declared(self, name):
        scope = self
        while scope is not None:
            if name in scope._table:
                return True
            scope = scope.parent
        return False

    def _find(self, name):
        scope = self
        while scope is not None:
            if name in scope._table:
                return scope
            scope = scope.parent
        raise UndefinedVariableError(name)

    def lookup(self, name):
        return self._find(name)._table[name][0]

    def declaration_line(self, name):
        return self._find(name)._table[name][1]

    # -- helpers for the static checker's branch analysis ------------------------
    def snapshot(self):
        return dict(self._table)

    def restore(self, snap):
        self._table = dict(snap)

    def local_names(self):
        return set(self._table)

    def as_dict(self):
        """Plain {name: value} snapshot of THIS scope (tests, CLI, web UI)."""
        return {name: value for name, (value, _line) in self._table.items()}

    def __contains__(self, name):
        return self.is_declared(name)

    def __len__(self):
        return len(self._table)
