"""Unified data-access layer."""

from dataclasses import dataclass, field
from itertools import groupby

from scifind_lib.db import in_clause, keyed_rows
from scifind_lib.formula import (
    dimension_columns,
    dimension_quantity_ids,
    dimension_symbols,
    filter_ops,
)
from scifind_lib.i18n import localise
from scifind_lib.tree import topic_tree_order
from scifind_lib.units import compound_unit_slug
from scifind_lib.util import eval_dim_expr, parse_int_or, safe_json_list

MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 10

_AND_OR = ("and", "or")

_NAME_EN = "json_extract(name, '$.en-us') AS name_en"
_DESC_EN = "json_extract(description, '$.en-us') AS description_en"


def _one(conn, table, row_id):
    """Single ``formula``/``quantity`` row with localisation helpers."""
    return conn.execute(
        f"SELECT *, {_NAME_EN}, {_DESC_EN}"
        f" FROM {table} WHERE id = ?",
        (row_id,),
    ).fetchone()


def _all(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def _first(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


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


def parse_csv_string(value):
    """Split a comma-separated query value into a list of stripped non-empty parts."""
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_mode(value, switched, key):
    """Resolve an and/or mode, accepting the legacy mode_switched toggle."""
    if switched:
        return "or" if key in switched else "and"
    return value if value in _AND_OR else "and"


def _dim_val(args, symbol, ops):
    """First matching dimension value for a symbol across filter ops."""
    for op in ops:
        val = eval_dim_expr(args.get(f"{symbol}_{op}"))
        if val is not None:
            return op, val
    return ops[0] if ops else "eq", None


def parse_filter_state(args, conn):
    """Parse query-string args into a QuantityFilter for the list pages."""
    mode_switched = set(parse_csv_string(args.get("mode_switched", "")))

    ops = filter_ops(conn)
    dimension_filter = {s: dict(zip(("op", "val"), _dim_val(args, s, ops)))
                        for s in dimension_symbols(conn)}

    ids_raw = args.get("ids")
    return QuantityFilter(
        ids=parse_csv_string(ids_raw) if ids_raw is not None else [],
        ids_provided=ids_raw is not None,
        exclude_all=args.get("exclude_all") == "1",
        quantity_ids=parse_csv_string(args.get("qty", "")),
        quantity_mode=_parse_mode(args.get("qty_mode", "and"), mode_switched, "fml"),
        diff_min=parse_int_or(args.get("diff_min"), MIN_DIFFICULTY),
        diff_max=parse_int_or(args.get("diff_max"), MAX_DIFFICULTY),
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
        " q.name AS quantity_name,"
        " c.symbol AS constant_symbol,"
        " c.unit AS constant_unit,"
        " c.name AS constant_name,"
        " rq.id AS related_quantity_id,"
        " rq.name AS related_quantity_name,"
        " rq.symbol AS related_quantity_symbol"
        " FROM formula_token ft"
        " LEFT JOIN quantity q ON q.id = ft.quantity_id"
        " LEFT JOIN constant c ON c.id = ft.constant_id"
        " LEFT JOIN quantity rq ON rq.id = c.quantity_id"
        " WHERE ft.formula_id = ?"
        " AND (q.id IS NULL OR q.hidden = 0)"
        " ORDER BY ft.position",
        (formula_id,))


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
        kind: keyed_rows(
            conn, _SEARCH_META_SQL[kind], [h[1] for h in hits if h[0] == kind])
        for kind in kinds if kind in _SEARCH_META_SQL
    }


def _quantity_rows(conn, from_join, where="", params=()):
    """Quantity rows with dimension columns, base dimensions first."""
    cols = ", ".join(f"q.{c}" for c in dimension_columns(conn))
    rows = _all(conn,
        f"SELECT DISTINCT q.id, q.name, q.symbol, {_NAME_EN},"
        f" q.topic_id, q.difficulty, {cols}"
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
    op_meta = {r["id"]: (r["arity"], r["type"] == "relational")
               for r in conn.execute("SELECT id, arity, type FROM operator")}

    def _left_of_first_comparison(token_rows):
        stack = []
        for row in token_rows:
            if row["token_kind"] != "operator":
                stack.append({row["quantity_id"]} if row["token_kind"] == "quantity" else set())
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
        " f.topic_id, f.difficulty,"
        " ft.token_kind, ft.quantity_id, ft.operator_id"
        " FROM formula f"
        " JOIN formula_token ft ON ft.formula_id = f.id"
        " WHERE f.id IN ("
        " SELECT DISTINCT formula_id FROM formula_token"
        " WHERE quantity_id = ? AND token_kind = 'quantity')"
        " ORDER BY f.topic_id, f.difficulty, f.id, ft.position",
        (quantity_id,))

    primary_out, non_primary_out = [], []
    for fid, token_rows in groupby(rows, key=lambda r: r["id"]):
        token_rows = list(token_rows)
        header = token_rows[0]
        formula = {"id": fid, "name": header["name"], "name_en": header["name_en"],
                   "topic_id": header["topic_id"], "difficulty": header["difficulty"]}
        (primary_out if quantity_id in _left_of_first_comparison(token_rows)
         else non_primary_out).append(formula)
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
    rows = keyed_rows(conn,
        "SELECT id, name FROM quantity WHERE id IN ({})", quantity_ids)
    return {rid: r["name"] for rid, r in rows.items()}


def fetch_unit(conn, unit_id):
    return _first(conn,
        "SELECT u.*, json_extract(q.name, '$.en-us') AS quantity_name,"
        " q.topic_id, json_extract(u.name, '$.en-us') AS name_en"
        " FROM unit u JOIN quantity q ON q.id = u.quantity_id"
        " WHERE u.id = ?",
        (unit_id,))


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
    base = ("FROM formula_token WHERE token_kind = 'quantity'"
            f" AND quantity_id IN ({placeholders})")
    if mode == "or":
        return {r["formula_id"] for r in _all(conn, f"SELECT DISTINCT formula_id {base}", params)}
    return {r["formula_id"] for r in _all(conn,
        f"SELECT formula_id, COUNT(DISTINCT quantity_id) AS match_count {base}"
        " GROUP BY formula_id HAVING match_count = ?", params + (len(set(quantity_ids)),))}


def fetch_all_constants(conn):
    return _all(conn, "SELECT id, name, symbol FROM constant ORDER BY id")


def fetch_constant(conn, constant_id):
    """One constant row with localisation helpers and its linked quantity."""
    return _first(conn,
        "SELECT c.*, rq.topic_id,"
        " json_extract(c.name, '$.en-us') AS name_en,"
        " json_extract(c.description, '$.en-us') AS description_en,"
        " rq.id AS related_quantity_id,"
        " rq.name AS related_quantity_name,"
        " rq.symbol AS related_quantity_symbol"
        " FROM constant c"
        " LEFT JOIN quantity rq ON rq.id = c.quantity_id"
        " WHERE c.id = ?",
        (constant_id,))


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
        " c.quantity_id, c.unit"
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


def _topic_diff_where(alias, topic_ids, diff_min, diff_max, extra=()):
    """Shared WHERE builder for topic/difficulty list pre-filters."""
    where, params = list(extra), []
    if topic_ids:
        marks, vals = in_clause(list(topic_ids))
        where.append(f"{alias}.topic_id IN ({marks})")
        params.extend(vals)
    if diff_min is not None and diff_max is not None:
        where.append(f"{alias}.difficulty BETWEEN ? AND ?")
        params.extend([diff_min, diff_max])
    return where, params


def fetch_formulas_filtered(conn, topic=None, diff_min=None, diff_max=None,
                              topic_ids=None):
    """Formulas filtered by topic and/or difficulty range (CLI + list pages)."""
    ids = topic_ids or ([topic] if topic else None)
    where, params = _topic_diff_where("f", ids, diff_min, diff_max)
    sql = ("SELECT f.id, f.name, json_extract(f.name, '$.en-us') AS name_en,"
           " f.topic_id, f.difficulty FROM formula f")
    if where:
        sql += " WHERE " + " AND ".join(where)
    return _all(conn, sql + " ORDER BY f.topic_id, f.difficulty, f.id", params)


def fetch_quantities_filtered(conn, topic_ids=None, diff_min=None, diff_max=None,
                               include_hidden=False):
    """Quantities filtered by topic/difficulty in SQL (base dimensions first)."""
    where, params = _topic_diff_where("q", topic_ids, diff_min, diff_max,
                                      [] if include_hidden else ["q.hidden = 0"])
    return _quantity_rows(conn, "quantity q",
                          f"WHERE {' AND '.join(where)}" if where else "", params)


def fetch_units_with_quantity(conn, quantity_id=None):
    """Unit rows joined with their quantity name, optionally filtered."""
    base = ("SELECT u.*, json_extract(q.name, '$.en-us') AS quantity_name"
            " FROM unit u JOIN quantity q ON q.id = u.quantity_id")
    if quantity_id:
        return _all(conn, f"{base} WHERE u.quantity_id = ?"
                     " ORDER BY u.is_base DESC, u.system, u.id", (quantity_id,))
    return _all(conn, f"{base} ORDER BY q.id, u.is_base DESC, u.system, u.id")


def fetch_compound_units(conn, quantity_id, only_non_base=False):
    """Compound-unit rows for a quantity, tagged with canonical id + kind."""
    sql = "SELECT * FROM compound_unit WHERE quantity_id = ?"
    if only_non_base:
        sql += " AND is_base = 0"
    return [dict(row, id=compound_unit_slug(row["quantity_id"], row["unit"]),
                 kind="compound_unit")
            for row in _all(conn, sql, (quantity_id,))]


def fetch_detail_items(conn, tokens):
    """Detail-items-shaped dicts from in-memory RPN tokens + overrides."""
    def _ids(kind, field):
        return {tok[field] for tok in tokens if tok.get("token_kind") == kind}
    qrows = keyed_rows(
        conn, "SELECT id, name, symbol, hidden FROM quantity WHERE id IN ({})",
        _ids("quantity", "quantity_id"))
    crows = keyed_rows(
        conn,
        "SELECT c.id, c.name, c.symbol, c.unit,"
        " rq.id AS related_quantity_id,"
        " rq.name AS related_quantity_name,"
        " rq.symbol AS related_quantity_symbol"
        " FROM constant c"
        " LEFT JOIN quantity rq ON rq.id = c.quantity_id"
        " WHERE c.id IN ({})",
        _ids("constant", "constant_id"))
    items = []
    for tok in tokens:
        if tok.get("token_kind") == "quantity":
            qrow = qrows.get(tok["quantity_id"])
            # Hidden sentinels (e.g. `drop`) never appear in detail tables,
            # mirroring fetch_formula_token_quantities.
            if not qrow or qrow.get("hidden"):
                continue
            qid = tok["quantity_id"]
            items.append({
                "quantity_id": qid,
                "quantity_symbol": qrow["symbol"],
                "quantity_name": qrow["name"],
                "symbol_overwrite": tok.get("symbol_overwrite") or "",
                "name_overwrite": tok.get("name_overwrite") or "",
                "label": tok.get("label") or "",
            })
        elif tok.get("token_kind") == "constant":
            crow = crows.get(tok["constant_id"])
            if crow:
                items.append({
                    "constant_id": tok["constant_id"],
                    "constant_symbol": crow["symbol"],
                    "constant_name": crow["name"],
                    "related_quantity_id": crow["related_quantity_id"] or "",
                    "related_quantity_name": crow["related_quantity_name"],
                    "related_quantity_symbol": crow["related_quantity_symbol"] or "",
                    "constant_unit": crow["unit"],
                })
    return items


def unit_is_base(conn, unit_id):
    """True if the unit row carries is_base = 1."""
    return bool(unit_id) and _first(conn,
        "SELECT 1 FROM unit WHERE id = ? AND is_base = 1 LIMIT 1", (unit_id,)) is not None


def fetch_prefixable_base_units(conn):
    """Ids of units that can carry an SI prefix."""
    ids = {r["id"] for r in _all(conn,
        "SELECT id FROM unit WHERE is_base = 1 AND system = 'SI'")}
    for r in _all(conn,
            "SELECT unit FROM compound_unit WHERE is_base = 1 AND system = 'SI'"):
        ids.update(entry["unit"] for entry in safe_json_list(r["unit"])
                   if isinstance(entry, dict) and entry.get("unit"))
    return ids


def fetch_si_prefix_map(conn, field="symbol", locale="en-us"):
    """{exponent_int: localised prefix field} for all SI prefixes."""
    return {int(p["id"]): localise(p[field], locale)
            for p in fetch_si_prefixes(conn)}




DEFAULT_LOCALE = "en-us"

SEARCHABLE_LOCALES = ("cs-cz", "en-us", "en-uk")

_SEARCH_SOURCES = (
    ("formula", "formula", None, ()),
    ("quantity", "quantity", "symbol", ("hidden = 0",)),
    ("unit", "unit", "symbol", ()),
    ("constant", "constant", "symbol", ()),
)


def search_entities(conn, query, limit=30, locale=DEFAULT_LOCALE):
    """Substring search over entity names/symbols/ids."""
    if not query or not query.strip():
        return []
    needle = query.strip().lower()
    like_pattern = f"%{needle.replace(chr(92), chr(92)*2).replace('%', chr(92)+'%').replace('_', chr(92)+'_')}%"
    locale_clauses = [f"LOWER(json_extract(name, '$.{loc}')) LIKE ? ESCAPE '{chr(92)}'"
                      for loc in SEARCHABLE_LOCALES]
    union_parts, params = [], []
    for table, kind, symbol_col, extra_clauses in _SEARCH_SOURCES:
        match = locale_clauses + ["LOWER(id) LIKE ? ESCAPE '\\'"]
        if symbol_col:
            match.append(f"LOWER({symbol_col}) LIKE ? ESCAPE '\\'")
        where = f"({' OR '.join(match)})"
        if extra_clauses:
            where += " AND " + " AND ".join(extra_clauses)
        union_parts.append(f"SELECT id, '{kind}' AS kind, name AS raw_name FROM {table} WHERE {where}")
        params.extend([like_pattern] * len(match))
    rows = conn.execute(f"SELECT * FROM ({' UNION ALL '.join(union_parts)})", params).fetchall()
    hits = [(r["kind"], r["id"], localise(r["raw_name"], locale)) for r in rows]
    hits.sort(key=lambda hit: (hit[2].strip().lower() != needle, len(hit[2])))
    return hits[:limit] if limit is not None else hits


_BASE_SORT_KEYS = ("id", "name", "diff_asc", "diff_desc", "topic_tree", "topic_alpha")
FORMULA_SORT_KEYS = _BASE_SORT_KEYS + ("qty",)
QUANTITY_SORT_KEYS = _BASE_SORT_KEYS
SEARCH_SORT_KEYS = ("relevance", "id", "name", "diff_asc", "diff_desc", "qty")
DEFAULT_FORMULA_SORT = "id"
DEFAULT_QUANTITY_SORT = "id"
DEFAULT_SEARCH_SORT = "relevance"

UNKNOWN_TREE_SORT_KEY = float("inf")


def normalize_sort(sort_key, allowed, default):
    """Single sort-key normalisation used by web + lib."""
    return sort_key if sort_key in allowed else default


def _difficulty_key(diff, sort_key, *tail):
    return ((diff if sort_key == "diff_asc" else -diff), *tail)


def entity_sort_key(row, sort_key, locale, tree_order, qty_const_tokens=None):
    if sort_key == "name":
        return (localise(row["name"], locale).lower(), row["id"])
    if sort_key in ("diff_asc", "diff_desc"):
        diff = row.get("difficulty") or 0
        return _difficulty_key(diff, sort_key, row["id"])
    if sort_key in ("topic_tree", "topic_alpha"):
        topic = row.get("topic_id") or ""
        if sort_key == "topic_alpha":
            return (topic, row["id"])
        return (tree_order.get(topic, UNKNOWN_TREE_SORT_KEY), topic, row["id"])
    if sort_key == "qty":
        return ((qty_const_tokens or {}).get(row["id"], []), row["id"])
    return (row["id"],)


def _sort_entities(conn, rows, sort_key, allowed, default, locale, with_qty):
    sort_key = normalize_sort(sort_key, allowed, default)
    qty_const_tokens = fetch_formula_quantity_constant_tokens(conn) if sort_key == "qty" else {}
    tree_order = topic_tree_order(conn) if sort_key == "topic_tree" else {}
    tokens = qty_const_tokens if with_qty else None
    rows = [r if isinstance(r, dict) else dict(r) for r in rows]
    return sorted(rows, key=lambda r: entity_sort_key(r, sort_key, locale, tree_order, tokens))


def sort_formulas(conn, rows, sort_key, locale="en-us"):
    return _sort_entities(conn, rows, sort_key, FORMULA_SORT_KEYS, DEFAULT_FORMULA_SORT, locale, True)


def sort_quantities(conn, rows, sort_key, locale="en-us"):
    return _sort_entities(conn, rows, sort_key, QUANTITY_SORT_KEYS, DEFAULT_QUANTITY_SORT, locale, False)


def sort_search_rows(conn, rows, sort_key, locale="en-us", meta_by_kind=None):
    sort_key = normalize_sort(sort_key, SEARCH_SORT_KEYS, DEFAULT_SEARCH_SORT)
    if sort_key == "relevance":
        return list(rows)
    if sort_key == "id":
        return sorted(rows, key=lambda r: (r[0], r[1]))
    if sort_key == "name":
        return sorted(rows, key=lambda r: ((r[2] or r[1]).lower(), r[0], r[1]))
    if meta_by_kind is None:
        meta_by_kind = fetch_search_meta(conn, rows)
    tokens = fetch_formula_quantity_constant_tokens(conn) if sort_key == "qty" else {}

    def _key(row):
        kind, ent_id = row[0], row[1]
        meta = meta_by_kind.get(kind, {}).get(ent_id) or {}
        if sort_key in ("diff_asc", "diff_desc"):
            diff = meta.get("difficulty") or meta.get("quantity_difficulty") or 0
            return _difficulty_key(diff, sort_key, kind, ent_id)
        if kind == "formula":
            qty_tokens = [f"{p:06d} {t} {i}" for p, t, i in tokens.get(ent_id, [])]
        elif kind == "quantity" or (kind == "unit" and meta.get("quantity_id")):
            qty_tokens = [f"quantity {meta['quantity_id'] if kind == 'unit' else ent_id}"]
        else:
            qty_tokens = []
        return (qty_tokens, kind, ent_id)

    return sorted(rows, key=_key)


def sort_quantities_base_first(quantity_rows, conn):
    """Sort quantities: base dimensions first, rest by id."""
    base_order = {qid: i for i, qid in enumerate(dimension_quantity_ids(conn).values())}
    return sorted(
        quantity_rows,
        key=lambda q: (base_order.get(q["id"], len(base_order)), q["id"]),
    )
