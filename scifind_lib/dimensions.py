"""Base dimensions: order, format helpers, and dimensional walker."""

import logging

from scifind_lib.constants import (
    _BASE_DIMENSION_ORDER,
    _BASE_DIMENSION_QTY_IDS,
)
from scifind_lib.i18n import wrap_symbol_in_latex
from scifind_lib.units import parse_compound_unit

logger = logging.getLogger("scifind.dimensions")


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
                     else f"{symbol}^{format_dimension_number(exponent)}")
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


def dimensions_from_row(row):
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
    qid_dims = {
        r["id"]: [r[c] for c in dimension_columns()]
        for r in conn.execute(f"SELECT id, {', '.join(dimension_columns())} FROM quantity")
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


def _walk_dimensions(node, qid_to_dims, dims):
    """Sum the dimensional exponents of every quantity under `node`.

    Explicit-stack iterative walk so deep formulas can't blow the recursion
    limit; raises `DimensionMismatchError` on structurally invalid forms.
    """
    stack = [(node, False)]
    while stack:
        n, returning = stack.pop()
        if n.kind != "operator":
            if n.kind == "quantity":
                if n.quantity_id not in qid_to_dims:
                    raise DimensionMismatchError(
                        f"quantity {n.quantity_id!r} has no registered dimensions"
                    )
                for i, v in enumerate(qid_to_dims[n.quantity_id]):
                    dims[i] += v
            elif n.kind == "constant":
                if n.constant_id not in qid_to_dims:
                    continue
                for i, v in enumerate(qid_to_dims[n.constant_id]):
                    dims[i] += v
            continue
        op = n.operator_id
        children = n.children
        if op in ("div", "frac"):
            lhs, rhs = [0.0] * len(dims), [0.0] * len(dims)
            _walk_dimensions(children[0], qid_to_dims, lhs)
            _walk_dimensions(children[1], qid_to_dims, rhs)
            for i in range(len(dims)):
                dims[i] += lhs[i] - rhs[i]
            continue
        if op == "pow":
            base, exp = children
            sub_dims = [0.0] * len(dims)
            exp_dims = [0.0] * len(dims)
            if exp.kind == "number" and exp.value is not None:
                _walk_dimensions(base, qid_to_dims, sub_dims)
                for i, v in enumerate(sub_dims):
                    dims[i] += v * exp.value
                continue
            _walk_dimensions(exp, qid_to_dims, exp_dims)
            if any(abs(v) > 1e-9 for v in exp_dims):
                raise DimensionMismatchError(
                    f"exponent must be dimensionless; got {exp_dims}"
                )
            if exp.kind == "quantity" or exp.kind == "operator":
                _walk_dimensions(base, qid_to_dims, sub_dims)
                for i, v in enumerate(sub_dims):
                    dims[i] += v
                continue
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
            for i in range(len(dims)):
                dims[i] += lhs[i]
            continue
        if op in ("sin", "cos", "tan"):
            arg = [0.0] * len(dims)
            _walk_dimensions(children[0], qid_to_dims, arg)
            if any(abs(v) > 1e-9 for v in arg):
                raise DimensionMismatchError(
                    f"argument of {op} must be dimensionless; got {arg}"
                )
            continue
        if op == "sqrt":
            sub_dims = [0.0] * len(dims)
            _walk_dimensions(children[0], qid_to_dims, sub_dims)
            for i, _ in enumerate(dims):
                dims[i] += sub_dims[i] * 0.5
            continue
        for c in children:
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
    from scifind_lib.renderer import reduce_rpn_to_tree
    try:
        tree = reduce_rpn_to_tree(conn, [dict(t) for t in tokens])
    except Exception as exc:
        logger.warning("formula %s: RPN evaluation failed: %s", formula_id, exc)
        return []
    try:
        return _compute_dimensions(conn, tree, [])
    except DimensionMismatchError as exc:
        logger.warning("formula %s: %s", formula_id, exc)
        return []


def compute_rpn_dimensions(conn, tokens):
    """Like compute_formula_dimensions, but on an in-memory RPN token list."""
    if not tokens:
        return [0.0] * len(dimension_columns())
    from scifind_lib.renderer import reduce_rpn_to_tree
    try:
        tree = reduce_rpn_to_tree(conn, tokens)
    except Exception as exc:
        logger.warning("RPN evaluation failed: %s", exc)
        return [0.0] * len(dimension_columns())
    try:
        return _compute_dimensions(conn, tree, [0.0] * len(dimension_columns()))
    except DimensionMismatchError as exc:
        logger.warning("%s", exc)
        return [0.0] * len(dimension_columns())


def compute_compound_unit_dimensions(conn, compound_unit_json):
    """Base-dimension exponents for a `compound_unit.unit` JSON string (zeros unparseable)."""
    total = [0] * len(dimension_columns())
    unit_qty = {r["id"]: r["quantity_id"]
                for r in conn.execute("SELECT id, quantity_id FROM unit")}
    qid_dims = _collect_qid_dimensions(conn)
    for unit_id, exponent in parse_compound_unit(compound_unit_json):
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


def format_dimension_number(n):
    if n == int(n):
        return str(int(n))
    return f"{n:.10f}".rstrip("0").rstrip(".")


def build_dimension_symbol_triplet(conn):
    """(variable_map, unit_map, dim_map) for the dimension display.

    `unit_map` uses the SI base symbol for each base dimension (kg, m², …),
    i.e. the row carrying `is_base=1` for the base quantity in the SI system.
    """
    from scifind_lib.units import format_compound_unit_symbol, select_base_unit
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