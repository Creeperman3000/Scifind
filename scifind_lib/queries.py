"""Database query helpers — fetch_* functions and the SQL IN-clause builder."""
# Licensed under the LICENSE file in the project root.

import html
import re
from itertools import groupby

from scifind_lib.constants import _BASE_DIMENSION_QTY_IDS
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
    """Return formula_token operand rows joined with quantity/constant
    metadata (drop excluded), in token order."""
    return conn.execute(
        """
        SELECT ft.*, q.symbol AS quantity_symbol, q.default_unit,
               json_extract(q.name, '$.en-us') AS quantity_name,
               c.symbol AS constant_symbol,
               json_extract(c.name, '$.en-us') AS constant_name,
               rq.id AS related_quantity_id,
               json_extract(rq.name, '$.en-us') AS related_quantity_name,
               rq.symbol AS related_quantity_symbol,
               rq.default_unit AS related_quantity_default_unit
        FROM formula_token ft
        LEFT JOIN quantity q ON q.id = ft.quantity_id
        LEFT JOIN constant c ON c.id = ft.constant_id
        LEFT JOIN quantity rq ON rq.id = c.quantity_id
        WHERE ft.formula_id = ?
          AND (ft.quantity_id IS NULL OR ft.quantity_id != 'drop')
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
    # (arity, is_relational) per operator id
    op_meta = {
        r["id"]: (r["arity"], r["operator_type"] == "relational")
        for r in conn.execute("SELECT id, arity, operator_type FROM operator")
    }

    def _left_of_first_relational(token_rows):
        stack = []
        for row in token_rows:
            kind = row["token_kind"]
            if kind != "operator":
                stack.append({row["quantity_id"]} if kind == "quantity" else set())
                continue
            meta = op_meta.get(row["operator_id"])
            if meta is None:
                continue
            arity, relational = meta
            if relational:
                # operands pop right-first, so the left operand sits at -arity
                return set(stack[-arity]) if len(stack) >= arity else set()
            if len(stack) >= arity:
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

    formulas = []
    for fid, token_rows in groupby(rows, key=lambda r: r["id"]):
        token_rows = list(token_rows)
        meta = token_rows[0]
        formulas.append({
            "id": fid,
            "name": meta["name"],
            "name_en": meta["name_en"],
            "topic_id": meta["topic_id"],
            "difficulty": meta["difficulty"],
            "_tokens": token_rows,
        })

    primary_out, non_primary_out = [], []
    for formula in formulas:
        is_primary = quantity_id in _left_of_first_relational(formula.pop("_tokens"))
        (primary_out if is_primary else non_primary_out).append(formula)
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


def fetch_si_prefixes(conn):
    """All SI prefixes, largest exponent first."""
    return conn.execute(
        "SELECT id, symbol, name, exponent FROM si_prefix ORDER BY exponent DESC"
    ).fetchall()


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
        SELECT id, name, symbol
        FROM constant
        ORDER BY id
        """
    ).fetchall()


def fetch_constant(conn, constant_id):
    """One constant row with localisation helpers and its linked quantity."""
    return conn.execute(
        """
        SELECT c.*, rq.topic AS topic_id,
               json_extract(c.name, '$.en-us') AS name_en,
               json_extract(c.description, '$.en-us') AS description_en,
               rq.id AS related_quantity_id,
               rq.name AS related_quantity_name,
               rq.symbol AS related_quantity_symbol,
               rq.default_unit AS related_quantity_default_unit
        FROM constant c
        LEFT JOIN quantity rq ON rq.id = c.quantity_id
        WHERE c.id = ?
        """,
        (constant_id,),
    ).fetchone()


def fetch_constant_formulas(conn, constant_id):
    """Formulas that reference the given constant."""
    return conn.execute(
        """
        SELECT DISTINCT f.id, f.name,
               json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty
        FROM formula_token ft
        JOIN formula f ON f.id = ft.formula_id
        WHERE ft.token_kind = 'constant' AND ft.constant_id = ?
        ORDER BY f.topic, f.difficulty, f.id
        """,
        (constant_id,),
    ).fetchall()


def fetch_quantity_constants(conn, quantity_id):
    """Constants pointing at this quantity via constant.quantity_id."""
    return conn.execute(
        """
        SELECT c.id, c.name, c.symbol, c.value,
               COALESCE(rq.default_unit, c.default_unit) AS unit_default
        FROM constant c
        LEFT JOIN quantity rq ON rq.id = c.quantity_id
        WHERE c.quantity_id = ?
        ORDER BY c.id
        """,
        (quantity_id,),
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


def sort_quantities_by_dimension(quantity_rows):
    """Sort quantities: base dimensions first, rest by id."""
    # Canonical base-dimension ordering lives in constants.py; the index
    # doubles as the "is a base quantity" marker (len = not one).
    base_order = {qid: i for i, qid in enumerate(_BASE_DIMENSION_QTY_IDS.values())}
    def key(quantity):
        base_index = base_order.get(quantity["id"], len(base_order))
        return (0 if base_index < len(base_order) else 1, base_index, quantity["id"])
    return sorted(quantity_rows, key=key)
