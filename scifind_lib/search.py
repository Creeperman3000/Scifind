"""Substring search across formula / quantity / unit names + symbols."""
# Licensed under the LICENSE file in the project root.

from scifind_lib.constants import is_hidden_quantity


_NAME_PICK_SQL = (
    "COALESCE("
    "CASE WHEN LOWER(json_extract(name, '$.cs-cz')) LIKE ? THEN json_extract(name, '$.cs-cz') END,"
    "CASE WHEN LOWER(json_extract(name, '$.en-us')) LIKE ? THEN json_extract(name, '$.en-us') END,"
    "json_extract(name, '$.en-us')"
    ")"
)


def search_headings(conn, query, limit=30):
    """Search entity names, symbols, and IDs via SQL LIKE substring match.

    Drop and dimensionless quantities are filtered out so they never
    appear in the search results.
    """
    if not query or not query.strip():
        return []
    q = query.strip().lower()
    pat = f"%{q}%"
    sources = (
        ("formula",   "formula",   None),
        ("quantity",  "quantity",  "symbol"),
        ("unit",      "unit",      "symbol"),
    )
    union_parts = []
    params = []
    for table, kind, extra in sources:
        where = [
            "LOWER(json_extract(name, '$.cs-cz')) LIKE ?",
            "LOWER(json_extract(name, '$.en-us')) LIKE ?",
            "LOWER(id) LIKE ?",
        ]
        params.extend([pat] * 5)
        if extra:
            where.append(f"LOWER({extra}) LIKE ?")
            params.append(pat)
        # Hidden quantities (see is_hidden_quantity) are dropped in
        # Python below rather than in SQL.
        union_parts.append(
            f"SELECT id, '{kind}' AS kind, {_NAME_PICK_SQL} AS display_name "
            f"FROM {table} WHERE {' OR '.join(where)}"
        )
    sql = (
        f"SELECT * FROM ({' UNION ALL '.join(union_parts)}) "
        f"ORDER BY CASE WHEN LOWER(display_name) = LOWER(?) THEN 0 ELSE 1 END, LENGTH(display_name)"
    )
    rows = conn.execute(sql, params + [q]).fetchall()
    out = []
    for r in rows:
        if r["kind"] == "quantity" and is_hidden_quantity(r["id"]):
            continue
        out.append((r["kind"], r["id"], r["display_name"]))
        if limit is not None and len(out) >= limit:
            break
    return out


def suggest_headings(conn, query, limit=8):
    """Prefix-matched autocomplete suggestions (same data as search_headings)."""
    return [(100, kind_id, kind, name) for kind, kind_id, name
            in search_headings(conn, query, limit=limit)]
