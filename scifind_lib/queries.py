"""Database query helpers — fetch_* functions and the SQL IN-clause builder."""
# Licensed under the LICENSE file in the project root.

import html
import re

from scifind_lib.dimensions import (
    dimension_columns,
    extract_dimensions_from_row,
)
from scifind_lib.i18n import localise
from scifind_lib.tree import topic_name_map


def fetch_formula_qty_const_tokens(conn):
    """Return {formula_id: [(position, token_kind, identifier), ...]}."""
    rows = conn.execute(
        "SELECT formula_id, position, token_kind, quantity_id, constant_id "
        "FROM formula_token "
        "WHERE token_kind IN ('quantity', 'constant') "
        "ORDER BY formula_id, position"
    ).fetchall()
    result: dict = {}
    for r in rows:
        fid = r["formula_id"]
        ident = r["quantity_id"] if r["token_kind"] == "quantity" else r["constant_id"]
        result.setdefault(fid, []).append((r["position"], r["token_kind"], ident))
    return result


def _in_clause(ids):
    """Build a `(?, ?, …)` placeholder list for an IN clause + the tuple of values."""
    return ",".join("?" for _ in ids), tuple(ids)


def fetch_formula(conn, formula_id):
    return conn.execute(
        """
        SELECT *, json_extract(name, '$.en-us') AS name_en,
               topic AS topic_id,
               json_extract(description, '$.en-us') AS description_en
        FROM formula WHERE id = ?
        """,
        (formula_id,),
    ).fetchone()


def fetch_formula_related(conn, formula_id):
    return conn.execute(
        """
        SELECT fr.relation_type, fr.related_id,
               f2.name AS name,
               json_extract(f2.name, '$.en-us') AS related_name
        FROM formula_relation fr
        JOIN formula f2 ON f2.id = fr.related_id
        WHERE fr.formula_id = ?
        ORDER BY fr.relation_type
        """,
        (formula_id,),
    ).fetchall()


def fetch_formula_detail_items(conn, formula_id):
    """Return formula_token rows joined with quantity metadata (drop excluded)."""
    return conn.execute(
        """
        SELECT ft.*, q.symbol AS quantity_symbol, q.default_unit,
               json_extract(q.name, '$.en-us') AS quantity_name
        FROM formula_token ft
        LEFT JOIN quantity q ON q.id = ft.quantity_id
        WHERE ft.formula_id = ? AND ft.quantity_id != 'drop'
        ORDER BY ft.position
        """,
        (formula_id,),
    ).fetchall()


def render_variable_base(item, locale="en-us"):
    """Render the base variable symbol (without exponent) for display tables."""
    var = (localise(item.get("symbol_overwrite") or "", locale)
           or item.get("quantity_symbol")
           or item.get("quantity_id")
           or "?")
    label = localise(item.get("label") or "", locale)
    if label and "_" not in var:
        var += "_{" + label + "}"
    return var


def parse_quantity_name_markers(text):
    """Replace [quantity_id] or [quantity_id|display_text] markers with <a> links."""
    def _repl(m):
        raw = m.group(1)
        if "|" in raw:
            qid, display = raw.split("|", 1)
        else:
            qid = display = raw
        qid = qid.lower().replace(" ", "_")
        return f'<a href="/quantity/{html.escape(qid)}">{html.escape(display)}</a>'
    return re.sub(r"\[([^\]]+)\]", _repl, text)


def fetch_formula_quantities(conn, formula_id):
    rows = conn.execute(
        f"""
        SELECT DISTINCT q.id, q.name, q.symbol,
               json_extract(q.name, '$.en-us') AS name_en,
               COALESCE(ft.quantity_name_overwrite, q.name) AS display_name_raw,
               q.default_unit,
               {', '.join(f'q.{c}' for c in dimension_columns())}
        FROM formula_token ft
        JOIN quantity q ON q.id = ft.quantity_id
        WHERE ft.formula_id = ?
        """,
        (formula_id,),
    ).fetchall()
    return sort_quantities_by_dimension(rows)


def fetch_quantity(conn, quantity_id):
    return conn.execute(
        """
        SELECT *, json_extract(name, '$.en-us') AS name_en,
               topic AS topic_id,
               json_extract(description, '$.en-us') AS description_en
        FROM quantity WHERE id = ?
        """,
        (quantity_id,),
    ).fetchone()


def fetch_quantity_units(conn, quantity_id):
    return conn.execute(
        """
        SELECT u.*, json_extract(u.name, '$.en-us') AS name_en
        FROM unit u WHERE u.quantity_id = ?
        ORDER BY u.default_unit DESC, u.unit_system
        """,
        (quantity_id,),
    ).fetchall()


def fetch_quantity_formulas(conn, quantity_id):
    return conn.execute(
        """
        SELECT DISTINCT f.id, f.name,
               json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty
        FROM formula_token ft
        JOIN formula f ON f.id = ft.formula_id
        WHERE ft.quantity_id = ?
        ORDER BY f.topic, f.difficulty, f.id
        """,
        (quantity_id,),
    ).fetchall()


def fetch_quantity_formulas_by_side(conn, quantity_id):
    """Return (primary, non_primary) formulas for a quantity.

    Formulas are stored as RPN token streams, so side membership cannot
    be decided from raw token positions (every operand precedes its
    trailing operator). Instead each stream is evaluated with a stack of
    per-subtree quantity-id sets: a formula is primary when the quantity
    occurs in the left operand of the first relational operator
    (=, ≈, ∝, <, >, …); everything else (right side only, or formulas
    without a relational operator at all) is non-primary.
    """
    arities = {}
    rel_arities = {}
    for op in conn.execute("SELECT id, arity, operator_type FROM operator"):
        arities[op["id"]] = op["arity"]
        if op["operator_type"] == "relational":
            rel_arities[op["id"]] = op["arity"]

    def _left_of_first_relational(token_rows):
        stack = []
        for row in token_rows:
            kind = row["token_kind"]
            if kind != "operator":
                stack.append({row["quantity_id"]} if kind == "quantity" else set())
                continue
            op_id = row["operator_id"]
            if op_id in rel_arities:
                # operands pop right-first, so the left operand sits at -arity
                arity = rel_arities[op_id]
                return set(stack[-arity]) if len(stack) >= arity else set()
            arity = arities.get(op_id)
            if arity and len(stack) >= arity:
                merged = set().union(*stack[-arity:])
                del stack[-arity:]
                stack.append(merged)
        return set()

    rows = conn.execute(
        """
        SELECT f.id, f.name,
               json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty,
               ft.token_kind, ft.quantity_id, ft.operator_id
        FROM formula f
        JOIN formula_token ft ON ft.formula_id = f.id
        WHERE f.id IN (
            SELECT DISTINCT formula_id FROM formula_token
            WHERE quantity_id = ? AND token_kind = 'quantity'
        )
        ORDER BY f.topic, f.difficulty, f.id, ft.position
        """,
        (quantity_id,),
    ).fetchall()

    primary, non_primary = [], []
    current = None
    for row in rows:
        fid = row["id"]
        if current is None or current["id"] != fid:
            current = {
                "id": fid,
                "name": row["name"],
                "name_en": row["name_en"],
                "topic_id": row["topic_id"],
                "difficulty": row["difficulty"],
                "_tokens": [],
            }
            primary.append(current)
        current["_tokens"].append(row)

    def _is_primary(formula):
        return quantity_id in _left_of_first_relational(formula.pop("_tokens"))

    primary_out, non_primary_out = [], []
    for f in primary:
        (primary_out if _is_primary(f) else non_primary_out).append(f)
    return primary_out, non_primary_out


def fetch_quantity_related_formulas(conn, quantity_id):
    return conn.execute(
        """
        SELECT DISTINCT f.id, f.name,
               json_extract(f.name, '$.en-us') AS name_en,
               fr.relation_type
        FROM formula_relation fr
        JOIN formula f ON f.id = fr.related_id
        JOIN formula_token ft ON ft.formula_id = f.id
        WHERE ft.quantity_id = ?
        ORDER BY fr.relation_type, f.id
        """,
        (quantity_id,),
    ).fetchall()


def fetch_quantities_by_ids(conn, quantity_ids):
    """{id: name_json} for the given quantity ids in one query."""
    if not quantity_ids:
        return {}
    placeholders, params = _in_clause(quantity_ids)
    rows = conn.execute(
        f"SELECT id, name FROM quantity WHERE id IN ({placeholders})",
        params,
    ).fetchall()
    return {r["id"]: r["name"] for r in rows}


def fetch_si_unit_symbol(conn, quantity_id):
    row = conn.execute(
        "SELECT symbol FROM unit WHERE quantity_id = ? AND default_unit = 1 LIMIT 1",
        (quantity_id,),
    ).fetchone()
    return row["symbol"] if row else ""


def fetch_unit(conn, unit_id):
    return conn.execute(
        """
        SELECT u.*, json_extract(q.name, '$.en-us') AS quantity_name,
               q.topic AS topic_id,
               json_extract(u.name, '$.en-us') AS name_en
        FROM unit u JOIN quantity q ON q.id = u.quantity_id
        WHERE u.id = ?
        """,
        (unit_id,),
    ).fetchone()


def fetch_all_quantities(conn):
    """Return all quantities with dimension columns, base dimensions first."""
    rows = conn.execute(
        f"""
        SELECT q.id, q.name, q.symbol,
               json_extract(q.name, '$.en-us') AS name_en,
               q.topic AS topic_id, q.difficulty, q.default_unit,
               {', '.join(f'q.{c}' for c in dimension_columns())}
        FROM quantity q
        ORDER BY q.id
        """
    ).fetchall()
    return sort_quantities_by_dimension(rows)


def fetch_formulas_with_any_quantity(conn, quantity_ids):
    """Return formula_ids that reference ANY of the given quantity IDs (OR)."""
    if not quantity_ids:
        return None
    placeholders, params = _in_clause(quantity_ids)
    rows = conn.execute(
        f"SELECT DISTINCT formula_id FROM formula_token "
        f"WHERE token_kind = 'quantity' AND quantity_id IN ({placeholders})",
        params,
    ).fetchall()
    return {r["formula_id"] for r in rows}


def fetch_formulas_with_all_quantities(conn, quantity_ids):
    """Return formula_ids that reference ALL of the given quantity IDs (AND)."""
    if not quantity_ids:
        return None
    placeholders, params = _in_clause(quantity_ids)
    rows = conn.execute(
        f"SELECT formula_id, COUNT(DISTINCT quantity_id) AS match_count "
        f"FROM formula_token "
        f"WHERE token_kind = 'quantity' AND quantity_id IN ({placeholders}) "
        f"GROUP BY formula_id HAVING match_count = ?",
        params + (len(quantity_ids),),
    ).fetchall()
    return {r["formula_id"] for r in rows}


def fetch_all_constants(conn):
    return conn.execute(
        """
        SELECT id, name, symbol, value
        FROM constant
        ORDER BY id
        """
    ).fetchall()


def fetch_all_operators(conn):
    return conn.execute(
        """
        SELECT id, symbol, math, arity, precedence, associativity, operator_type
        FROM operator
        ORDER BY operator_type, precedence DESC, id
        """
    ).fetchall()


def fetch_all_formulas(conn):
    return conn.execute(
        """
        SELECT f.id, f.name, json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty
        FROM formula f
        ORDER BY f.topic, f.difficulty, f.id
        """
    ).fetchall()


def _base_dimension_order():
    return {qid: i for i, qid in enumerate([
        "mass", "length", "time", "current",
        "temperature", "amount", "luminous_intensity",
    ])}


def sort_quantities_by_dimension(quantity_rows):
    """Sort quantities: base dimensions first, rest by id."""
    base_order = _base_dimension_order()
    def key(quantity):
        base_index = base_order.get(quantity["id"], 99)
        return (0 if base_index < 99 else 1, base_index, quantity["id"])
    return sorted(quantity_rows, key=key)
