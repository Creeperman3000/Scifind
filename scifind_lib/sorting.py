"""Sorting helpers used by the list pages."""
# Licensed under the LICENSE file in the project root.

from scifind_lib.queries import _in_clause, fetch_formula_qty_const_tokens
from scifind_lib.tree import topic_tree_order
from scifind_lib.i18n import localise


FORMULA_SORT_KEYS = (
    "id", "name", "diff_asc", "diff_desc", "topic_tree", "topic_alpha", "qty",
)
QUANTITY_SORT_KEYS = (
    "id", "name", "diff_asc", "diff_desc", "topic_tree", "topic_alpha",
)
SEARCH_SORT_KEYS = (
    "relevance", "id", "name", "diff_asc", "diff_desc", "qty",
)
DEFAULT_FORMULA_SORT = "id"
DEFAULT_QUANTITY_SORT = "id"
DEFAULT_SEARCH_SORT = "relevance"


def entity_sort_key(row, sort_key, locale, tree_order, qty_const_tokens=None):
    """Sort key shared by formulas and quantities."""
    if sort_key == "name":
        return (localise(row["name"], locale).lower(), row["id"])
    if sort_key == "diff_asc":
        return (row.get("difficulty") or 0, row["id"])
    if sort_key == "diff_desc":
        return (-(row.get("difficulty") or 0), row["id"])
    if sort_key in ("topic_tree", "topic_alpha"):
        topic = row.get("topic_id") or ""
        if sort_key == "topic_tree":
            return (tree_order.get(topic, 10 ** 9), topic, row["id"])
        return (topic, row["id"])
    if sort_key == "qty":
        tokens = (qty_const_tokens or {}).get(row["id"], [])
        return (tokens, row["id"])
    return (row["id"],)


def sort_formulas(conn, rows, sort_key, locale="en-us"):
    """Return formula dict-rows sorted by the given key."""
    if sort_key not in FORMULA_SORT_KEYS:
        sort_key = DEFAULT_FORMULA_SORT
    qty_const_tokens = fetch_formula_qty_const_tokens(conn) if sort_key == "qty" else {}
    tree_order = topic_tree_order() if sort_key == "topic_tree" else {}
    key_fn = lambda r: entity_sort_key(r, sort_key, locale, tree_order, qty_const_tokens)
    return sorted(rows, key=key_fn)


def sort_quantities(rows, sort_key, locale="en-us"):
    """Return quantity dict-rows sorted by the given key."""
    if sort_key not in QUANTITY_SORT_KEYS:
        sort_key = DEFAULT_QUANTITY_SORT
    tree_order = topic_tree_order() if sort_key == "topic_tree" else {}
    key_fn = lambda r: entity_sort_key(r, sort_key, locale, tree_order)
    return sorted(rows, key=key_fn)


def sort_search_rows(conn, rows, sort_key, locale="en-us"):
    """Sort mixed search hits (kind, id, display_name)."""
    if sort_key not in SEARCH_SORT_KEYS:
        sort_key = DEFAULT_SEARCH_SORT
    if sort_key == "relevance":
        return list(rows)

    formula_ids = [r[1] for r in rows if r[0] == "formula"]
    quantity_ids = [r[1] for r in rows if r[0] == "quantity"]
    unit_ids = [r[1] for r in rows if r[0] == "unit"]

    formula_meta = {}
    if formula_ids:
        placeholders, params = _in_clause(formula_ids)
        for fr in conn.execute(
            f"SELECT id, name, topic, difficulty FROM formula WHERE id IN ({placeholders})",
            params,
        ).fetchall():
            formula_meta[fr["id"]] = dict(fr)

    quantity_meta = {}
    if quantity_ids:
        placeholders, params = _in_clause(quantity_ids)
        for qr in conn.execute(
            f"SELECT id, name, topic, difficulty FROM quantity WHERE id IN ({placeholders})",
            params,
        ).fetchall():
            quantity_meta[qr["id"]] = dict(qr)

    unit_meta = {}
    if unit_ids:
        placeholders, params = _in_clause(unit_ids)
        for ur in conn.execute(
            f"""
            SELECT u.id, u.name, u.quantity_id, q.name AS quantity_name,
                   q.topic AS quantity_topic, q.difficulty AS quantity_difficulty
            FROM unit u LEFT JOIN quantity q ON q.id = u.quantity_id
            WHERE u.id IN ({placeholders})
            """,
            params,
        ).fetchall():
            unit_meta[ur["id"]] = dict(ur)

    qty_const_tokens = fetch_formula_qty_const_tokens(conn)
    tree_order = topic_tree_order() if sort_key in ("topic_tree", "topic_alpha") else {}

    def key(row):
        kind, ent_id, display_name = row[0], row[1], row[2]
        if sort_key == "id":
            return (kind, ent_id)
        if sort_key == "name":
            name = display_name or ent_id
            return (name.lower(), kind, ent_id)
        if sort_key in ("diff_asc", "diff_desc", "topic_tree", "topic_alpha"):
            meta = None
            if kind == "formula":
                meta = formula_meta.get(ent_id)
            elif kind == "quantity":
                meta = quantity_meta.get(ent_id)
            elif kind == "unit":
                meta = unit_meta.get(ent_id)
            if meta is None:
                difficulty = 0
                topic = ""
            else:
                difficulty = meta.get("difficulty") or meta.get("quantity_difficulty") or 0
                topic = meta.get("topic") or meta.get("quantity_topic") or ""
            if sort_key == "diff_asc":
                return (difficulty, kind, ent_id)
            if sort_key == "diff_desc":
                return (-difficulty, kind, ent_id)
            if sort_key == "topic_tree":
                return (tree_order.get(topic, 10 ** 9), topic, kind, ent_id)
            return (topic, kind, ent_id)
        if sort_key == "qty":
            if kind == "formula":
                tokens = qty_const_tokens.get(ent_id, [])
                return (tokens, kind, ent_id)
            if kind == "quantity":
                return (["quantity:" + ent_id], kind, ent_id)
            if kind == "unit":
                meta = unit_meta.get(ent_id)
                qid = meta["quantity_id"] if meta else None
                return (["quantity:" + qid] if qid else [], kind, ent_id)
            return ([], kind, ent_id)
        return (kind, ent_id)

    return sorted(rows, key=key)
