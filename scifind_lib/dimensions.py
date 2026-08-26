"""Base dimensions: order, format helpers, and dimensional walker."""
# Licensed under the LICENSE file in the project root.

import json

from scifind_lib.constants import (
    _BASE_DIMENSION_ORDER,
    _BASE_DIMENSION_QTY_IDS,
)
from scifind_lib.units import parse_default_unit


def dimension_symbols():
    return list(_BASE_DIMENSION_ORDER)


def dimension_columns():
    return [f"dim_{s}" for s in _BASE_DIMENSION_ORDER]


def dimension_quantity_ids():
    return dict(_BASE_DIMENSION_QTY_IDS)


DIMENSION_OPS = ("eq", "geq", "leq")
_DIMENSION_OP_FNS = {
    "eq":  lambda a, v: a == v,
    "geq": lambda a, v: a >= v,
    "leq": lambda a, v: a <= v,
}


def format_dimensions_plain(*values):
    """Render dimension exponents as a human-readable string like M·L·T⁻¹."""
    parts = []
    for symbol, exponent in zip(dimension_symbols(), values):
        exponent = exponent or 0
        if exponent == 0:
            continue
        parts.append(symbol if exponent == 1
                     else f"{symbol}^{format_number(exponent)}")
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
    for symbol, exponent in zip(dimension_symbols(), values):
        if not exponent:
            continue
        sym = lookup.get(symbol, symbol)
        if exponent == 1:
            parts.append(sym)
        else:
            e = str(int(exponent)) if exponent == int(exponent) else str(exponent)
            parts.append(f"{sym}^{{{e}}}")
    return " \\cdot ".join(parts) if parts else "\\varnothing"


def extract_dimensions_from_row(row):
    return [row[c] for c in dimension_columns()]


def dimension_matches(row_dimensions, dimension_filter, dim_mode="and"):
    """Apply a {symbol: {op, val}} filter to a dimension row."""
    syms = dimension_symbols()
    cols = dimension_columns()
    sym_to_col = dict(zip(syms, cols))
    active = [(s, df) for s, df in dimension_filter.items() if df["val"] is not None]
    if not active:
        return True

    def _get(row, key):
        v = row.get(key)
        return v if v is not None else 0

    if dim_mode == "or":
        return any(_DIMENSION_OP_FNS[df["op"]](_get(row_dimensions, sym_to_col[s]), df["val"])
                   for s, df in active)
    return all(_DIMENSION_OP_FNS[df["op"]](_get(row_dimensions, sym_to_col[s]), df["val"])
               for s, df in active)


def _collect_qid_dimensions(conn):
    return {
        r["id"]: [r[c] for c in dimension_columns()]
        for r in conn.execute(f"SELECT id, {', '.join(dimension_columns())} FROM quantity")
    }


def _walk_dimensions(node, qid_to_dims, dims):
    """Sum the dimensional exponents of every quantity under `node` into `dims`."""
    if node.kind != "operator":
        if node.kind == "quantity":
            for i, v in enumerate(qid_to_dims.get(node.quantity_id, [])):
                dims[i] += v
        return
    op = node.operator_id
    if op in ("div", "frac"):
        lhs = [0.0] * len(dims)
        rhs = [0.0] * len(dims)
        _walk_dimensions(node.children[0], qid_to_dims, lhs)
        _walk_dimensions(node.children[1], qid_to_dims, rhs)
        for i in range(len(dims)):
            dims[i] += lhs[i] - rhs[i]
    elif op == "pow":
        base, exp = node.children
        scale = exp.value if exp.kind == "number" and exp.value is not None else 1
        sub_dims = [0.0] * len(dims)
        _walk_dimensions(base, qid_to_dims, sub_dims)
        for i, v in enumerate(sub_dims):
            dims[i] += v * scale
    elif op in ("add", "sub"):
        _walk_dimensions(node.children[0], qid_to_dims, dims)
    elif op in ("sin", "cos", "tan"):
        pass
    elif op == "sqrt":
        sub_dims = [0.0] * len(dims)
        _walk_dimensions(node.children[0], qid_to_dims, sub_dims)
        for i, _ in enumerate(dims):
            dims[i] += sub_dims[i] * 0.5
    else:
        for c in node.children:
            _walk_dimensions(c, qid_to_dims, dims)


def _lhs_dimensions(tree, qid_to_dims):
    node = tree
    while node.kind == "operator" and node.operator_type == "relational":
        node = node.children[0]
    dims = [0.0] * len(dimension_columns())
    _walk_dimensions(node, qid_to_dims, dims)
    return [int(round(d)) for d in dims]


def _compute_dimensions(conn, tree, empty_default):
    if tree is None:
        return empty_default
    return _lhs_dimensions(tree, _collect_qid_dimensions(conn))


def compute_formula_dimensions(conn, formula_id):
    """Compute dimensions from the LHS of a stored formula."""
    tokens = conn.execute(
        "SELECT * FROM formula_token WHERE formula_id = ? ORDER BY position",
        (formula_id,),
    ).fetchall()
    if not tokens:
        return []
    from scifind_lib.renderer import _evaluate_rpn
    try:
        tree = _evaluate_rpn(conn, [dict(t) for t in tokens])
    except Exception:
        return []
    return _compute_dimensions(conn, tree, [])


def compute_rpn_dimensions(conn, tokens):
    """Like compute_formula_dimensions, but on an in-memory RPN token list."""
    if not tokens:
        return [0.0] * len(dimension_columns())
    from scifind_lib.renderer import _evaluate_rpn
    try:
        tree = _evaluate_rpn(conn, tokens)
    except Exception:
        return [0.0] * len(dimension_columns())
    return _compute_dimensions(conn, tree, [0.0] * len(dimension_columns()))


def compute_default_unit_dimensions(conn, default_unit):
    """Base-dimension exponents for a default_unit JSON string.

    Zeros for absent/unparseable input; each unit contributes its
    quantity's exponents scaled by the JSON exponent."""
    total = [0] * len(dimension_columns())
    unit_qty = {r["id"]: r["quantity_id"]
                for r in conn.execute("SELECT id, quantity_id FROM unit")}
    qid_dims = _collect_qid_dimensions(conn)
    for unit_id, exponent in parse_default_unit(default_unit):
        for i, v in enumerate(qid_dims.get(unit_qty.get(unit_id), [])[: len(total)]):
            total[i] += v * exponent
    return [int(round(v)) for v in total]


def compute_all_formula_dimensions(conn, formula_ids=None):
    """{formula_id: {dim_M, dim_L, ...}} for all or given formulas."""
    cols = dimension_columns()
    ids = formula_ids if formula_ids is not None else {
        r["id"] for r in conn.execute("SELECT id FROM formula")}
    result = {}
    for fid in ids:
        dims = compute_formula_dimensions(conn, fid)
        result[fid] = dict(zip(cols, dims)) if dims else dict.fromkeys(cols, 0)
    return result


def format_number(n):
    if n == int(n):
        return str(int(n))
    return f"{n:.10f}".rstrip("0").rstrip(".")


def build_dimension_symbol_maps(conn):
    """(variable_map, unit_map, dim_map) for the dimension display."""
    qty_rows = conn.execute(
        f"SELECT id, symbol, default_unit FROM quantity "
        f"WHERE id IN ({','.join('?' * len(_BASE_DIMENSION_QTY_IDS))})",
        tuple(_BASE_DIMENSION_QTY_IDS.values()),
    ).fetchall()
    by_id = {r["id"]: r for r in qty_rows}
    variable_map, unit_map, dim_map = {}, {}, {}
    for symbol, qid in _BASE_DIMENSION_QTY_IDS.items():
        row = by_id.get(qid)
        variable_map[symbol] = (row["symbol"] if row and row["symbol"] else symbol)
        unit_map[symbol] = variable_map[symbol]
        if row and row["default_unit"]:
            try:
                first = json.loads(row["default_unit"])[0]
                uid = first.get("unit", "")
            except (ValueError, TypeError, IndexError, KeyError):
                uid = ""
            if uid:
                unit_row = conn.execute(
                    "SELECT symbol FROM unit WHERE id=?", (uid,),
                ).fetchone()
                if unit_row:
                    sym = unit_row["symbol"]
                    unit_map[symbol] = (sym if "\\" in sym else f"\\mathrm{{{sym}}}")
        dim_map[symbol] = symbol
    return variable_map, unit_map, dim_map
