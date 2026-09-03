"""Sorting helpers used by the list pages."""

from scifind_lib.constants import _BASE_DIMENSION_QTY_IDS
from scifind_lib.db import in_clause
from scifind_lib.queries import fetch_formula_quantity_constant_tokens
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

UNKNOWN_TREE_SORT_KEY = float("inf")


def _metadata_by_id(conn, sql, ids):
    if not ids:
        return {}
    placeholders, params = in_clause(ids)
    return {r["id"]: dict(r)
            for r in conn.execute(sql.format(placeholders), params).fetchall()}


def entity_sort_key(row, sort_key, locale, tree_order, qty_const_tokens=None):
    if sort_key == "name":
        return (localise(row["name"], locale).lower(), row["id"])
    if sort_key == "diff_asc":
        return (row.get("difficulty") or 0, row["id"])
    if sort_key == "diff_desc":
        return (-(row.get("difficulty") or 0), row["id"])
    if sort_key in ("topic_tree", "topic_alpha"):
        topic = row.get("topic_id") or ""
        if sort_key == "topic_tree":
            return (tree_order.get(topic, UNKNOWN_TREE_SORT_KEY), topic, row["id"])
        return (topic, row["id"])
    if sort_key == "qty":
        tokens = (qty_const_tokens or {}).get(row["id"], [])
        return (tokens, row["id"])
    return (row["id"],)


def sort_formulas(conn, rows, sort_key, locale="en-us"):
    if sort_key not in FORMULA_SORT_KEYS:
        sort_key = DEFAULT_FORMULA_SORT
    qty_const_tokens = fetch_formula_quantity_constant_tokens(conn) if sort_key == "qty" else {}
    tree_order = topic_tree_order() if sort_key == "topic_tree" else {}
    key_fn = lambda r: entity_sort_key(r, sort_key, locale, tree_order, qty_const_tokens)
    return sorted(rows, key=key_fn)


def sort_quantities(rows, sort_key, locale="en-us"):
    if sort_key not in QUANTITY_SORT_KEYS:
        sort_key = DEFAULT_QUANTITY_SORT
    tree_order = topic_tree_order() if sort_key == "topic_tree" else {}
    key_fn = lambda r: entity_sort_key(r, sort_key, locale, tree_order)
    return sorted(rows, key=key_fn)


def sort_search_rows(conn, rows, sort_key, locale="en-us"):
    if sort_key not in SEARCH_SORT_KEYS:
        sort_key = DEFAULT_SEARCH_SORT
    if sort_key == "relevance":
        return list(rows)

    meta_by_kind = {
        k: _metadata_by_id(conn, sql, [r[1] for r in rows if r[0] == k])
        for k, sql in {
            "formula": "SELECT id, name, topic, difficulty FROM formula WHERE id IN ({})",
            "quantity": "SELECT id, name, topic, difficulty FROM quantity WHERE id IN ({})",
            "unit": (
                "SELECT u.id, u.name, u.quantity_id, q.name AS quantity_name, "
                "q.topic AS quantity_topic, q.difficulty AS quantity_difficulty "
                "FROM unit u LEFT JOIN quantity q ON q.id = u.quantity_id WHERE u.id IN ({})"
            ),
            "constant": (
                "SELECT c.id, c.name, c.difficulty, q.topic AS quantity_topic "
                "FROM constant c LEFT JOIN quantity q ON q.id = c.quantity_id WHERE c.id IN ({})"
            ),
        }.items()
    }

    qty_const_tokens = fetch_formula_quantity_constant_tokens(conn)
    tree_order = topic_tree_order() if sort_key == "topic_tree" else {}

    def _metadata_for(kind, ent_id):
        meta = meta_by_kind[kind].get(ent_id) or {}
        difficulty = meta.get("difficulty") or meta.get("quantity_difficulty") or 0
        topic = meta.get("topic") or meta.get("quantity_topic") or ""
        return difficulty, topic

    def search_row_sort_key(row):
        kind, ent_id, display_name = row[0], row[1], row[2]
        if sort_key == "id":
            return (kind, ent_id)
        if sort_key == "name":
            return ((display_name or ent_id).lower(), kind, ent_id)
        if sort_key in ("diff_asc", "diff_desc", "topic_tree", "topic_alpha"):
            difficulty, topic = _metadata_for(kind, ent_id)
            if sort_key == "diff_asc":
                return (difficulty, kind, ent_id)
            if sort_key == "diff_desc":
                return (-difficulty, kind, ent_id)
            if sort_key == "topic_tree":
                return (tree_order.get(topic, UNKNOWN_TREE_SORT_KEY), topic, kind, ent_id)
            return (topic, kind, ent_id)
        if sort_key == "qty":
            if kind == "formula":
                tokens = [
                    f"{position:06d} {token_kind} {ident}"
                    for position, token_kind, ident in qty_const_tokens.get(ent_id, [])
                ]
                return (tokens, kind, ent_id)
            if kind == "quantity":
                return ([f"quantity {ent_id}"], kind, ent_id)
            if kind == "unit":
                meta = meta_by_kind["unit"].get(ent_id)
                qid = meta["quantity_id"] if meta else None
                return ([f"quantity {qid}"] if qid else [], kind, ent_id)
            return ([], kind, ent_id)
        return (kind, ent_id)

    return sorted(rows, key=search_row_sort_key)


def sort_quantities_base_first(quantity_rows):
    """Sort quantities: base dimensions first, rest by id."""
    base_order = {qid: i for i, qid in enumerate(_BASE_DIMENSION_QTY_IDS.values())}
    def dimension_sort_key(quantity):
        base_index = base_order.get(quantity["id"], len(base_order))
        return (0 if base_index < len(base_order) else 1, base_index, quantity["id"])
    return sorted(quantity_rows, key=dimension_sort_key)