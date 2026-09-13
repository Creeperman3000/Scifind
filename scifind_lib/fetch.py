"""Unified data-access layer."""

import json
from dataclasses import dataclass, field
from itertools import groupby

from scifind_lib.db import in_clause
from scifind_lib.formula import (
    dimension_columns,
    dimension_quantity_ids,
    dimension_symbols,
    filter_ops,
)
from scifind_lib.i18n import localise
from scifind_lib.tree import topic_tree_order
from scifind_lib.units import compound_unit_slug

MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 10

_AND_OR = ("and", "or")

_NAME_EN = "json_extract(name, '$.en-us') AS name_en"
_DESC_EN = "json_extract(description, '$.en-us') AS description_en"


def _one(conn, table, row_id):
    """Single ``formula``/``quantity`` row with localisation helpers."""
    return conn.execute(
        f"SELECT *, {_NAME_EN}, topic_id AS topic_id, {_DESC_EN}"
        f" FROM {table} WHERE id = ?",
        (row_id,),
    ).fetchone()


def _all(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


@dataclass
class QuantityFilter:
    ids: list = field(default_factory=list)
    ids_provided: bool = False
    exclude_all: bool = False
    quantity_ids: list = field(default_factory=list)
    quantity_mode: str = "and"
    diff_min: int = MIN_DIFFICULTY
    diff_max: int = MAX_DIFFICULTY
    dimension_filter: dict = field(default_factory=dict)
    dim_mode: str = "and"
    base_quantity_only: bool = False

    @property
    def has_dimension_filter(self) -> bool:
        return any(d.get("val") is not None for d in self.dimension_filter.values())


def parse_int_with_default(value, default=None):
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_csv_string(value):
    """Split a comma-separated query value into a list of stripped non-empty parts."""
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_mode(value, switched, key):
    """Resolve an and/or mode, accepting the legacy mode_switched toggle."""
    if switched:
        return "or" if key in switched else "and"
    return value if value in _AND_OR else "and"


def parse_filter_state(args, conn):
    """Parse query-string args into a QuantityFilter for the list pages."""
    mode_switched = set(parse_csv_string(args.get("mode_switched", "")))

    ops = filter_ops(conn)
    default_op = ops[0] if ops else "eq"
    dimension_filter = {}
    for symbol in dimension_symbols(conn):
        dimension_filter[symbol] = {"op": default_op, "val": None}
        for op in ops:
            v = parse_int_with_default(args.get(f"{symbol}_{op}"))
            if v is not None:
                dimension_filter[symbol] = {"op": op, "val": v}
                break

    ids_raw = args.get("ids")
    return QuantityFilter(
        ids=parse_csv_string(ids_raw) if ids_raw is not None else [],
        ids_provided=ids_raw is not None,
        exclude_all=args.get("exclude_all") == "1",
        quantity_ids=parse_csv_string(args.get("qty", "")),
        quantity_mode=_parse_mode(args.get("qty_mode", "and"), mode_switched, "fml"),
        diff_min=parse_int_with_default(args.get("diff_min"), MIN_DIFFICULTY),
        diff_max=parse_int_with_default(args.get("diff_max"), MAX_DIFFICULTY),
        dimension_filter=dimension_filter,
        dim_mode=_parse_mode(args.get("dim_mode", "and"), mode_switched, "dim"),
        base_quantity_only=args.get("is_dim") == "1",
    )


def fetch_formula_quantity_constant_tokens(conn):
    """Return {formula_id: [(position, token_kind, identifier), ...]}."""
    rows = _all(conn,
        "SELECT formula_id, position, token_kind, quantity_id, constant_id "
        "FROM formula_token "
        "WHERE token_kind IN ('quantity', 'constant') "
        "ORDER BY formula_id, position")
    tokens_by_formula: dict = {}
    for r in rows:
        fid = r["formula_id"]
        ident = r["quantity_id"] if r["token_kind"] == "quantity" else r["constant_id"]
        tokens_by_formula.setdefault(fid, []).append((r["position"], r["token_kind"], ident))
    return tokens_by_formula


def fetch_formula(conn, formula_id):
    return _one(conn, "formula", formula_id)


def fetch_formula_relations(conn, formula_id):
    return _all(conn,
        "SELECT fr.relation_type, fr.related_id,"
        " f2.name AS name,"
        " json_extract(f2.name, '$.en-us') AS related_name"
        " FROM formula_relation fr"
        " JOIN formula f2 ON f2.id = fr.related_id"
        " WHERE fr.formula_id = ?"
        " ORDER BY fr.relation_type",
        (formula_id,))


def fetch_formula_token_quantities(conn, formula_id):
    """formula_token operand rows joined with quantity/constant metadata (drop excluded), in token order."""
    return _all(conn,
        "SELECT ft.*, q.symbol AS quantity_symbol,"
        " json_extract(q.name, '$.en-us') AS quantity_name,"
        " c.symbol AS constant_symbol,"
        " c.unit_id AS constant_unit_id,"
        " c.compound_unit_id AS constant_compound_unit_id,"
        " json_extract(c.name, '$.en-us') AS constant_name,"
        " rq.id AS related_quantity_id,"
        " json_extract(rq.name, '$.en-us') AS related_quantity_name,"
        " rq.symbol AS related_quantity_symbol"
        " FROM formula_token ft"
        " LEFT JOIN quantity q ON q.id = ft.quantity_id"
        " LEFT JOIN constant c ON c.id = ft.constant_id"
        " LEFT JOIN quantity rq ON rq.id = c.quantity_id"
        " WHERE ft.formula_id = ?"
        " AND (q.id IS NULL OR q.hidden = 0)"
        " ORDER BY ft.position",
        (formula_id,))


def fetch_keyed_rows(conn, sql, ids):
    """Map ``{id: dict(row)}`` for a SELECT with one ``{}`` IN-list slot; {} for empty ids."""
    if not ids:
        return {}
    placeholders, params = in_clause(ids)
    return {r["id"]: dict(r) for r in _all(conn, sql.format(placeholders), params)}


_SEARCH_META_SQL = {
    "formula": (
        "SELECT id, name, json_extract(name, '$.en-us') AS name_en,"
        " topic_id, difficulty FROM formula WHERE id IN ({})"
    ),
    "quantity": (
        "SELECT id, name, symbol, topic_id, difficulty"
        " FROM quantity WHERE id IN ({})"
    ),
    "unit": (
        "SELECT u.id, u.name, u.symbol, u.quantity_id,"
        " q.topic_id AS quantity_topic, q.difficulty AS quantity_difficulty"
        " FROM unit u LEFT JOIN quantity q ON q.id = u.quantity_id"
        " WHERE u.id IN ({})"
    ),
    "constant": (
        "SELECT c.id, c.name, c.symbol, c.difficulty,"
        " q.topic_id AS quantity_topic"
        " FROM constant c LEFT JOIN quantity q ON q.id = c.quantity_id"
        " WHERE c.id IN ({})"
    ),
}


def fetch_search_meta(conn, hits):
    """``{kind: {id: row}}`` for the kinds present in search hits, one query each."""
    kinds = {h[0] for h in hits}
    return {
        kind: fetch_keyed_rows(
            conn, _SEARCH_META_SQL[kind], [h[1] for h in hits if h[0] == kind])
        for kind in kinds if kind in _SEARCH_META_SQL
    }


def _quantity_rows(conn, from_join, where="", params=()):
    """Quantity rows with dimension columns, base dimensions first."""
    cols = ", ".join(f"q.{c}" for c in dimension_columns(conn))
    rows = _all(conn,
        f"SELECT DISTINCT q.id, q.name, q.symbol, {_NAME_EN},"
        f" q.topic_id AS topic_id, q.difficulty, {cols}"
        f" FROM {from_join} {where}", params)
    return sort_quantities_base_first(rows, conn)


def fetch_formula_quantities(conn, formula_id):
    return _quantity_rows(conn,
        "formula_token ft JOIN quantity q ON q.id = ft.quantity_id",
        "WHERE ft.formula_id = ?", (formula_id,))


def fetch_quantity(conn, quantity_id):
    return _one(conn, "quantity", quantity_id)


def fetch_quantity_units(conn, quantity_id):
    return _all(conn,
        "SELECT u.*, json_extract(u.name, '$.en-us') AS name_en"
        " FROM unit u WHERE u.quantity_id = ?"
        " ORDER BY u.is_base DESC,"
        " CASE u.system WHEN 'SI' THEN 0 WHEN 'CGS' THEN 1"
        " WHEN 'Imperial' THEN 2 ELSE 3 END, u.id",
        (quantity_id,))


def fetch_quantity_formulas(conn, quantity_id):
    """All formulas referencing a quantity, primary-side first."""
    primary, non_primary = fetch_quantity_formulas_by_side(conn, quantity_id)
    return primary + non_primary


def fetch_quantity_formulas_by_side(conn, quantity_id):
    """Return (primary, non-primary) formulas; primary holds the quantity left of the first comparison."""
    op_meta = {
        r["id"]: (r["arity"], r["type"] == "relational")
        for r in conn.execute("SELECT id, arity, type FROM operator")
    }

    def _left_of_first_comparison(token_rows):
        stack = []
        for row in token_rows:
            kind = row["token_kind"]
            if kind != "operator":
                stack.append({row["quantity_id"]} if kind == "quantity" else set())
                continue
            meta = op_meta.get(row["operator_id"])
            if meta is None:
                continue
            arity, is_comparison = meta
            if is_comparison:
                return set(stack[-arity]) if len(stack) >= arity else set()
            if len(stack) >= arity:
                merged = set().union(*stack[-arity:])
                del stack[-arity:]
                stack.append(merged)
        return set()

    rows = _all(conn,
        "SELECT f.id, f.name,"
        f" {_NAME_EN},"
        " f.topic_id AS topic_id, f.difficulty,"
        " ft.token_kind, ft.quantity_id, ft.operator_id"
        " FROM formula f"
        " JOIN formula_token ft ON ft.formula_id = f.id"
        " WHERE f.id IN ("
        " SELECT DISTINCT formula_id FROM formula_token"
        " WHERE quantity_id = ? AND token_kind = 'quantity')"
        " ORDER BY f.topic_id, f.difficulty, f.id, ft.position",
        (quantity_id,))

    formulas = []
    for fid, token_rows in groupby(rows, key=lambda r: r["id"]):
        token_rows = list(token_rows)
        header_row = token_rows[0]
        formulas.append({
            "id": fid,
            "name": header_row["name"],
            "name_en": header_row["name_en"],
            "topic_id": header_row["topic_id"],
            "difficulty": header_row["difficulty"],
            "_tokens": token_rows,
        })

    primary_out, non_primary_out = [], []
    for formula in formulas:
        is_primary = quantity_id in _left_of_first_comparison(formula.pop("_tokens"))
        (primary_out if is_primary else non_primary_out).append(formula)
    return primary_out, non_primary_out


def fetch_quantity_related_formulas(conn, quantity_id):
    return _all(conn,
        "SELECT DISTINCT f.id, f.name,"
        f" json_extract(f.name, '$.en-us') AS name_en,"
        " fr.relation_type"
        " FROM formula_relation fr"
        " JOIN formula f ON f.id = fr.related_id"
        " JOIN formula_token ft ON ft.formula_id = f.id"
        " WHERE ft.quantity_id = ?"
        " ORDER BY fr.relation_type, f.id",
        (quantity_id,))


def fetch_quantities_by_ids(conn, quantity_ids):
    """{id: name_json} for the given quantity ids in one query."""
    rows = fetch_keyed_rows(conn,
        "SELECT id, name FROM quantity WHERE id IN ({})", quantity_ids)
    return {rid: r["name"] for rid, r in rows.items()}


def fetch_unit(conn, unit_id):
    return conn.execute(
        """
        SELECT u.*, json_extract(q.name, '$.en-us') AS quantity_name,
               q.topic_id AS topic_id,
               json_extract(u.name, '$.en-us') AS name_en
        FROM unit u JOIN quantity q ON q.id = u.quantity_id
        WHERE u.id = ?
        """,
        (unit_id,),
    ).fetchone()


def fetch_si_prefixes(conn):
    """All SI prefixes, largest exponent first; id is the exponent as a string."""
    return _all(conn,
        "SELECT id, name, symbol FROM si_prefix ORDER BY CAST(id AS INTEGER) DESC")


def fetch_all_quantities(conn):
    """All quantities with dimension columns, base first; hidden backing rows excluded."""
    return _quantity_rows(conn, "quantity q", "WHERE q.hidden = 0")


def fetch_formulas_with_quantities(conn, quantity_ids, mode="and"):
    """Formula ids referencing ANY ("or") or ALL ("and") of the given quantity ids."""
    if not quantity_ids:
        return None
    placeholders, params = in_clause(quantity_ids)
    base = (f"FROM formula_token WHERE token_kind = 'quantity'"
            f" AND quantity_id IN ({placeholders})")
    if mode == "or":
        sql = f"SELECT DISTINCT formula_id {base}"
    else:
        sql = (f"SELECT formula_id, COUNT(DISTINCT quantity_id) AS match_count {base}"
               f" GROUP BY formula_id HAVING match_count = ?")
        params = params + (len(quantity_ids),)
    return {r["formula_id"] for r in _all(conn, sql, params)}


def fetch_formulas_with_any_quantity(conn, quantity_ids):
    return fetch_formulas_with_quantities(conn, quantity_ids, "or")


def fetch_formulas_with_all_quantities(conn, quantity_ids):
    return fetch_formulas_with_quantities(conn, quantity_ids, "and")


def fetch_all_constants(conn):
    return _all(conn, "SELECT id, name, symbol FROM constant ORDER BY id")


def fetch_constant(conn, constant_id):
    """One constant row with localisation helpers and its linked quantity."""
    return conn.execute(
        "SELECT c.*, rq.topic_id AS topic_id,"
        " json_extract(c.name, '$.en-us') AS name_en,"
        " json_extract(c.description, '$.en-us') AS description_en,"
        " rq.id AS related_quantity_id,"
        " rq.name AS related_quantity_name,"
        " rq.symbol AS related_quantity_symbol"
        " FROM constant c"
        " LEFT JOIN quantity rq ON rq.id = c.quantity_id"
        " WHERE c.id = ?",
        (constant_id,),
    ).fetchone()


def fetch_constant_formulas(conn, constant_id):
    """Formulas that reference the given constant."""
    return _all(conn,
        "SELECT DISTINCT f.id, f.name,"
        f" json_extract(f.name, '$.en-us') AS name_en,"
        " f.topic_id AS topic_id, f.difficulty"
        " FROM formula_token ft"
        " JOIN formula f ON f.id = ft.formula_id"
        " WHERE ft.token_kind = 'constant' AND ft.constant_id = ?"
        " ORDER BY f.topic_id, f.difficulty, f.id",
        (constant_id,))


def fetch_quantity_constants(conn, quantity_id):
    """Constants pointing at this quantity via constant.quantity_id."""
    return _all(conn,
        "SELECT c.id, c.name, c.symbol, c.value,"
        " c.unit_id, c.compound_unit_id"
        " FROM constant c WHERE c.quantity_id = ? ORDER BY c.id",
        (quantity_id,))


def fetch_all_operators(conn):
    return _all(conn,
        "SELECT id, symbol, aliases, arity, precedence, associativity, type,"
        " latex_template, dim_spec"
        " FROM operator ORDER BY type, precedence DESC, id")


def fetch_all_formulas(conn):
    return _all(conn,
        "SELECT f.id, f.name, json_extract(f.name, '$.en-us') AS name_en,"
        " f.topic_id AS topic_id, f.difficulty"
        " FROM formula f ORDER BY f.topic_id, f.difficulty, f.id")


def fetch_formulas_filtered(conn, topic=None, diff_min=None, diff_max=None):
    """Formulas filtered by topic and/or difficulty range (CLI + list pages)."""
    where, params = [], []
    if topic:
        where.append("f.topic_id = ?")
        params.append(topic)
    if diff_min is not None and diff_max is not None:
        # BETWEEN with equal bounds ≡ equality, so no special case needed.
        where.append("f.difficulty BETWEEN ? AND ?")
        params.extend([diff_min, diff_max])
    sql = ("SELECT f.id, json_extract(f.name, '$.en-us') AS name_en,"
           " f.topic_id AS topic_id, f.difficulty FROM formula f")
    if where:
        sql += " WHERE " + " AND ".join(where)
    return _all(conn, sql + " ORDER BY f.topic_id, f.difficulty, f.id", params)


def fetch_units_with_quantity(conn, quantity_id=None):
    """Unit rows joined with their quantity name, optionally filtered."""
    base = ("SELECT u.*, json_extract(q.name, '$.en-us') AS quantity_name"
            " FROM unit u JOIN quantity q ON q.id = u.quantity_id")
    where, params, order = "", (), "q.id, u.is_base DESC, u.system, u.id"
    if quantity_id:
        where, params, order = " WHERE u.quantity_id = ?", (quantity_id,), "u.is_base DESC, u.system, u.id"
    return _all(conn, f"{base}{where} ORDER BY {order}", params)


def fetch_compound_units(conn, quantity_id, only_non_base=False):
    """Compound-unit rows for a quantity, tagged with computed id + kind."""
    sql = "SELECT * FROM compound_unit WHERE quantity_id = ?"
    if only_non_base:
        sql += " AND is_base = 0"
    return [dict(row, id=compound_unit_slug(conn, row["quantity_id"], row["unit"]),
                 kind="compound_unit")
            for row in _all(conn, sql, (quantity_id,))]


def unit_is_base(conn, unit_id):
    """True if the unit row carries is_base = 1."""
    return bool(unit_id) and bool(_all(conn,
        "SELECT 1 FROM unit WHERE id = ? AND is_base = 1 LIMIT 1", (unit_id,)))


def fetch_prefixable_base_units(conn):
    """SI base unit id -> prefixable base id; mass prefixes attach to its gram part."""
    result = {r["id"]: r["id"] for r in _all(conn,
        "SELECT id FROM unit WHERE is_base = 1 AND system = 'SI'")}
    row = conn.execute(
        "SELECT quantity_id, unit FROM compound_unit "
        "WHERE quantity_id = 'mass' AND system = 'SI' AND is_base = 1").fetchone()
    if row is None:
        return result
    gram = next((p["unit"] for p in json.loads(row["unit"])
                 if p.get("prefix") is not None), None)
    if gram is None:
        return result
    result[gram] = gram
    result[compound_unit_slug(conn, row["quantity_id"], row["unit"])] = gram
    return result


def fetch_first_unit(conn, quantity_id):
    """First unit row for a quantity (fallback when no base row exists)."""
    return conn.execute(
        "SELECT * FROM unit WHERE quantity_id = ? LIMIT 1",
        (quantity_id,),
    ).fetchone()


def fetch_si_prefix_map(conn, field="symbol", locale="en-us"):
    """{exponent_int: localised prefix field} for all SI prefixes."""
    return {int(p["id"]): localise(p[field], locale)
            for p in fetch_si_prefixes(conn)}




DEFAULT_LOCALE = "en-us"

# Locale keys stored in the name JSON that search should match.
SEARCHABLE_LOCALES = ("cs-cz", "en-us", "en-uk")

# (table, kind, extra symbol column or None, extra AND clauses)
_SEARCH_SOURCES = (
    ("formula", "formula", None, ()),
    ("quantity", "quantity", "symbol", ("hidden = 0",)),
    ("unit", "unit", "symbol", ()),
    ("constant", "constant", "symbol", ()),
)


def search_entities(conn, query, limit=30, locale=DEFAULT_LOCALE):
    """Search entity names, symbols, and IDs via SQL LIKE substring match; hidden quantities never appear."""
    if not query or not query.strip():
        return []
    needle = query.strip().lower()
    like_pattern = f"%{needle}%"
    locale_clauses = [
        f"LOWER(json_extract(name, '$.{loc}')) LIKE ?"
        for loc in SEARCHABLE_LOCALES
    ]
    union_parts, params = [], []
    for table, kind, extra, extra_clauses in _SEARCH_SOURCES:
        match = locale_clauses + ["LOWER(id) LIKE ?"] + ([f"LOWER({extra}) LIKE ?"] if extra else [])
        where = f"({' OR '.join(match)})" + (" AND " + " AND ".join(extra_clauses) if extra_clauses else "")
        union_parts.append(f"SELECT id, '{kind}' AS kind, name AS raw_name FROM {table} WHERE {where}")
        params.extend([like_pattern] * len(match))
    rows = conn.execute(
        f"SELECT * FROM ({' UNION ALL '.join(union_parts)})", params
    ).fetchall()

    out = [(r["kind"], r["id"], localise(r["raw_name"], locale)) for r in rows]
    out.sort(key=lambda hit: (hit[2].strip().lower() != needle, len(hit[2])))
    return out[:limit] if limit is not None else out


def suggest_entities(conn, query, limit=8, locale=DEFAULT_LOCALE):
    return search_entities(conn, query, limit=limit, locale=locale)


_BASE_SORT_KEYS = ("id", "name", "diff_asc", "diff_desc", "topic_tree", "topic_alpha")
FORMULA_SORT_KEYS = _BASE_SORT_KEYS + ("qty",)
QUANTITY_SORT_KEYS = _BASE_SORT_KEYS
SEARCH_SORT_KEYS = (
    "relevance", "id", "name", "diff_asc", "diff_desc", "qty",
)
DEFAULT_FORMULA_SORT = "id"
DEFAULT_QUANTITY_SORT = "id"
DEFAULT_SEARCH_SORT = "relevance"

UNKNOWN_TREE_SORT_KEY = float("inf")


def _normalize(sort_key, allowed, default):
    return sort_key if sort_key in allowed else default


def entity_sort_key(row, sort_key, locale, tree_order, qty_const_tokens=None):
    if sort_key == "name":
        return (localise(row["name"], locale).lower(), row["id"])
    if sort_key in ("diff_asc", "diff_desc"):
        diff = row.get("difficulty") or 0
        return ((diff if sort_key == "diff_asc" else -diff), row["id"])
    if sort_key in ("topic_tree", "topic_alpha"):
        topic = row.get("topic_id") or ""
        if sort_key == "topic_alpha":
            return (topic, row["id"])
        return (tree_order.get(topic, UNKNOWN_TREE_SORT_KEY), topic, row["id"])
    if sort_key == "qty":
        return ((qty_const_tokens or {}).get(row["id"], []), row["id"])
    return (row["id"],)


def _sort_entities(conn, rows, sort_key, allowed, default, locale, with_qty):
    sort_key = _normalize(sort_key, allowed, default)
    qty_const_tokens = fetch_formula_quantity_constant_tokens(conn) if sort_key == "qty" else {}
    tree_order = topic_tree_order(conn) if sort_key == "topic_tree" else {}
    return sorted(rows, key=lambda r: entity_sort_key(
        r, sort_key, locale, tree_order,
        qty_const_tokens if with_qty else None))


def sort_formulas(conn, rows, sort_key, locale="en-us"):
    return _sort_entities(conn, rows, sort_key, FORMULA_SORT_KEYS, DEFAULT_FORMULA_SORT, locale, True)


def sort_quantities(conn, rows, sort_key, locale="en-us"):
    return _sort_entities(conn, rows, sort_key, QUANTITY_SORT_KEYS, DEFAULT_QUANTITY_SORT, locale, False)


def sort_search_rows(conn, rows, sort_key, locale="en-us", meta_by_kind=None):
    sort_key = _normalize(sort_key, SEARCH_SORT_KEYS, DEFAULT_SEARCH_SORT)
    if sort_key == "relevance":
        return list(rows)
    if sort_key == "id":
        return sorted(rows, key=lambda r: (r[0], r[1]))
    if sort_key == "name":
        return sorted(rows, key=lambda r: ((r[2] or r[1]).lower(), r[0], r[1]))
    meta_by_kind = meta_by_kind if meta_by_kind is not None else fetch_search_meta(conn, rows)
    tokens = fetch_formula_quantity_constant_tokens(conn) if sort_key == "qty" else {}

    def _key(row):
        kind, ent_id = row[0], row[1]
        meta = meta_by_kind.get(kind, {}).get(ent_id) or {}
        if sort_key in ("diff_asc", "diff_desc"):
            diff = meta.get("difficulty") or meta.get("quantity_difficulty") or 0
            return ((diff if sort_key == "diff_asc" else -diff), kind, ent_id)
        if kind == "formula":
            qt = [f"{p:06d} {t} {i}" for p, t, i in tokens.get(ent_id, [])]
        elif kind == "quantity":
            qt = [f"quantity {ent_id}"]
        elif kind == "unit" and meta.get("quantity_id"):
            qt = [f"quantity {meta['quantity_id']}"]
        else:
            qt = []
        return (qt, kind, ent_id)

    return sorted(rows, key=_key)


def sort_quantities_base_first(quantity_rows, conn):
    """Sort quantities: base dimensions first, rest by id."""
    base_order = {qid: i for i, qid in enumerate(dimension_quantity_ids(conn).values())}
    return sorted(
        quantity_rows,
        key=lambda q: (base_order.get(q["id"], len(base_order)), q["id"]),
    )
