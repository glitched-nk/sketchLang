"""
Visualisation helpers: turn compiler data structures into plain JSON-friendly
dicts/strings for the web UI, the CLI (--show-ast) and the report.
"""


def _label(node):
    k, a = node.kind, node.args
    if k == "PROC":
        return f"PROC {a[0]}({', '.join(a[1])})"
    if k == "PEN":
        return f"PEN {a[0]}"
    if k == "LET":
        return f"LET {a[0]}"
    if k == "CALL":
        return f"CALL {a[0]}"
    if k == "COND":
        return f"COND {a[0]}"
    if k == "BINOP":
        return f"BINOP {a[0]}"
    if k == "NUM":
        return f"NUM {a[0]:g}"
    if k == "VAR":
        return f"VAR {a[0]}"
    return k


def _children(node):
    k, a = node.kind, node.args
    if k == "PROGRAM":
        return list(a)
    if k == "PROC":
        return list(a[2])
    if k in ("FORWARD", "TURN", "NEG"):
        return [a[0]]
    if k == "MOVE":
        return [a[0], a[1]]
    if k == "LET":
        return [a[1]]
    if k == "REPEAT":
        return [a[0]] + list(a[1])
    if k == "CALL":
        return list(a[1])
    if k == "COND":
        return [a[1], a[2]]
    if k == "BINOP":
        return [a[1], a[2]]
    if k == "IF":
        then_group = {"label": "THEN", "children": [ast_to_dict(c) for c in a[1]]}
        kids = [a[0], then_group]
        if a[2]:
            kids.append({"label": "ELSE", "children": [ast_to_dict(c) for c in a[2]]})
        return kids
    return []


def ast_to_dict(node):
    """AST -> nested {'label', 'line', 'children'} dict."""
    if isinstance(node, dict):
        return node
    return {
        "label": _label(node),
        "line": node.line,
        "children": [c if isinstance(c, dict) else ast_to_dict(c) for c in _children(node)],
    }


def ast_to_text(node, indent=0):
    """Indented text dump (used by the CLI and the report)."""
    d = ast_to_dict(node)

    def rec(d, depth):
        lines = ["  " * depth + d["label"]]
        for c in d["children"]:
            lines.extend(rec(c, depth + 1))
        return lines

    return "\n".join(rec(d, indent))


def tokens_to_list(tokens):
    return [{"kind": t.kind, "value": t.value, "line": t.line} for t in tokens if t.kind != "EOF"]
