"""RPN evaluator + LaTeX renderer."""

from dataclasses import dataclass, field
from typing import Optional

from scifind_lib.dimensions import (
    build_dimension_symbol_triplet,
    compute_rpn_dimensions,
    format_dimension_number,
    format_dimensions_latex,
)
from scifind_lib.i18n import localise
from scifind_lib.parser import _CHAINABLE_RELATIONALS, _parse_paren_arg, parse_equation


_RANGED_OPS = ("sum", "int", "prod", "oint")


@dataclass
class FormulaNode:
    """A node in the parsed formula tree.

    `paren_arg` (operator nodes) lists which operands may be wrapped in
    \\left(...\\right); `_paren_wrap` marks nodes that came from a source
    (...) group and must keep their parens.
    """
    kind: str
    children: list = field(default_factory=list)
    quantity_id: Optional[str] = None
    constant_id: Optional[str] = None
    value: Optional[float] = None
    label: Optional[str] = None
    symbol_overwrite: Optional[str] = None
    name_overwrite: Optional[str] = None
    operator_id: Optional[str] = None
    symbol: Optional[str] = None
    arity: int = 0
    precedence: int = 0
    associativity: str = "left"
    operator_type: str = "infix"
    paren_arg: Optional[list] = None
    _paren_wrap: bool = False


def _load_row(conn, table, columns, key):
    row = conn.execute(
        f"SELECT {columns} FROM {table} WHERE id = ?", (key,)
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown {table.rstrip('s')}: {key!r}")
    return dict(row)


def _load_operator(conn, operator_id):
    return _load_row(conn, "operator",
                  "id, symbol, arity, precedence, associativity, operator_type, paren_arg",
                  operator_id)


def _load_constant(conn, constant_id):
    return _load_row(conn, "constant",
                  "id, name, symbol, value, unit_id, compound_unit_id",
                  constant_id)


def _load_quantity(conn, quantity_id):
    return _load_row(conn, "quantity",
                  "id, name, symbol, symbol_overwrite",
                  quantity_id)


def reduce_rpn_to_tree(conn, tokens):
    """Reduce a token stream to an expression tree."""
    stack = []
    for tok in tokens:
        kind = tok["token_kind"]
        if kind == "operator":
            op = _load_operator(conn, tok["operator_id"])
            if len(stack) < op["arity"]:
                raise ValueError(
                    f"RPN underflow at {tok['operator_id']}: need {op['arity']}, have {len(stack)}"
                )
            args = [stack.pop() for _ in range(op["arity"])][::-1]
            new_node = FormulaNode(
                kind="operator",
                children=args,
                operator_id=op["id"],
                symbol=op["symbol"],
                arity=op["arity"],
                precedence=op["precedence"],
                associativity=op["associativity"],
                operator_type=op["operator_type"],
                paren_arg=_parse_paren_arg(op["paren_arg"], op["arity"], op["id"]),
                _paren_wrap=bool(tok.get("_paren_wrap")),
            )
            if (
                op["operator_type"] == "relational"
                and op["id"] in _CHAINABLE_RELATIONALS
                and len(args) == 2
                and args[1].kind == "operator"
                and args[1].operator_id == op["id"]
                and args[1].operator_type == "relational"
            ):
                inner = args[1]
                new_node.children = [args[0]] + list(inner.children)
                new_node.arity = len(new_node.children)
                new_node._paren_wrap = inner._paren_wrap
            stack.append(new_node)
        elif kind == "quantity":
            stack.append(FormulaNode(
                kind="quantity",
                quantity_id=tok["quantity_id"],
                label=tok.get("label"),
                symbol_overwrite=tok.get("symbol_overwrite"),
                name_overwrite=tok.get("name_overwrite"),
                _paren_wrap=bool(tok.get("_paren_wrap")),
            ))
        elif kind == "constant":
            stack.append(FormulaNode(
                kind="constant",
                constant_id=tok["constant_id"],
                _paren_wrap=bool(tok.get("_paren_wrap")),
            ))
        elif kind == "number":
            stack.append(FormulaNode(
                kind="number",
                value=tok["value"],
                _paren_wrap=bool(tok.get("_paren_wrap")),
            ))
        else:
            raise ValueError(f"unknown token kind: {tok!r}")
    if not stack:
        return None
    if len(stack) > 1:
        raise ValueError(f"RPN did not reduce: {len(stack)} items left on stack")
    return stack[0]


def _latex_quantity(node, conn, locale):
    if not node.quantity_id:
        return "?"
    if node.quantity_id == "drop":
        return ""
    q = _load_quantity(conn, node.quantity_id)
    sym = localise(node.symbol_overwrite or "", locale) or q["symbol"]
    if not sym:
        return ""
    label = localise(node.label or "", locale)
    if label and "_" not in sym:
        return sym + "_{" + label + "}"
    return sym


def _latex_constant(node, conn):
    c = _load_constant(conn, node.constant_id)
    return c["symbol"] or c["id"]


def _latex_number(node):
    if node.value is None:
        return "?"
    v = node.value
    if v < 0:
        return "-" + _latex_number(FormulaNode(kind="number", value=-v))
    if v == int(v):
        return str(int(v))
    from fractions import Fraction
    try:
        f = Fraction(v).limit_denominator(100)
    except (ValueError, ZeroDivisionError, OverflowError):
        return format_dimension_number(v)
    if f.denominator != 1 and f.numerator == 1 and f.denominator < 20:
        return "\\frac{1}{" + str(f.denominator) + "}"
    return format_dimension_number(v)


def _latex_ranged_op(node, conn, locale):
    """Render `\\op_{from}^{to}{body}` for sum/int/prod/oint."""
    lo = _latex_node(node.children[0], conn, locale)
    hi = _latex_node(node.children[1], conn, locale)
    body = _latex_node(node.children[2], conn, locale)
    if not body:
        return ""
    op = f"\\{node.operator_id}"
    if not lo and not hi:
        return f"{op}{{{body}}}"
    if not lo:
        return f"{op}^{{{hi}}}{{{body}}}"
    if not hi:
        return f"{op}_{{{lo}}}{{{body}}}"
    return f"{op}_{{{lo}}}^{{{hi}}}{{{body}}}"


def _needs_paren(child, parent, side):
    """Precedence/associativity check for wrapping a child operand."""
    if child.kind != "operator":
        return False
    if child.operator_type == "relational":
        return True
    if child.precedence < parent.precedence:
        return True
    if child.precedence == parent.precedence:
        if parent.associativity == "none":
            return True
        if parent.associativity == "left" and side == "right":
            return True
        if parent.associativity == "right" and side == "left":
            return True
    return False


def _wrap_in_parens(child_str, child, parent, side):
    """Wrap child in `\\left(...\\right)` per paren_arg / precedence / source parens."""
    side_idx = 0 if side == "child" else (0 if side == "left" else 1)
    paren_arg = parent.paren_arg or [True] * parent.arity
    if side_idx >= len(paren_arg) or not paren_arg[side_idx]:
        return child_str
    if _needs_paren(child, parent, side):
        return "\\left(" + child_str + "\\right)"
    if child._paren_wrap and child.kind == "operator" \
            and not child_str.startswith("\\left("):
        return "\\left(" + child_str + "\\right)"
    return child_str


def _render_binary(node, conn, locale):
    if node.arity != 2:
        raise ValueError(f"{node.operator_type} op {node.operator_id} arity {node.arity}")
    left, right = node.children
    left_latex = _latex_node(left, conn, locale)
    right_latex = _latex_node(right, conn, locale)
    left_latex = _wrap_in_parens(left_latex, left, node, "left")
    right_latex = _wrap_in_parens(right_latex, right, node, "right")
    return left_latex, right_latex


def _render_child(node, conn, locale):
    child_latex = _latex_node(node.children[0], conn, locale)
    return _wrap_in_parens(child_latex, node.children[0], node, "child")


def _latex_infix(node, conn, locale):
    if node.operator_id == "sqrt":
        radicand = _latex_node(node.children[0], conn, locale)
        index = node.children[1]
        if not radicand:
            return ""
        is_default = (index.kind == "number" and index.value == 2)
        if is_default:
            return f"\\sqrt{{{radicand}}}"
        idx = _latex_node(index, conn, locale)
        if not idx:
            return f"\\sqrt{{{radicand}}}"
        return f"\\sqrt[{idx}]{{{radicand}}}"
    if node.operator_id == "sub":
        left, right = node.children
        left_latex = _latex_node(left, conn, locale)
        right_latex = _latex_node(right, conn, locale)
        if left.kind == "quantity" and left.quantity_id == "drop":
            right_latex = _wrap_in_parens(right_latex, right, node, "right")
            return f"-{right_latex}"
        left_latex = _wrap_in_parens(left_latex, left, node, "left")
        right_latex = _wrap_in_parens(right_latex, right, node, "right")
        return f"{left_latex} - {right_latex}"
    if node.operator_id == "log":
        base_node = node.children[0]
        arg = _latex_node(node.children[1], conn, locale)
        if not arg:
            return ""
        if base_node.kind == "constant" and base_node.constant_id == "euler_e":
            return f"\\ln{{{arg}}}"
        base = _latex_node(base_node, conn, locale)
        if not base:
            return f"\\log{{{arg}}}"
        return f"\\log_{{{base}}}{{{arg}}}"
    if node.operator_id in _RANGED_OPS:
        return _latex_ranged_op(node, conn, locale)
    if node.operator_id == "lim":
        var = _latex_node(node.children[0], conn, locale)
        val = _latex_node(node.children[1], conn, locale)
        body = _latex_node(node.children[2], conn, locale)
        if not body:
            return ""
        if not var or not val:
            return f"\\lim{{{body}}}"
        return f"\\lim_{{{var} \\to {val}}}{{{body}}}"
    left, right = node.children
    if node.operator_id == "frac":
        left_latex = _latex_node(left, conn, locale)
        right_latex = _latex_node(right, conn, locale)
        return f"\\frac{{{left_latex}}}{{{right_latex}}}"
    if node.operator_id == "pow":
        left_latex = _latex_node(left, conn, locale)
        right_latex = _latex_node(right, conn, locale)
        left_latex = _wrap_in_parens(left_latex, left, node, "left")
        right_latex = _wrap_in_parens(right_latex, right, node, "right")
        return f"{left_latex}^{{{right_latex}}}"
    left_latex, right_latex = _render_binary(node, conn, locale)
    if node.symbol:
        return f"{left_latex} {node.symbol} {right_latex}"
    if left.kind == "number" and right.kind == "number":
        return f"{left_latex} \\times {right_latex}"
    if left.kind == "number":
        if right.kind == "operator" and right.operator_id == "frac":
            return f"{left_latex}\\,\\frac{{{_latex_node(right.children[0], conn, locale)}}}{{{_latex_node(right.children[1], conn, locale)}}}"
        if right.kind in ("constant", "quantity") and right_latex.startswith("\\"):
            return f"{left_latex}\\,{right_latex}"
        return f"{left_latex}{right_latex}"
    if right.kind == "number":
        if left.kind in ("constant", "quantity"):
            return f"{left_latex}\\,{right_latex}"
        return f"{left_latex}{right_latex}"
    return f"{left_latex} {right_latex}"


def _latex_prefix(node, conn, locale):
    if node.operator_id == "abs":
        child_latex = _render_child(node, conn, locale)
        return f"\\left|{child_latex}\\right|"
    child_latex = _render_child(node, conn, locale)
    sym = node.symbol or ""
    if sym == "-":
        return f"-{child_latex}"
    return f"{sym} {{{child_latex}}}"


def _latex_postfix(node, conn, locale):
    child_latex = _render_child(node, conn, locale)
    return f"{child_latex}{node.symbol or ''}"


def _latex_relational(node, conn, locale):
    sym = node.symbol or "="
    if len(node.children) > 2:
        parts = []
        for i, child in enumerate(node.children):
            child_str = _latex_node(child, conn, locale)
            child_str = _wrap_in_parens(child_str, child, node, "left" if i == 0 else "right")
            parts.append(child_str)
            if i < len(node.children) - 1:
                parts.append(f" {sym} ")
        return "".join(parts)
    left_latex, right_latex = _render_binary(node, conn, locale)
    return f"{left_latex} {node.symbol} {right_latex}"


def _latex_node(node, conn, locale="en-us"):
    if node.kind == "quantity":
        return _latex_quantity(node, conn, locale)
    if node.kind == "constant":
        return _latex_constant(node, conn)
    if node.kind == "number":
        return _latex_number(node)
    if node.kind == "operator":
        return {
            "infix": _latex_infix,
            "prefix": _latex_prefix,
            "postfix": _latex_postfix,
            "relational": _latex_relational,
        }[node.operator_type](node, conn, locale)
    raise ValueError(f"cannot render node: {node!r}")


def render_formula_latex(conn, formula_id, locale="en-us"):
    """Render a formula (by id) as a LaTeX string."""
    tokens = conn.execute(
        "SELECT * FROM formula_token WHERE formula_id = ? ORDER BY position",
        (formula_id,),
    ).fetchall()
    if not tokens:
        return ""
    tree = reduce_rpn_to_tree(conn, [dict(t) for t in tokens])
    if tree is None:
        return ""
    return _latex_node(tree, conn, locale)


def parse_and_preview_equation(conn, equation, locale="en-us", dim_caches=None, overrides=None, dim_mode="dim"):
    """Parse an equation and return a preview dict (no DB writes).

    Returns {tokens, latex, dim_latex, variables, error}.
    """
    if not equation or not equation.strip():
        return {"tokens": [], "latex": "", "dim_latex": "",
                "variables": [], "error": ""}
    try:
        tokens = parse_equation(conn, equation)
    except ValueError as e:
        return {"tokens": [], "latex": "", "dim_latex": "",
                "variables": [], "error": str(e)}
    if not tokens:
        return {"tokens": [], "latex": "", "dim_latex": "",
                "variables": [], "error": ""}

    for pos, tok in enumerate(tokens, start=1):
        if tok["token_kind"] != "quantity":
            continue
        tok["pos"] = pos
        key = tok["quantity_id"] + "|" + (tok.get("label") or "") + "|" + str(pos)
        if overrides:
            ov = overrides.get(key) or {}
            if ov.get("symbol"):
                tok["symbol_overwrite"] = ov["symbol"]
            if ov.get("label"):
                tok["label"] = ov["label"]

    try:
        tree = reduce_rpn_to_tree(conn, tokens)
    except ValueError as e:
        return {"tokens": tokens, "latex": "", "dim_latex": "",
                "variables": [], "error": str(e)}

    latex = _latex_node(tree, conn, locale)

    dims = compute_rpn_dimensions(conn, tokens)
    if dim_caches is None:
        var_map, unit_map, dim_map = build_dimension_symbol_triplet(conn)
    else:
        var_map = dim_caches.get("var", {})
        unit_map = dim_caches.get("unit", {})
        dim_map = dim_caches.get("dim", {})
    dim_latex = format_dimensions_latex(
        *dims,
        variable_symbols=var_map,
        unit_symbols=unit_map,
        dim_symbols=dim_map,
        mode=dim_mode,
    )

    variables = []
    for tok in tokens:
        if tok["token_kind"] != "quantity":
            continue
        qid = tok["quantity_id"]
        if qid == "drop":
            continue
        pos = tok["pos"]
        qrow = _load_quantity(conn, qid)
        key = qid + "|" + (tok.get("label") or "") + "|" + str(pos)
        ov = (overrides or {}).get(key) or {}
        variables.append({
            "id": qid,
            "alias": tok.get("label") or "",
            "pos": pos,
            "key": key,
            "symbol": qrow["symbol"],
            "name": qrow["name"],
            "symbol_overwrite": ov.get("symbol", ""),
            "name_overwrite": ov.get("name", ""),
        })

    return {
        "tokens": tokens,
        "latex": latex,
        "dim_latex": dim_latex,
        "variables": variables,
        "error": "",
    }