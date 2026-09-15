"""Formula dimensions + LaTeX rendering (both data-driven from operator specs)."""

import logging
from fractions import Fraction

from scifind_lib.constants import FILTER_OPS
from scifind_lib.db import in_clause
from scifind_lib.i18n import localise, with_subscript, wrap_symbol_in_latex
from scifind_lib.operators import (
    apply_dim_spec,
    load_operators,
    operand_info,
    render_template,
    template_arity,
    template_bare_slots,
)
from scifind_lib.parser import (
    bulk_entity_rows,
    parse_equation,
    quantity_token_key,
    reduce_rpn_to_tree,
    reduce_rpn_to_tree_preloaded,
)
from scifind_lib.units import (
    format_compound_unit_symbol,
    parse_compound_unit,
    select_base_unit,
)
from scifind_lib.util import as_int

logger = logging.getLogger("scifind.dimensions")
DimensionMismatchError = ValueError
_FILTER_COMPARISONS = {
    "eq": lambda a, v: a == v,
    "geq": lambda a, v: a >= v,
    "leq": lambda a, v: a <= v,
}


def _dim_id_rows(conn):
    return [dict(r) for r in conn.execute(
        "SELECT dim_symbol, id FROM quantity "
        "WHERE dim_symbol IS NOT NULL ORDER BY dim_position").fetchall()]


def dimension_symbols(conn):
    """Base-dimension symbols from quantity.dim_symbol ordered by dim_position."""
    return [r["dim_symbol"] for r in _dim_id_rows(conn)]


def dimension_columns(conn):
    return [f"dim_{r['dim_symbol']}" for r in _dim_id_rows(conn)]


def dimension_column_for(symbol):
    return f"dim_{symbol}"


def dimension_quantity_ids(conn):
    """{dim_symbol: quantity_id} from quantity rows with dim_symbol set."""
    return {r["dim_symbol"]: r["id"] for r in _dim_id_rows(conn)}


def filter_ops(conn=None):
    """Dimension filter operator ids (backend constant, position order)."""
    return tuple(FILTER_OPS)


def format_dimension_number(n):
    if (iv := as_int(n)) is not None:
        return str(iv)
    return f"{n:.10f}".rstrip("0").rstrip(".")


def _nonzero_dims(exponents, symbols):
    """Yield (symbol, exponent) pairs with a truthy exponent."""
    return ((s, e) for s, e in zip(symbols, exponents) if e)


def format_dimensions_plain(*exponents, symbols):
    """Render dimension exponents as a human-readable string like M·L·T⁻¹."""
    parts = [s if e == 1 else f"{s}^{format_dimension_number(e)}"
             for s, e in _nonzero_dims(exponents, symbols)]
    return " · ".join(parts) if parts else "\\varnothing"


def format_dimensions_latex(
    *exponents, symbols, variable_symbols=None, unit_symbols=None,
    dim_symbols=None, mode="var",
):
    """Render dimension exponents as LaTeX (mode: dim | var | unit)."""
    lookup = {"dim": dim_symbols, "var": variable_symbols, "unit": unit_symbols}.get(mode) or {}
    parts = [(lookup.get(s, s) if e == 1 else f"{lookup.get(s, s)}^{{{format_dimension_number(e)}}}")
             for s, e in _nonzero_dims(exponents, symbols)]
    return " \\cdot ".join(parts) if parts else "\\varnothing"


def dimensions_from_row(row, conn):
    cols = dimension_columns(conn)
    return list(row) if isinstance(row, (list, tuple)) else [row[c] for c in cols]


def dimension_matches(row_dimensions, dimension_filter, dim_mode, conn):
    active = [(s, df) for s, df in dimension_filter.items() if df["val"] is not None]
    if not active:
        return True
    cols = dimension_columns(conn)

    def _val(symbol):
        col = f"dim_{symbol}"
        if isinstance(row_dimensions, (list, tuple)):
            idx = cols.index(col)
            v = row_dimensions[idx] if idx < len(row_dimensions) else None
            return v if v is not None else 0
        v = row_dimensions[col]
        return v if v is not None else 0

    checks = [_FILTER_COMPARISONS[df["op"]](_val(s), df["val"]) for s, df in active]
    return any(checks) if dim_mode == "or" else all(checks)


def _collect_qid_dimensions(conn):
    cols = dimension_columns(conn)
    dims_by_qid = {r["id"]: [r[c] for c in cols] for r in conn.execute(f"SELECT id, {', '.join(cols)} FROM quantity")}
    for r in conn.execute("SELECT id, quantity_id FROM constant WHERE quantity_id IS NOT NULL"):
        if r["quantity_id"] in dims_by_qid:
            dims_by_qid[r["id"]] = list(dims_by_qid[r["quantity_id"]])
    return dims_by_qid


def _formula_tokens(conn, formula_id):
    return [dict(t) for t in conn.execute(
        "SELECT * FROM formula_token WHERE formula_id = ? ORDER BY position", (formula_id,)).fetchall()]


def _rounded(dims):
    return [int(round(v)) for v in dims]


def _operand_info(node):
    """Operand descriptor for template matchers and dimension specs."""
    if node.kind == "quantity":
        return operand_info("quantity", ref=node.quantity_id, placeholder=node.placeholder)
    if node.kind == "constant":
        return operand_info("constant", ref=node.constant_id)
    if node.kind == "number":
        return operand_info("number", value=node.value)
    return operand_info(node.kind)


def _node_dimensions(node, qid_to_dims, width=None):
    if width is None:
        width = len(next(iter(qid_to_dims.values()), []))
    if node.kind == "quantity":
        if node.quantity_id not in qid_to_dims:
            raise DimensionMismatchError(f"quantity {node.quantity_id!r} has no registered dimensions")
        return list(qid_to_dims[node.quantity_id])
    if node.kind == "constant":
        return list(qid_to_dims.get(node.constant_id, [0] * width))
    if node.kind == "number":
        return [0] * width
    if node.kind != "operator":
        raise DimensionMismatchError(f"cannot analyse node: {node!r}")
    children = node.children
    return apply_dim_spec(node.dim_spec or {}, [_node_dimensions(c, qid_to_dims, width) for c in children],
                          [_operand_info(c) for c in children], node.operator_id)


def _dims_for_tokens(conn, tokens, label=None, qid_dims=None, cols=None):
    cols = cols if cols is not None else dimension_columns(conn)
    try:
        tree = reduce_rpn_to_tree(conn, tokens)
        while tree.kind == "operator" and tree.fixity == "relational":
            tree = tree.children[0]
        return _rounded(_node_dimensions(tree, qid_dims or _collect_qid_dimensions(conn), len(cols)))
    except Exception as exc:
        logger.warning("formula %s: %s", label, exc)
        return [0] * len(cols)


def compute_formula_dimensions(conn, formula_id):
    return _dims_for_tokens(conn, _formula_tokens(conn, formula_id), label=formula_id)


def compute_rpn_dimensions(conn, tokens):
    return _dims_for_tokens(conn, tokens)


def compute_compound_unit_dimensions(conn, compound_unit_json):
    cols = dimension_columns(conn)
    total = [0.0] * len(cols)
    unit_qty = {r["id"]: r["quantity_id"] for r in conn.execute("SELECT id, quantity_id FROM unit")}
    qid_dims = _collect_qid_dimensions(conn)
    for unit_id, exponent in parse_compound_unit(compound_unit_json):
        dims = qid_dims.get(unit_qty.get(unit_id))
        if dims:
            total = [t + v * exponent for t, v in zip(total, dims)]
    return _rounded(total)


def compute_all_formula_dimensions(conn, formula_ids=None):
    formula_ids = ([r["id"] for r in conn.execute("SELECT id FROM formula")]
                   if formula_ids is None else list(formula_ids))
    cols = dimension_columns(conn)
    qid_dims = _collect_qid_dimensions(conn)
    marks, params = in_clause(formula_ids)
    grouped = {fid: [] for fid in formula_ids}
    rows = conn.execute(f"SELECT * FROM formula_token WHERE formula_id IN ({marks}) ORDER BY formula_id, position", params).fetchall() if formula_ids else []
    for r in rows:
        grouped.setdefault(r["formula_id"], []).append(dict(r))
    return {fid: dict(zip(cols, _dims_for_tokens(conn, grouped.get(fid, []), label=fid, qid_dims=qid_dims, cols=cols)))
            for fid in formula_ids}


def build_dimension_symbol_triplet(conn):
    """(variable_map, unit_map, dim_map) for the dimension display."""
    qty_map = dimension_quantity_ids(conn)
    by_id = {}
    if qty_map:
        marks, params = in_clause(list(qty_map.values()))
        by_id = {r["id"]: r for r in conn.execute(
            f"SELECT id, symbol FROM quantity WHERE id IN ({marks})", params).fetchall()}
    unit_syms = {r["id"]: r["symbol"] for r in conn.execute("SELECT id, symbol FROM unit")}
    variable_map, unit_map, dim_map = {}, {}, {}
    for symbol, qid in qty_map.items():
        row = by_id.get(qid)
        variable_map[symbol] = row["symbol"] if row and row["symbol"] else symbol
        unit_map[symbol] = variable_map[symbol]
        dim_map[symbol] = symbol
        base = select_base_unit(conn, qid, "SI")
        if base is None:
            continue
        if base["kind"] == "compound_unit":
            base_sym = base.get("symbol_overwrite") or format_compound_unit_symbol(
                base["unit"], unit_symbol=lambda uid: wrap_symbol_in_latex(unit_syms.get(uid, uid)))
        else:
            base_sym = wrap_symbol_in_latex(base.get("symbol") or symbol)
        if base_sym:
            unit_map[symbol] = base_sym
    return variable_map, unit_map, dim_map


def _latex_quantity(node, locale):
    if not node.quantity_id:
        return "?"
    # Empty symbols (placeholder operands) render "?" like display tables.
    sym = localise(node.symbol_overwrite or "", locale) or node.symbol
    return with_subscript(sym, localise(node.label or "", locale)) if sym else "?"


def _latex_number(node):
    if node.value is None:
        return "?"
    v = node.value
    v = -v if v < 0 else v
    neg = "-" if node.value < 0 else ""
    if (iv := as_int(v)) is not None:
        return neg + str(iv)
    try:
        frac = Fraction(v).limit_denominator(100)
    except (ValueError, ZeroDivisionError, OverflowError):
        return neg + format_dimension_number(v)
    if frac.denominator != 1 and frac.numerator == 1 and frac.denominator < 20:
        return neg + "\\frac{1}{" + str(frac.denominator) + "}"
    return neg + format_dimension_number(v)


def _needs_parens(child, parent, index):
    """Whether a child operand needs ``\\left(...\\right)`` wrapping."""
    if child.kind != "operator" or child.precedence != parent.precedence:
        return child.kind == "operator" and child.precedence < parent.precedence
    if parent.associativity == "none":
        return True
    if parent.fixity == "infix" and len(parent.children) == 2:
        return (index == 1) if parent.associativity == "left" else (index == 0)
    return False


def _join_juxtaposition(left, right, left_latex, right_latex):
    """Spacing for a juxtaposition operator (NULL symbol in the operator table)."""
    if not left_latex:
        return right_latex
    if not right_latex:
        return left_latex
    if left.kind == "number" and right.kind == "number":
        return f"{left_latex} \\times {right_latex}"
    if left.kind == "number":
        sep = "\\," if right_latex.startswith("\\") else ""
        return f"{left_latex}{sep}{right_latex}"
    if right.kind == "number":
        sep = "\\," if left.kind in ("constant", "quantity") else ""
        return f"{left_latex}{sep}{right_latex}"
    return f"{left_latex} {right_latex}"


def _wrap_child(child_str, child, parent, index, bare):
    """Wrap a rendered child in ``\\left(...\\right)`` when needed."""
    if child.kind == "operator" and (
            (child._paren_wrap and not child_str.startswith("\\left("))
            or (index not in bare and _needs_parens(child, parent, index))):
        return "\\left(" + child_str + "\\right)"
    return child_str


def _latex_operator(node, locale):
    template = node.latex_template or ""
    if not template:
        raise ValueError(f"operator {node.operator_id!r} has no latex_template")
    op_id = node.operator_id or "<template>"
    bare = template_bare_slots(template, op_id)
    # Juxtaposition is schema-defined as NULL symbol, not a template comparison.
    if len(node.children) == 2 and node.arity == 2 and node.symbol is None:
        left, right = node.children
        left_latex, right_latex = _latex_node(left, locale), _latex_node(right, locale)
        # A placeholder operand (empty rendering) vanishes with its grouping.
        if not left_latex:
            return right_latex
        if not right_latex:
            return left_latex
        return _join_juxtaposition(left, right,
                                   _wrap_child(left_latex, left, node, 0, bare),
                                   _wrap_child(right_latex, right, node, 1, bare))
    operands = [_wrap_child(_latex_node(c, locale), c, node, i, bare) for i, c in enumerate(node.children)]
    infos = [_operand_info(c) for c in node.children]
    slots = template_arity(template, op_id)
    if len(operands) <= slots:
        return render_template(template, operands, infos, op_id)
    # N-ary chain (relational fold): extra operands rejoin with empty lead slots.
    latex = render_template(template, operands[:slots], infos[:slots], op_id)
    for extra, info in zip(operands[slots:], infos[slots:]):
        latex += render_template(template, [""] * (slots - 1) + [extra],
                               [operand_info("operator")] * (slots - 1) + [info], op_id)
    return latex


def _latex_node(node, locale="en-us"):
    if node.kind == "quantity":
        return _latex_quantity(node, locale)
    if node.kind == "constant":
        return node.symbol or node.constant_id
    if node.kind == "number":
        return _latex_number(node)
    if node.kind == "operator":
        return _latex_operator(node, locale)
    raise ValueError(f"cannot render node: {node!r}")


def render_formula_latex(conn, formula_id, locale="en-us"):
    """Render a formula (by id) as a LaTeX string."""
    return render_formulas_latex_batched(conn, [formula_id], locale).get(formula_id, "")


def render_formulas_latex_batched(conn, formula_ids, locale="en-us"):
    """{formula_id: latex} for many formulas with 3 queries total (no N+1)."""
    fids = list(dict.fromkeys(formula_ids))
    if not fids:
        return {}
    marks, params = in_clause(fids)
    tokens_by_formula: dict = {fid: [] for fid in fids}
    for r in conn.execute(
            f"SELECT * FROM formula_token WHERE formula_id IN ({marks})"
            " ORDER BY formula_id, position", params).fetchall():
        tokens_by_formula.setdefault(r["formula_id"], []).append(dict(r))
    operators = load_operators(conn)
    all_tokens = [t for toks in tokens_by_formula.values() for t in toks]
    qty_map = bulk_entity_rows(conn, "quantity", "id, name, symbol",
        {t["quantity_id"] for t in all_tokens if t.get("token_kind") == "quantity" and t.get("quantity_id")})
    const_map = bulk_entity_rows(conn, "constant", "id, symbol",
        {t["constant_id"] for t in all_tokens if t.get("token_kind") == "constant" and t.get("constant_id")})
    latex_by_id = {}
    for fid in fids:
        try:
            tree = reduce_rpn_to_tree_preloaded(tokens_by_formula.get(fid, []), operators, qty_map, const_map)
            latex_by_id[fid] = _latex_node(tree, locale) if tree is not None else ""
        except Exception as exc:
            logger.warning("formula %s: %s", fid, exc)
            latex_by_id[fid] = ""
    return latex_by_id


def _empty_preview(error=""):
    return {"tokens": [], "latex": "", "dim_latex": "", "variables": [], "error": error}


def _apply_quantity_overrides(tokens, overrides):
    """Stamp 1-based positions and apply per-occurrence symbol/label overrides."""
    for pos, tok in enumerate(tokens, start=1):
        if tok["token_kind"] != "quantity":
            continue
        tok["pos"] = pos
        ov = (overrides or {}).get(quantity_token_key(tok["quantity_id"], tok.get("label"), pos)) or {}
        if ov.get("symbol"):
            tok["symbol_overwrite"] = ov["symbol"]
        if ov.get("label"):
            tok["label"] = ov["label"]


def _preview_variables(conn, tokens, overrides):
    """Per-occurrence variable list for the /create form (hidden rows skipped)."""
    qty_rows = bulk_entity_rows(conn, "quantity", "id, name, symbol, hidden",
                                (t["quantity_id"] for t in tokens if t["token_kind"] == "quantity"))
    variables = []
    for tok in tokens:
        if tok["token_kind"] != "quantity":
            continue
        qrow = qty_rows.get(tok["quantity_id"])
        if qrow is None:
            raise ValueError(f"unknown quantity: {tok['quantity_id']!r}")
        if qrow.get("hidden"):
            continue
        key = quantity_token_key(tok["quantity_id"], tok.get("label"), tok["pos"])
        ov = (overrides or {}).get(key) or {}
        variables.append({"id": tok["quantity_id"], "alias": tok.get("label") or "", "pos": tok["pos"],
                          "key": key, "symbol": qrow["symbol"], "name": qrow["name"],
                          "symbol_overwrite": ov.get("symbol", ""), "name_overwrite": ov.get("name", "")})
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
        return {"tokens": tokens, "latex": "", "dim_latex": "", "variables": [], "error": str(e)}
    if dim_caches is None:
        dim_caches = dict(zip(("var", "unit", "dim"), build_dimension_symbol_triplet(conn)))
    dims = compute_rpn_dimensions(conn, tokens)
    return {"tokens": tokens, "latex": _latex_node(tree, locale),
            "dim_latex": format_dimensions_latex(
                *dims, symbols=dimension_symbols(conn),
                variable_symbols=dim_caches.get("var", {}),
                unit_symbols=dim_caches.get("unit", {}),
                dim_symbols=dim_caches.get("dim", {}), mode=dim_mode),
            "variables": _preview_variables(conn, tokens, overrides), "error": ""}
