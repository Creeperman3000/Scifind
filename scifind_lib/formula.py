"""Formula dimensions + LaTeX rendering."""

import logging
from fractions import Fraction

from scifind_lib.constants import (
    _BASE_DIMENSION_ORDER,
    _BASE_DIMENSION_QTY_IDS,
)
from scifind_lib.i18n import localise, with_subscript, wrap_symbol_in_latex
from scifind_lib.parser import (
    bulk_entity_rows,
    parse_equation,
    quantity_token_key,
    reduce_rpn_to_tree,
)
from scifind_lib.units import (
    format_compound_unit_symbol,
    parse_compound_unit,
    select_base_unit,
)

logger = logging.getLogger("scifind.dimensions")

_SYMS = list(_BASE_DIMENSION_ORDER)
_COLS = [f"dim_{s}" for s in _SYMS]
_SYM_TO_COL = dict(zip(_SYMS, _COLS))


def dimension_symbols():
    return list(_SYMS)


def dimension_columns():
    return list(_COLS)


def dimension_quantity_ids():
    return dict(_BASE_DIMENSION_QTY_IDS)


DIMENSION_OPS = ("eq", "geq", "leq")
_DIMENSION_OP_FNS = {
    "eq":  lambda a, v: a == v,
    "geq": lambda a, v: a >= v,
    "leq": lambda a, v: a <= v,
}


def format_dimension_number(n):
    if n == int(n):
        return str(int(n))
    return f"{n:.10f}".rstrip("0").rstrip(".")


def _nonzero_dims(values):
    """Yield (symbol, exponent) pairs with a truthy exponent."""
    for symbol, exponent in zip(_SYMS, values):
        if exponent:
            yield symbol, exponent


def format_dimensions_plain(*values):
    """Render dimension exponents as a human-readable string like M·L·T⁻¹."""
    parts = [
        symbol if exponent == 1 else f"{symbol}^{format_dimension_number(exponent)}"
        for symbol, exponent in _nonzero_dims(values)
    ]
    return " · ".join(parts) if parts else "\\varnothing"


def format_dimensions_latex(
    *values, variable_symbols=None, unit_symbols=None,
    dim_symbols=None, mode="var",
):
    """Render dimension exponents as LaTeX (mode: dim | var | unit)."""
    lookup = {
        "dim": dim_symbols,
        "var": variable_symbols,
        "unit": unit_symbols,
    }.get(mode) or {}
    parts = []
    for symbol, exponent in _nonzero_dims(values):
        sym = lookup.get(symbol, symbol)
        if exponent == 1:
            parts.append(sym)
        else:
            exp_text = str(int(exponent)) if exponent == int(exponent) else str(exponent)
            parts.append(f"{sym}^{{{exp_text}}}")
    return " \\cdot ".join(parts) if parts else "\\varnothing"


def dimensions_from_row(row):
    return [row[c] for c in _COLS]


def dimension_matches(row_dimensions, dimension_filter, dim_mode="and"):
    """Apply a {symbol: {op, val}} filter to a dimension row."""
    active = [(s, df) for s, df in dimension_filter.items() if df["val"] is not None]
    if not active:
        return True

    def _get(key):
        v = row_dimensions.get(key)
        return v if v is not None else 0

    results = (
        _DIMENSION_OP_FNS[df["op"]](_get(_SYM_TO_COL[s]), df["val"])
        for s, df in active
    )
    return any(results) if dim_mode == "or" else all(results)


def _collect_qid_dimensions(conn):
    qid_dims = {
        r["id"]: [r[c] for c in _COLS]
        for r in conn.execute(f"SELECT id, {', '.join(_COLS)} FROM quantity")
    }
    # Constants whose quantity_id resolves a known quantity inherit its
    # dimensions (standard_gravity -> acceleration) instead of contributing zero.
    for r in conn.execute(
        "SELECT id, quantity_id FROM constant WHERE quantity_id IS NOT NULL"
    ):
        if r["quantity_id"] in qid_dims:
            qid_dims[r["id"]] = list(qid_dims[r["quantity_id"]])
    return qid_dims


class DimensionMismatchError(ValueError):
    """Raised when a formula's dimensional structure cannot be analysed."""


def _add_dims(dst, src, scale=1.0):
    for i, v in enumerate(src):
        dst[i] += v * scale


def _walk_dimensions(node, qid_to_dims, dims):
    """Add the dimensional exponents of every quantity under `node` to `dims`; raises on invalid structure."""
    if node.kind == "quantity":
        if node.quantity_id not in qid_to_dims:
            raise DimensionMismatchError(
                f"quantity {node.quantity_id!r} has no registered dimensions"
            )
        _add_dims(dims, qid_to_dims[node.quantity_id])
        return
    if node.kind == "constant":
        if node.constant_id in qid_to_dims:
            _add_dims(dims, qid_to_dims[node.constant_id])
        return
    if node.kind != "operator":
        return
    op = node.operator_id
    children = node.children
    if op in ("div", "frac"):
        lhs, rhs = [0.0] * len(dims), [0.0] * len(dims)
        _walk_dimensions(children[0], qid_to_dims, lhs)
        _walk_dimensions(children[1], qid_to_dims, rhs)
        _add_dims(dims, lhs)
        _add_dims(dims, rhs, scale=-1.0)
        return
    if op == "pow":
        base, exp = children
        if exp.kind == "number" and exp.value is not None:
            sub_dims = [0.0] * len(dims)
            _walk_dimensions(base, qid_to_dims, sub_dims)
            _add_dims(dims, sub_dims, scale=exp.value)
            return
        exp_dims = [0.0] * len(dims)
        _walk_dimensions(exp, qid_to_dims, exp_dims)
        if any(abs(v) > 1e-9 for v in exp_dims):
            raise DimensionMismatchError(
                f"exponent must be dimensionless; got {exp_dims}"
            )
        if exp.kind in ("quantity", "operator"):
            sub_dims = [0.0] * len(dims)
            _walk_dimensions(base, qid_to_dims, sub_dims)
            _add_dims(dims, sub_dims)
            return
        raise DimensionMismatchError(
            f"exponent must be a number, quantity, or operator expression; "
            f"got kind={exp.kind!r}"
        )
    if op in ("add", "sub"):
        lhs, rhs = [0.0] * len(dims), [0.0] * len(dims)
        _walk_dimensions(children[0], qid_to_dims, lhs)
        _walk_dimensions(children[1], qid_to_dims, rhs)
        if any(abs(a - b) > 1e-9 for a, b in zip(lhs, rhs)):
            raise DimensionMismatchError(
                f"operands of {op} have mismatched dimensions: "
                f"{lhs} vs {rhs}"
            )
        _add_dims(dims, lhs)
        return
    if op in ("sin", "cos", "tan"):
        arg = [0.0] * len(dims)
        _walk_dimensions(children[0], qid_to_dims, arg)
        if any(abs(v) > 1e-9 for v in arg):
            raise DimensionMismatchError(
                f"argument of {op} must be dimensionless; got {arg}"
            )
        return
    if op == "sqrt":
        sub_dims = [0.0] * len(dims)
        _walk_dimensions(children[0], qid_to_dims, sub_dims)
        _add_dims(dims, sub_dims, scale=0.5)
        return
    for c in children:
        _walk_dimensions(c, qid_to_dims, dims)


def _compute_dimensions(conn, tree, empty_default, qid_dims=None):
    if tree is None:
        return empty_default
    node = tree
    while node.kind == "operator" and node.operator_type == "relational":
        node = node.children[0]
    dims = [0.0] * len(_COLS)
    _walk_dimensions(node, qid_dims or _collect_qid_dimensions(conn), dims)
    return [int(round(d)) for d in dims]


def _dims_for_tokens(conn, tokens, empty_default, label=None, qid_dims=None):
    """Reduce RPN tokens to dimension exponents, logging failures as `label`."""
    if not tokens:
        return empty_default
    try:
        tree = reduce_rpn_to_tree(conn, tokens)
    except Exception as exc:
        if label:
            logger.warning("formula %s: RPN evaluation failed: %s", label, exc)
        else:
            logger.warning("RPN evaluation failed: %s", exc)
        return empty_default
    try:
        return _compute_dimensions(conn, tree, empty_default, qid_dims)
    except DimensionMismatchError as exc:
        if label:
            logger.warning("formula %s: %s", label, exc)
        else:
            logger.warning("%s", exc)
        return empty_default


def compute_formula_dimensions(conn, formula_id):
    """Compute dimensions from the LHS of a stored formula."""
    tokens = conn.execute(
        "SELECT * FROM formula_token WHERE formula_id = ? ORDER BY position",
        (formula_id,),
    ).fetchall()
    return _dims_for_tokens(conn, [dict(t) for t in tokens], [], label=formula_id)


def compute_rpn_dimensions(conn, tokens):
    """Like compute_formula_dimensions, but on an in-memory RPN token list."""
    return _dims_for_tokens(conn, tokens, [0.0] * len(_COLS))


def compute_compound_unit_dimensions(conn, compound_unit_json):
    """Base-dimension exponents for a `compound_unit.unit` JSON string (zeros unparseable)."""
    total = [0] * len(_COLS)
    unit_qty = {r["id"]: r["quantity_id"]
                for r in conn.execute("SELECT id, quantity_id FROM unit")}
    qid_dims = _collect_qid_dimensions(conn)
    for unit_id, exponent in parse_compound_unit(compound_unit_json):
        for i, v in enumerate(qid_dims.get(unit_qty.get(unit_id), [])):
            total[i] += v * exponent
    return [int(round(v)) for v in total]


def compute_all_formula_dimensions(conn, formula_ids=None):
    """{formula_id: {dim_M, dim_L, ...}} for all or given formulas."""
    ids = formula_ids if formula_ids is not None else {
        r["id"] for r in conn.execute("SELECT id FROM formula")}
    qid_dims = _collect_qid_dimensions(conn)
    result = {}
    for fid in ids:
        tokens = conn.execute(
            "SELECT * FROM formula_token WHERE formula_id = ? ORDER BY position",
            (fid,),
        ).fetchall()
        dims = _dims_for_tokens(
            conn, [dict(t) for t in tokens], [], label=fid, qid_dims=qid_dims)
        result[fid] = dict(zip(_COLS, dims)) if dims else dict.fromkeys(_COLS, 0)
    return result


def build_dimension_symbol_triplet(conn):
    """(variable_map, unit_map, dim_map) for the dimension display."""
    qty_rows = conn.execute(
        f"SELECT id, symbol FROM quantity "
        f"WHERE id IN ({','.join('?' * len(_BASE_DIMENSION_QTY_IDS))})",
        tuple(_BASE_DIMENSION_QTY_IDS.values()),
    ).fetchall()
    by_id = {r["id"]: r for r in qty_rows}
    syms = {
        r["id"]: r["symbol"]
        for r in conn.execute("SELECT id, symbol FROM unit")
    }
    variable_map, unit_map, dim_map = {}, {}, {}
    for symbol, qid in _BASE_DIMENSION_QTY_IDS.items():
        row = by_id.get(qid)
        variable_map[symbol] = (row["symbol"] if row and row["symbol"] else symbol)
        unit_map[symbol] = variable_map[symbol]
        base = select_base_unit(conn, qid, "SI")
        if base is None:
            continue
        if base["kind"] == "compound_unit":
            sym = base.get("symbol_overwrite") or format_compound_unit_symbol(
                base["unit"],
                unit_symbol=lambda uid: wrap_symbol_in_latex(syms.get(uid, uid)),
            )
        else:
            sym = wrap_symbol_in_latex(base.get("symbol") or symbol)
        if sym:
            unit_map[symbol] = sym
        dim_map[symbol] = symbol
    return variable_map, unit_map, dim_map


_RANGED_OPS = ("sum", "int", "prod", "oint")


def _latex_quantity(node, locale):
    if not node.quantity_id:
        return "?"
    if node.quantity_id == "drop":
        return ""
    sym = localise(node.symbol_overwrite or "", locale) or node.symbol
    if not sym:
        return ""
    return with_subscript(sym, localise(node.label or "", locale))


def _latex_number(node):
    if node.value is None:
        return "?"
    v = node.value
    return "-" + _format_positive_number(-v) if v < 0 else _format_positive_number(v)


def _format_positive_number(v):
    if v == int(v):
        return str(int(v))
    try:
        frac = Fraction(v).limit_denominator(100)
    except (ValueError, ZeroDivisionError, OverflowError):
        return format_dimension_number(v)
    if frac.denominator != 1 and frac.numerator == 1 and frac.denominator < 20:
        return "\\frac{1}{" + str(frac.denominator) + "}"
    return format_dimension_number(v)


def _latex_ranged_op(node, locale):
    """Render `\\op_{from}^{to}{body}` for sum/int/prod/oint."""
    lo = _latex_node(node.children[0], locale)
    hi = _latex_node(node.children[1], locale)
    body = _latex_node(node.children[2], locale)
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
    if child.operator_type == "relational" or child.precedence < parent.precedence:
        return True
    if child.precedence != parent.precedence:
        return False
    if parent.associativity == "none":
        return True
    if side == "child":
        return False
    return (parent.associativity == "left") == (side == "right")


def _wrap_in_parens(child_str, child, parent, side):
    """Wrap child in `\\left(...\\right)` per paren_arg / precedence / source parens."""
    side_idx = 1 if side == "right" else 0
    paren_arg = parent.paren_arg or [True] * parent.arity
    if side_idx >= len(paren_arg) or not paren_arg[side_idx]:
        return child_str
    if _needs_paren(child, parent, side):
        return "\\left(" + child_str + "\\right)"
    if child._paren_wrap and child.kind == "operator" \
            and not child_str.startswith("\\left("):
        return "\\left(" + child_str + "\\right)"
    return child_str


def _render_binary(node, locale):
    if node.arity != 2:
        raise ValueError(f"{node.operator_type} op {node.operator_id} arity {node.arity}")
    left, right = node.children
    left_latex = _latex_node(left, locale)
    right_latex = _latex_node(right, locale)
    left_latex = _wrap_in_parens(left_latex, left, node, "left")
    right_latex = _wrap_in_parens(right_latex, right, node, "right")
    return left_latex, right_latex


def _render_child(node, locale):
    child_latex = _latex_node(node.children[0], locale)
    return _wrap_in_parens(child_latex, node.children[0], node, "child")


def _latex_sqrt(node, locale):
    radicand = _latex_node(node.children[0], locale)
    if not radicand:
        return ""
    index = node.children[1]
    if index.kind == "number" and index.value == 2:
        return f"\\sqrt{{{radicand}}}"
    idx = _latex_node(index, locale)
    if not idx:
        return f"\\sqrt{{{radicand}}}"
    return f"\\sqrt[{idx}]{{{radicand}}}"


def _latex_sub(node, locale):
    left, right = node.children
    right_latex = _wrap_in_parens(_latex_node(right, locale), right, node, "right")
    if left.kind == "quantity" and left.quantity_id == "drop":
        return f"-{right_latex}"
    left_latex = _wrap_in_parens(_latex_node(left, locale), left, node, "left")
    return f"{left_latex} - {right_latex}"


def _latex_log(node, locale):
    base_node = node.children[0]
    arg = _latex_node(node.children[1], locale)
    if not arg:
        return ""
    if base_node.kind == "constant" and base_node.constant_id == "euler_e":
        return f"\\ln{{{arg}}}"
    base = _latex_node(base_node, locale)
    if not base:
        return f"\\log{{{arg}}}"
    return f"\\log_{{{base}}}{{{arg}}}"


def _latex_lim(node, locale):
    var = _latex_node(node.children[0], locale)
    val = _latex_node(node.children[1], locale)
    body = _latex_node(node.children[2], locale)
    if not body:
        return ""
    if not var or not val:
        return f"\\lim{{{body}}}"
    return f"\\lim_{{{var} \\to {val}}}{{{body}}}"


def _latex_implicit_mul(node, locale, left, right, left_latex, right_latex):
    """Juxtaposition rendering for a symbol-less binary operator."""
    if left.kind == "number" and right.kind == "number":
        return f"{left_latex} \\times {right_latex}"
    if left.kind == "number":
        if right.kind == "operator" and right.operator_id == "frac":
            num = _latex_node(right.children[0], locale)
            den = _latex_node(right.children[1], locale)
            return f"{left_latex}\\,\\frac{{{num}}}{{{den}}}"
        if right.kind in ("constant", "quantity") and right_latex.startswith("\\"):
            return f"{left_latex}\\,{right_latex}"
        return f"{left_latex}{right_latex}"
    if right.kind == "number":
        if left.kind in ("constant", "quantity"):
            return f"{left_latex}\\,{right_latex}"
        return f"{left_latex}{right_latex}"
    return f"{left_latex} {right_latex}"


def _latex_infix(node, locale):
    if node.operator_id == "sqrt":
        return _latex_sqrt(node, locale)
    if node.operator_id == "sub":
        return _latex_sub(node, locale)
    if node.operator_id == "log":
        return _latex_log(node, locale)
    if node.operator_id in _RANGED_OPS:
        return _latex_ranged_op(node, locale)
    if node.operator_id == "lim":
        return _latex_lim(node, locale)
    left, right = node.children
    if node.operator_id == "frac":
        left_latex = _latex_node(left, locale)
        right_latex = _latex_node(right, locale)
        return f"\\frac{{{left_latex}}}{{{right_latex}}}"
    left_latex, right_latex = _render_binary(node, locale)
    if node.operator_id == "pow":
        return f"{left_latex}^{{{right_latex}}}"
    if node.symbol:
        return f"{left_latex} {node.symbol} {right_latex}"
    return _latex_implicit_mul(node, locale, left, right, left_latex, right_latex)


def _latex_prefix(node, locale):
    if node.operator_id == "abs":
        child_latex = _render_child(node, locale)
        return f"\\left|{child_latex}\\right|"
    child_latex = _render_child(node, locale)
    sym = node.symbol or ""
    if sym == "-":
        return f"-{child_latex}"
    return f"{sym} {{{child_latex}}}"


def _latex_postfix(node, locale):
    child_latex = _render_child(node, locale)
    return f"{child_latex}{node.symbol or ''}"


def _latex_relational(node, locale):
    sym = node.symbol or "="
    parts = []
    for i, child in enumerate(node.children):
        child_str = _wrap_in_parens(
            _latex_node(child, locale), child, node, "left" if i == 0 else "right")
        parts.append(child_str)
        if i < len(node.children) - 1:
            parts.append(f" {sym} ")
    return "".join(parts)


def _latex_node(node, locale="en-us"):
    if node.kind == "quantity":
        return _latex_quantity(node, locale)
    if node.kind == "constant":
        return node.symbol or node.constant_id
    if node.kind == "number":
        return _latex_number(node)
    if node.kind == "operator":
        if node.operator_type == "infix":
            return _latex_infix(node, locale)
        if node.operator_type == "prefix":
            return _latex_prefix(node, locale)
        if node.operator_type == "postfix":
            return _latex_postfix(node, locale)
        if node.operator_type == "relational":
            return _latex_relational(node, locale)
        raise ValueError(f"unknown operator type: {node.operator_type!r}")
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
    return _latex_node(tree, locale)


def _empty_preview(error=""):
    return {"tokens": [], "latex": "", "dim_latex": "",
            "variables": [], "error": error}


def _apply_quantity_overrides(tokens, overrides):
    """Stamp 1-based positions and apply per-occurrence symbol/label overrides."""
    for pos, tok in enumerate(tokens, start=1):
        if tok["token_kind"] != "quantity":
            continue
        tok["pos"] = pos
        if not overrides:
            continue
        ov = overrides.get(quantity_token_key(tok["quantity_id"], tok.get("label"), pos)) or {}
        if ov.get("symbol"):
            tok["symbol_overwrite"] = ov["symbol"]
        if ov.get("label"):
            tok["label"] = ov["label"]


def _preview_variables(conn, tokens, overrides):
    """Build the per-occurrence variable list for the /create form."""
    qty_rows = bulk_entity_rows(
        conn, "quantity", "id, name, symbol",
        (tok["quantity_id"] for tok in tokens
         if tok["token_kind"] == "quantity" and tok["quantity_id"] != "drop"),
    )
    variables = []
    for tok in tokens:
        if tok["token_kind"] != "quantity":
            continue
        qid = tok["quantity_id"]
        if qid == "drop":
            continue
        pos = tok["pos"]
        qrow = qty_rows.get(qid)
        if qrow is None:
            raise ValueError(f"unknown quantity: {qid!r}")
        key = quantity_token_key(qid, tok.get("label"), pos)
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
    return variables


def parse_and_preview_equation(conn, equation, locale="en-us", dim_caches=None, overrides=None, dim_mode="dim"):
    """Parse an equation and return a preview dict (no DB writes)."""
    if not equation or not equation.strip():
        return _empty_preview()
    try:
        tokens = parse_equation(conn, equation)
    except ValueError as e:
        return _empty_preview(str(e))
    if not tokens:
        return _empty_preview()

    _apply_quantity_overrides(tokens, overrides)

    try:
        tree = reduce_rpn_to_tree(conn, tokens)
    except ValueError as e:
        return {"tokens": tokens, "latex": "", "dim_latex": "",
                "variables": [], "error": str(e)}

    latex = _latex_node(tree, locale)

    dims = compute_rpn_dimensions(conn, tokens)
    if dim_caches is None:
        dim_caches = dict(zip(
            ("var", "unit", "dim"), build_dimension_symbol_triplet(conn)))
    dim_latex = format_dimensions_latex(
        *dims,
        variable_symbols=dim_caches.get("var", {}),
        unit_symbols=dim_caches.get("unit", {}),
        dim_symbols=dim_caches.get("dim", {}),
        mode=dim_mode,
    )

    return {
        "tokens": tokens,
        "latex": latex,
        "dim_latex": dim_latex,
        "variables": _preview_variables(conn, tokens, overrides),
        "error": "",
    }
