"""Substring search across formula / quantity / unit names + symbols."""
# Licensed under the LICENSE file in the project root.

from scifind_lib.constants import is_hidden_quantity
from scifind_lib.i18n import localise


DEFAULT_LOCALE = "en-us"


def search_headings(conn, query, limit=30, locale=DEFAULT_LOCALE):
    """Search entity names, symbols, and IDs via SQL LIKE substring match.

    Names match in every stored language so an entry is findable by any
    of its translations, while the returned display name follows the
    active `locale` (same resolution as everywhere else in the app).
    Drop and dimensionless quantities are filtered out so they never
    appear in the results.
    """
    if not query or not query.strip():
        return []
    q = query.strip().lower()
    pat = f"%{q}%"
    sources = (
        ("formula",   "formula",   None),
        ("quantity",  "quantity",  "symbol"),
        ("unit",      "unit",      "symbol"),
        ("constant",  "constant",  "symbol"),
    )
    union_parts = []
    params = []
    for table, kind, extra in sources:
        where = [
            "LOWER(json_extract(name, '$.cs-cz')) LIKE ?",
            "LOWER(json_extract(name, '$.en-us')) LIKE ?",
            "LOWER(id) LIKE ?",
        ]
        table_params = [pat] * len(where)
        if extra:
            where.append(f"LOWER({extra}) LIKE ?")
            table_params.append(pat)
        # Hidden quantities (see is_hidden_quantity) are dropped in
        # Python below rather than in SQL.
        union_parts.append(
            f"SELECT id, '{kind}' AS kind, name AS raw_name "
            f"FROM {table} WHERE {' OR '.join(where)}"
        )
        params.extend(table_params)
    sql = f"SELECT * FROM ({' UNION ALL '.join(union_parts)})"
    rows = conn.execute(sql, params).fetchall()

    out = []
    seen = set()
    for r in rows:
        if r["kind"] == "quantity" and is_hidden_quantity(r["id"]):
            continue
        key = (r["kind"], r["id"])
        if key in seen:
            continue
        seen.add(key)
        display = localise(r["raw_name"], locale)
        out.append((r["kind"], r["id"], display))
    # Exact display-name match first, then shorter names (mirrors the
    # previous in-SQL ordering).
    out.sort(key=lambda hit: (0 if hit[2].strip().lower() == q else 1, len(hit[2])))
    if limit is not None:
        out = out[:limit]
    return out


def suggest_headings(conn, query, limit=8, locale=DEFAULT_LOCALE):
    """Prefix-matched autocomplete suggestions (same data as search_headings)."""
    return [(kind_id, kind, name) for kind, kind_id, name
            in search_headings(conn, query, limit=limit, locale=locale)]
