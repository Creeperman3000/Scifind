"""Shared library for Scifind.

Database access, LaTeX rendering, dimension formatting, default unit parsing,
and CSV/XLSX/ODS export.
"""

import csv
import html
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from fractions import Fraction
from io import StringIO
from pathlib import Path
from typing import Optional


DEFAULT_DATABASE_PATH = str(Path(__file__).resolve().parent / "scifind.db")

# Base dimension order is fixed; matches the dim_* columns on the `quantity` table.
_BASE_DIMENSION_ORDER = ("M", "L", "T", "I", "Θ", "N", "J")
_BASE_DIMENSION_QTY_IDS = {
    "M": "mass",
    "L": "length",
    "T": "time",
    "I": "current",
    "Θ": "temperature",
    "N": "amount",
    "J": "luminous_intensity",
}


def DIMENSION_SYMBOLS():
    return list(_BASE_DIMENSION_ORDER)


def DIMENSION_COLUMNS():
    return [f"dim_{s}" for s in _BASE_DIMENSION_ORDER]


def fetch_dimensions(conn):
    """Return dimension rows: one per base dimension, in the canonical order."""
    qid_rows = conn.execute(
        f"SELECT id, name, json_extract(name, '$.en-us') AS name_en "
        f"FROM quantity WHERE id IN ({','.join('?' * len(_BASE_DIMENSION_QTY_IDS))})",
        tuple(_BASE_DIMENSION_QTY_IDS.values()),
    ).fetchall()
    by_id = {r["id"]: r for r in qid_rows}
    return [
        {
            "symbol_overwrite": symbol,
            "quantity_id": qid,
            "quantity_name": by_id[qid]["name"],
            "name_en": by_id[qid]["name_en"],
        }
        for symbol, qid in _BASE_DIMENSION_QTY_IDS.items()
        if qid in by_id
    ]


def dimension_quantity_ids():
    return dict(_BASE_DIMENSION_QTY_IDS)


def _base_dimension_order():
    return {qid: i for i, qid in enumerate(_BASE_DIMENSION_QTY_IDS.values())}


# ---------------------------------------------------------------------------
# Locale helpers
# ---------------------------------------------------------------------------

_LOCALE_DIR = Path(__file__).resolve().parent / "locales"
_locale_configs = {}


def _load_locale_config(locale):
    if locale not in _locale_configs:
        path = _LOCALE_DIR / f"{locale}.json"
        try:
            with open(path, encoding="utf-8") as f:
                _locale_configs[locale] = json.load(f).get("meta", {})
        except (OSError, ValueError):
            _locale_configs[locale] = {}
    return _locale_configs[locale]


def localise(value, locale, default="en-us"):
    """Resolve a JSON i18n string, dict, or plain text to the active locale."""
    if not value:
        return ""
    if isinstance(value, dict):
        return value.get(locale) or value.get(default) or ""
    s = value.strip()
    if not s.startswith("{"):
        return s
    try:
        d = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        d = None
    if isinstance(d, dict):
        return d.get(locale) or d.get(default) or s
    # Malformed JSON (e.g. LaTeX backslashes like \_, \lambda) — recover
    # the first value by stripping the "key": "..." envelope.
    if d is None and s.endswith("}"):
        _, _, raw = s[s.find("{") + 1 : s.rfind("}")].partition(":")
        raw = raw.strip()
        if raw.startswith('"') and raw.endswith('"'):
            return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return s


def localise_english(value):
    return localise(value, "en-us")


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def database_path():
    return os.environ.get("SCIFIND_DB", DEFAULT_DATABASE_PATH)


def open_database():
    path = database_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


# ---------------------------------------------------------------------------
# Name + symbol search & autocomplete
# ---------------------------------------------------------------------------

def search_headings(conn, query, limit=30):
    """Search entity names, symbols, and IDs via SQL LIKE substring match."""
    if not query or not query.strip():
        return []
    q = query.strip().lower()
    pat = f"%{q}%"
    rows = conn.execute("""
        SELECT * FROM (
            SELECT id, 'formula' AS kind,
                   COALESCE(
                       CASE WHEN LOWER(json_extract(name, '$.cs-cz')) LIKE ? THEN json_extract(name, '$.cs-cz') END,
                       CASE WHEN LOWER(json_extract(name, '$.en-us')) LIKE ? THEN json_extract(name, '$.en-us') END,
                       json_extract(name, '$.en-us')
                   ) AS display_name
            FROM formula
            WHERE LOWER(json_extract(name, '$.cs-cz')) LIKE ?
               OR LOWER(json_extract(name, '$.en-us')) LIKE ?
               OR LOWER(id) LIKE ?
            UNION ALL
            SELECT id, 'quantity' AS kind,
                   COALESCE(
                       CASE WHEN LOWER(json_extract(name, '$.cs-cz')) LIKE ? THEN json_extract(name, '$.cs-cz') END,
                       CASE WHEN LOWER(json_extract(name, '$.en-us')) LIKE ? THEN json_extract(name, '$.en-us') END,
                       json_extract(name, '$.en-us')
                   ) AS display_name
            FROM quantity
            WHERE LOWER(json_extract(name, '$.cs-cz')) LIKE ?
               OR LOWER(json_extract(name, '$.en-us')) LIKE ?
               OR LOWER(symbol) LIKE ?
               OR LOWER(id) LIKE ?
            UNION ALL
            SELECT id, 'unit' AS kind,
                   COALESCE(
                       CASE WHEN LOWER(json_extract(name, '$.cs-cz')) LIKE ? THEN json_extract(name, '$.cs-cz') END,
                       CASE WHEN LOWER(json_extract(name, '$.en-us')) LIKE ? THEN json_extract(name, '$.en-us') END,
                       json_extract(name, '$.en-us')
                   ) AS display_name
            FROM unit
            WHERE LOWER(json_extract(name, '$.cs-cz')) LIKE ?
               OR LOWER(json_extract(name, '$.en-us')) LIKE ?
               OR LOWER(symbol) LIKE ?
               OR LOWER(id) LIKE ?
        ) ORDER BY CASE WHEN LOWER(display_name) = LOWER(?) THEN 0 ELSE 1 END, LENGTH(display_name)
    """, (pat,) * 17 + (q,)).fetchall()
    return [(r["kind"], r["id"], r["display_name"]) for r in rows]


def suggest_headings(conn, query, limit=8):
    """Prefix-matched autocomplete suggestions (same data as search_headings)."""
    return [(100, kind_id, kind, name) for kind, kind_id, name
            in search_headings(conn, query, limit=limit)]


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------

def format_number(n):
    if n == int(n):
        return str(int(n))
    return f"{n:.10f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

def format_dimensions_plain(*values):
    """Render dimension exponents as a human-readable string like M·L²·T⁻¹."""
    parts = []
    for symbol, exponent in zip(DIMENSION_SYMBOLS(), values):
        exponent = exponent or 0
        if exponent == 0:
            continue
        parts.append(symbol if exponent == 1
                     else f"{symbol}^{format_number(exponent)}")
    return " · ".join(parts) if parts else "dimensionless"


def format_dimensions_latex(
    *values, variable_symbols=None, unit_symbols=None,
    dimension_symbols=None, mode="var",
):
    """Render dimension exponents as LaTeX.

    mode: "dim", "var" (default), or "unit" — selects which symbol map to use.
    """
    lookup = {
        "dim": dimension_symbols,
        "var": variable_symbols,
        "unit": unit_symbols,
    }.get(mode) or {}
    parts = []
    for symbol, exponent in zip(DIMENSION_SYMBOLS(), values):
        if not exponent:
            continue
        sym = lookup.get(symbol, symbol)
        if exponent == 1:
            parts.append(sym)
        else:
            e = str(int(exponent)) if exponent == int(exponent) else str(exponent)
            parts.append(f"{sym}^{{{e}}}")
    return " \\cdot ".join(parts) if parts else "\\text{dimensionless}"


def extract_dimensions_from_row(row):
    return [row[c] for c in DIMENSION_COLUMNS()]


def _dimension_matches(row_dimensions, dimension_filter, dim_mode="and"):
    syms = DIMENSION_SYMBOLS()
    cols = DIMENSION_COLUMNS()
    sym_to_col = dict(zip(syms, cols))
    active = [(s, df) for s, df in dimension_filter.items() if df["val"] is not None]
    if not active:
        return True
    def _get(row, key):
        v = row.get(key)
        return v if v is not None else 0
    op_map = {"eq": (lambda a, v: a == v),
              "geq": (lambda a, v: a >= v),
              "leq": (lambda a, v: a <= v)}
    if dim_mode == "or":
        return any(op_map[df["op"]](_get(row_dimensions, sym_to_col[s]), df["val"])
                   for s, df in active)
    return all(op_map[df["op"]](_get(row_dimensions, sym_to_col[s]), df["val"])
               for s, df in active)


# ---------------------------------------------------------------------------
# Default unit
# ---------------------------------------------------------------------------

def parse_default_unit(json_text):
    """Parse default_unit JSON and return [(unit_id, exponent)]."""
    if not json_text:
        return []
    try:
        return [(p["unit"], p["exponent"]) for p in json.loads(json_text)]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def split_numerator_denominator(parts):
    return ([(u, e) for u, e in parts if e >= 0],
            [(u, -e) for u, e in parts if e < 0])


def format_default_unit_html(
    json_text, unit_url=None, unit_name=None, locale="en-us", unit_quantity_map=None,
):
    """Render default_unit JSON as HTML with optional unit links."""
    parts = parse_default_unit(json_text)
    if not parts:
        return ""
    words = locale_words(locale)
    numerators, denominators = split_numerator_denominator(parts)
    num_html = render_unit_group(numerators, unit_url, unit_name, locale)
    if not denominators:
        return num_html
    per_word = words["per"]
    use_special = False
    if unit_quantity_map:
        special = locale_quantities_special(locale)
        for uid, _ in denominators:
            if unit_quantity_map.get(uid) in special:
                per_word = words.get("perSpecial", per_word)
                use_special = True
                break
    den_html = render_unit_group(denominators, unit_url, unit_name, locale,
                                 use_special_exponents=use_special)
    if not num_html:
        return f"{words['reciprocal']} {den_html}"
    return f"{num_html} {per_word} {den_html}"


def format_default_unit_symbol(json_text, unit_symbol=None):
    """Render default_unit JSON as a LaTeX symbol expression."""
    parts = parse_default_unit(json_text)
    if not parts:
        return ""
    numerators, denominators = split_numerator_denominator(parts)

    def render(items):
        if not items:
            return ""
        out = []
        for unit_id, exponent in items:
            sym = unit_symbol(unit_id) if unit_symbol else unit_id
            out.append(sym if exponent == 1 else f"{sym}^{{{int(exponent)}}}")
        return " \\cdot ".join(out)

    num_str = render(numerators)
    den_str = render(denominators)
    if not den_str:
        return num_str
    if not num_str:
        return f"1 / ({den_str})" if len(denominators) > 1 else f"1 / {den_str}"
    return f"{num_str} / ({den_str})" if len(denominators) > 1 else f"{num_str} / {den_str}"


def render_unit_group(parts, url_func, name_func=None, locale="en-us", use_special_exponents=False):
    """Render [(unit_id, exponent)] as HTML with natural-language exponents."""
    accusative = locale_accusative_names(locale) if use_special_exponents else {}
    items = []
    for i, (unit_id, exponent) in enumerate(parts):
        label = name_func(unit_id) if name_func else unit_id.replace("_", " ").title()
        if use_special_exponents and label.lower() in accusative:
            label = accusative[label.lower()]
        if i > 0 and label:
            label = label[0].lower() + label[1:]
        word = exponent_word(exponent, locale, denominator=use_special_exponents)
        text = (f'<a href="{html.escape(url_func(unit_id))}">{html.escape(label)}</a>'
                if url_func else html.escape(label))
        if word:
            text += " " + html.escape(word)
        items.append(text)
    return "-".join(items)


# ---------------------------------------------------------------------------
# Locale words and ordinals
# ---------------------------------------------------------------------------

def locale_words(locale):
    config = _load_locale_config(locale)
    return config.get("unitWords", _load_locale_config("en-us").get("unitWords", {}))


def locale_quantities_special(locale):
    return _load_locale_config(locale).get("quantitiesSpecial", [])


def locale_accusative_names(locale):
    return _load_locale_config(locale).get("accusativeNames", {})


def locale_sibilants(locale):
    return _load_locale_config(locale).get("sibilants",
                                           {"chars": [], "preposition": {"suffix": ""}})


def _ordinal(n, locale="en-us"):
    suffix = _load_locale_config(locale).get("ordinalSuffix", "th")
    return f"{n}." if suffix == "." else f"{n}{suffix}"


def exponent_word(exp, locale="en-us", denominator=False):
    """Return the natural-language word for a unit exponent."""
    words = locale_words(locale)
    if exp == 1:
        return ""
    if exp == -1:
        return words.get("inverse", "inverse")
    if exp == 2:
        return words.get("squaredSpecial" if denominator else "squared", "squared")
    if exp == 3:
        return words.get("cubedSpecial" if denominator else "cubed", "cubed")
    if exp > 3:
        return f"{words.get('toThe', 'to the')} {_ordinal(exp, locale)}"
    return ""


def difficulty_to_stars(difficulty, max_dots=5):
    """Render a difficulty (1-10) as a string of filled + empty stars."""
    filled = min(int(difficulty or 0), max_dots)
    return "★" * filled + "☆" * (max_dots - filled)


# ---------------------------------------------------------------------------
# LaTeX rendering
# ---------------------------------------------------------------------------

def render_symbol(symbol):
    if not symbol:
        return ""
    s = symbol.strip()
    if not s or "\\" in s:
        return s
    return re.sub(r"[A-Za-z]+", lambda m: f"\\mathrm{{{m.group(0)}}}", s.replace("_", "\\_"))


def render_formula(conn, formula_id, locale="en-us"):
    """Render a formula (by id) as a LaTeX string.

    Reads ordered formula_token rows for the formula, evaluates them onto a
    stack to build an expression tree, then renders the tree as LaTeX with
    the minimum required parentheses.
    """
    tokens = conn.execute(
        "SELECT * FROM formula_token WHERE formula_id = ? ORDER BY position",
        (formula_id,),
    ).fetchall()
    if not tokens:
        return ""
    tree = _evaluate_rpn(conn, [dict(t) for t in tokens])
    if tree is None:
        return ""
    return _latex_node(tree, conn, locale)


# --- RPN evaluator and LaTeX renderer ---------------------------------------


@dataclass
class _Node:
    kind: str  # "quantity" | "constant" | "number" | "operator"
    children: list["_Node"] = field(default_factory=list)
    # operand metadata
    quantity_id: Optional[str] = None
    constant_id: Optional[str] = None
    value: Optional[float] = None
    label: Optional[str] = None
    symbol_overwrite: Optional[str] = None
    # operator metadata
    operator_id: Optional[str] = None
    symbol: Optional[str] = None
    arity: int = 0
    precedence: int = 0
    associativity: str = "left"
    operator_type: str = "infix"


def _fetch(conn, table: str, columns: str, key: str) -> dict:
    row = conn.execute(
        f"SELECT {columns} FROM {table} WHERE id = ?", (key,)
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown {table.rstrip('s')}: {key!r}")
    return dict(row)


def _load_operator(conn, operator_id: str) -> dict:
    return _fetch(conn, "operator",
                  "id, symbol, arity, precedence, associativity, operator_type",
                  operator_id)


def _load_constant(conn, constant_id: str) -> dict:
    return _fetch(conn, "constant",
                  "id, name, symbol, value, default_unit",
                  constant_id)


def _load_quantity(conn, quantity_id: str) -> dict:
    return _fetch(conn, "quantity",
                  "id, name, symbol, symbol_overwrite, default_unit",
                  quantity_id)


def _evaluate_rpn(conn, tokens: list[dict]) -> Optional[_Node]:
    stack: list[_Node] = []
    for t in tokens:
        kind = t["token_kind"]
        if kind == "operator":
            op = _load_operator(conn, t["operator_id"])
            if len(stack) < op["arity"]:
                raise ValueError(
                    f"RPN underflow at {t['operator_id']}: need {op['arity']}, have {len(stack)}"
                )
            args = [stack.pop() for _ in range(op["arity"])][::-1]
            stack.append(_Node(
                kind="operator",
                children=args,
                operator_id=op["id"],
                symbol=op["symbol"],
                arity=op["arity"],
                precedence=op["precedence"],
                associativity=op["associativity"],
                operator_type=op["operator_type"],
            ))
        elif kind == "quantity":
            stack.append(_Node(
                kind="quantity",
                quantity_id=t["quantity_id"],
                label=t["label"],
                symbol_overwrite=t["symbol_overwrite"],
            ))
        elif kind == "constant":
            stack.append(_Node(kind="constant", constant_id=t["constant_id"]))
        elif kind == "number":
            stack.append(_Node(kind="number", value=t["value"]))
        else:
            raise ValueError(f"unknown token kind: {kind!r}")
    if not stack:
        return None
    if len(stack) > 1:
        raise ValueError(f"RPN did not reduce: {len(stack)} items left on stack")
    return stack[0]


def _latex_quantity(node: _Node, conn, locale: str) -> str:
    if not node.quantity_id:
        return "?"
    q = _load_quantity(conn, node.quantity_id)
    var = localise(node.symbol_overwrite or "", locale) or q["symbol"] or node.quantity_id
    label = localise(node.label or "", locale)
    if label and "_" not in var:
        var += "_{" + label + "}"
    return var


def _latex_constant(node: _Node, conn) -> str:
    c = _load_constant(conn, node.constant_id)
    return c["symbol"] or c["id"]


def _latex_number(node: _Node) -> str:
    if node.value is None:
        return "?"
    v = node.value
    if v < 0:
        return "-" + _latex_number(_Node(kind="number", value=-v))
    if v == int(v):
        return str(int(v))
    try:
        f = Fraction(v).limit_denominator(100)
    except (ValueError, ZeroDivisionError):
        return format_number(v)
    if f.denominator != 1 and f.numerator == 1 and f.denominator < 20:
        return "\\frac{1}{" + str(f.denominator) + "}"
    return format_number(v)


def _needs_paren(child: _Node, parent: _Node, side: str) -> bool:
    if child.kind != "operator":
        return False
    if child.operator_type == "relational":
        return True
    if child.precedence < parent.precedence:
        return True
    if child.precedence == parent.precedence:
        if parent.associativity == "none":
            return True
        if parent.associativity == "left" and side == "right":
            return True
        if parent.associativity == "right" and side == "left":
            return True
    return False


def _wrap(child_str: str, child: _Node, parent: _Node, side: str) -> str:
    if _needs_paren(child, parent, side):
        return "\\left(" + child_str + "\\right)"
    return child_str


def _render_binary(node: _Node, conn, locale: str) -> tuple[str, str]:
    if node.arity != 2:
        raise ValueError(f"{node.operator_type} op {node.operator_id} arity {node.arity}")
    left, right = node.children
    l = _latex_node(left, conn, locale)
    r = _latex_node(right, conn, locale)
    l = _wrap(l, left, node, "left")
    r = _wrap(r, right, node, "right")
    return l, r


def _latex_infix(node: _Node, conn, locale: str) -> str:
    left, right = node.children
    if node.operator_id == "frac":
        return f"\\frac{{{_latex_node(left, conn, locale)}}}{{{_latex_node(right, conn, locale)}}}"
    l, r = _render_binary(node, conn, locale)
    if node.operator_id == "pow":
        return f"{l}^{{{r}}}"
    if node.symbol:
        return f"{l} {node.symbol} {r}"
    if left.kind == "number" and right.kind == "number":
        return f"{l} \\cdot {r}"
    if left.kind == "number" or right.kind == "number":
        return f"{l}{r}"
    return f"{l} {r}"


def _latex_prefix(node: _Node, conn, locale: str) -> str:
    a = _latex_node(node.children[0], conn, locale)
    a = _wrap(a, node.children[0], node, "child")
    sym = node.symbol or ""
    if sym == "-":
        return f"-{a}"
    return f"{sym} {a}"


def _latex_postfix(node: _Node, conn, locale: str) -> str:
    a = _latex_node(node.children[0], conn, locale)
    a = _wrap(a, node.children[0], node, "child")
    return f"{a}{node.symbol or ''}"


def _latex_relational(node: _Node, conn, locale: str) -> str:
    l, r = _render_binary(node, conn, locale)
    return f"{l} {node.symbol} {r}"


def _latex_node(node: _Node, conn, locale: str = "en-us") -> str:
    if node.kind == "quantity":
        return _latex_quantity(node, conn, locale)
    if node.kind == "constant":
        return _latex_constant(node, conn)
    if node.kind == "number":
        return _latex_number(node)
    if node.kind == "operator":
        return {
            "infix": _latex_infix,
            "prefix": _latex_prefix,
            "postfix": _latex_postfix,
            "relational": _latex_relational,
        }[node.operator_type](node, conn, locale)
    raise ValueError(f"cannot render node: {node!r}")


# ---------------------------------------------------------------------------
# Common queries
# ---------------------------------------------------------------------------

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
    """Return all formula_token rows for a formula, joined with quantity metadata."""
    return conn.execute(
        """
        SELECT ft.*, q.symbol AS quantity_symbol, q.default_unit,
               json_extract(q.name, '$.en-us') AS quantity_name
        FROM formula_token ft
        LEFT JOIN quantity q ON q.id = ft.quantity_id
        WHERE ft.formula_id = ?
        ORDER BY ft.position
        """,
        (formula_id,),
    ).fetchall()


def render_variable_base(item, locale="en-us"):
    """Render the base variable symbol (without exponent) for display tables.

    Works with formula_token rows. Prefix operators (e.g. \\Delta, \\sin) are
    not applied here — this is the base symbol for the detail table.
    """
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
               {', '.join(f'q.{c}' for c in DIMENSION_COLUMNS())}
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


def fetch_quantities_by_ids(conn, quantity_ids):
    """Return {id: name_json} for the given quantity ids in one query."""
    if not quantity_ids:
        return {}
    placeholders = ",".join("?" for _ in quantity_ids)
    rows = conn.execute(
        f"SELECT id, name FROM quantity WHERE id IN ({placeholders})",
        tuple(quantity_ids),
    ).fetchall()
    return {r["id"]: r["name"] for r in rows}


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

    Primary: the quantity appears on the LHS of the formula (i.e. before
    the first `=` operator in the RPN token stream).
    """
    primary = conn.execute(
        """
        SELECT DISTINCT f.id, f.name,
               json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty
        FROM formula_token ft
        JOIN formula f ON f.id = ft.formula_id
        WHERE ft.quantity_id = ?
          AND ft.token_kind = 'quantity'
          AND ft.position < COALESCE(
            (SELECT MIN(position) FROM formula_token
             WHERE formula_id = ft.formula_id AND operator_id = 'eq'),
            99999
          )
        ORDER BY f.topic, f.difficulty, f.id
        """,
        (quantity_id,),
    ).fetchall()
    non_primary = conn.execute(
        """
        SELECT DISTINCT f.id, f.name,
               json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty
        FROM formula_token ft
        JOIN formula f ON f.id = ft.formula_id
        WHERE ft.quantity_id = ?
          AND f.id NOT IN (
            SELECT ft2.formula_id FROM formula_token ft2
            WHERE ft2.quantity_id = ?
              AND ft2.token_kind = 'quantity'
              AND ft2.position < COALESCE(
                (SELECT MIN(position) FROM formula_token
                 WHERE formula_id = ft2.formula_id AND operator_id = 'eq'),
                99999
              )
          )
        ORDER BY f.topic, f.difficulty, f.id
        """,
        (quantity_id, quantity_id),
    ).fetchall()
    return primary, non_primary


def compute_formula_dimensions(conn, formula_id):
    """Compute dimensions from the LHS of a formula.

    The LHS is identified by walking the RPN tree and taking the first
    operand of the topmost `=` operator. We then sum the dimensional
    exponents of all quantities in that subtree.
    """
    tokens = conn.execute(
        "SELECT * FROM formula_token WHERE formula_id = ? ORDER BY position",
        (formula_id,),
    ).fetchall()
    if not tokens:
        return []
    try:
        tree = _evaluate_rpn(conn, [dict(t) for t in tokens])
    except Exception:
        return []
    if tree is None:
        return []

    def find_lhs(node):
        if node.kind == "operator" and node.operator_type == "relational":
            return find_lhs(node.children[0])
        return node

    cols = DIMENSION_COLUMNS()
    qid_to_dims = {
        r["id"]: [r[c] for c in cols]
        for r in conn.execute(
            f"SELECT id, {', '.join(cols)} FROM quantity"
        ).fetchall()
    }
    dims = [0.0] * len(cols)

    def walk(node, sign):
        if node.kind != "operator":
            if node.kind == "quantity":
                for i, v in enumerate(qid_to_dims.get(node.quantity_id, [])):
                    dims[i] += v * sign
            return
        op = node.operator_id
        if op in ("div", "frac"):
            walk(node.children[0], sign)
            walk(node.children[1], -sign)
        elif op == "pow":
            base, exp = node.children
            scale = exp.value if exp.kind == "number" and exp.value is not None else 1
            walk(base, sign * scale)
        elif op in ("add", "sub"):
            # Addition/subtraction doesn't change dimensions — all
            # operands must have the same dimension. Walk only one.
            walk(node.children[0], sign)
        elif op in ("sin", "cos", "tan"):
            # Transcendental functions produce dimensionless results.
            pass
        elif op == "sqrt":
            before = list(dims)
            walk(node.children[0], sign)
            for i in range(len(dims)):
                dims[i] = before[i] + (dims[i] - before[i]) * 0.5
        else:
            for c in node.children:
                walk(c, sign)

    walk(find_lhs(tree), 1)
    return [int(round(d)) for d in dims]


def fetch_si_unit_symbol(conn, quantity_id):
    row = conn.execute(
        "SELECT symbol FROM unit WHERE quantity_id = ? AND default_unit = 1 LIMIT 1",
        (quantity_id,),
    ).fetchone()
    return row["symbol"] if row else ""


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


def _unit_name_map(db, locale):
    return {r["id"]: localise(r["name"], locale)
            for r in db.execute("SELECT id, name FROM unit").fetchall()}


def _unit_quantity_map(db):
    return {r["id"]: r["quantity_id"]
            for r in db.execute("SELECT id, quantity_id FROM unit").fetchall()}


def _unit_symbol_map(db):
    return {r["id"]: r["symbol"]
            for r in db.execute("SELECT id, symbol FROM unit").fetchall()}


def build_dimension_symbol_maps(conn):
    """Return (variable_map, unit_map, dim_map) for dimension display."""
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


def sort_quantities_by_dimension(quantity_rows):
    """Sort quantities: base dimensions first, rest by id."""
    base_order = _base_dimension_order()
    def key(quantity):
        base_index = base_order.get(quantity["id"], 99)
        return (0 if base_index < 99 else 1, base_index, quantity["id"])
    return sorted(quantity_rows, key=key)


def fetch_all_quantities(conn):
    """Return all quantities with default_unit parsed and dimensions."""
    rows = conn.execute(
        f"""
        SELECT q.id, q.name, q.symbol,
               json_extract(q.name, '$.en-us') AS name_en,
               q.topic AS topic_id, q.difficulty, q.default_unit,
               {', '.join(f'q.{c}' for c in DIMENSION_COLUMNS())}
        FROM quantity q
        ORDER BY q.id
        """
    ).fetchall()
    return sort_quantities_by_dimension(rows)


def fetch_all_formulas(conn):
    return conn.execute(
        """
        SELECT f.id, f.name, json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty
        FROM formula f
        ORDER BY f.topic, f.difficulty, f.id
        """
    ).fetchall()


def compute_all_formula_dimensions(conn):
    """Return {formula_id: {dim_M, dim_L, ...}} for all formulas.

    Evaluates the RPN tree for each formula to correctly compute
    LHS dimensions (handles frac, pow, etc.). Formulas without a
    valid LHS or with no tokens get all-zero dimensions.
    """
    cols = DIMENSION_COLUMNS()
    all_ids = {r["id"] for r in conn.execute("SELECT id FROM formula").fetchall()}
    zero_row = {c: 0 for c in cols}
    result = {}
    for fid in all_ids:
        dims = compute_formula_dimensions(conn, fid)
        if dims:
            result[fid] = dict(zip(cols, dims))
        else:
            result[fid] = dict(zero_row)
    return result


def fetch_formulas_with_any_quantity(conn, quantity_ids):
    """Return formula_ids that reference ANY of the given quantity IDs (OR)."""
    if not quantity_ids:
        return None
    placeholders = ",".join("?" for _ in quantity_ids)
    rows = conn.execute(
        f"SELECT DISTINCT formula_id FROM formula_token "
        f"WHERE token_kind = 'quantity' AND quantity_id IN ({placeholders})",
        quantity_ids,
    ).fetchall()
    return {r["formula_id"] for r in rows}


def fetch_formulas_with_all_quantities(conn, quantity_ids):
    """Return formula_ids that reference ALL of the given quantity IDs (AND)."""
    if not quantity_ids:
        return None
    placeholders = ",".join("?" for _ in quantity_ids)
    rows = conn.execute(
        f"SELECT formula_id, COUNT(DISTINCT quantity_id) AS match_count "
        f"FROM formula_token "
        f"WHERE token_kind = 'quantity' AND quantity_id IN ({placeholders}) "
        f"GROUP BY formula_id HAVING match_count = ?",
        quantity_ids + [len(quantity_ids)],
    ).fetchall()
    return {r["formula_id"] for r in rows}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

EXPORT_TABLE_ORDER = [
    "formula", "formula_token", "formula_relation",
    "operator", "constant", "quantity", "unit",
]

EXPORT_TABLE_COLUMNS = {
    "formula": ["id", "name", "topic", "difficulty", "description", "links"],
    "formula_token": [
        "formula_id", "position", "token_kind",
        "quantity_id", "constant_id", "operator_id",
        "value", "label", "symbol_overwrite", "quantity_name_overwrite",
    ],
    "formula_relation": ["formula_id", "related_id", "relation_type", "description"],
    "operator": ["id", "symbol", "math", "arity", "precedence", "associativity", "operator_type"],
    "constant": ["id", "name", "symbol", "value", "default_unit"],
    "quantity": [
        "id", "name", "symbol", "symbol_overwrite", "topic",
        "difficulty", "description", "links", "default_unit",
    ],
    "unit": [
        "id", "name", "symbol", "quantity_id", "default_unit", "unit_system",
        "factor", "latex_factor", "offset",
    ],
}


def _each_table(conn):
    """Yield (table_name, columns, rows) for all tables in export order."""
    for table in EXPORT_TABLE_ORDER:
        columns = list(EXPORT_TABLE_COLUMNS[table])
        if table == "quantity":
            # Insert dim_* columns after default_unit (index 8).
            columns[9:9] = DIMENSION_COLUMNS()
        rows = conn.execute(
            f"SELECT {','.join(columns)} FROM {table} ORDER BY rowid"
        ).fetchall()
        yield table, columns, [[r[c] for c in columns] for r in rows]


def export_to_csv(conn):
    """Export all tables to a single CSV string with section headers."""
    buffer = StringIO()
    for table, columns, rows in _each_table(conn):
        buffer.write(f"=== {table} ===\n")
        writer = csv.writer(buffer)
        writer.writerow(columns)
        writer.writerows(rows)
        buffer.write("\n")
    return buffer.getvalue()


def export_to_csv_directory(conn, directory):
    """Export each table to a separate CSV file in a directory."""
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    for table, columns, rows in _each_table(conn):
        with open(out_dir / f"{table}.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)


def export_to_xlsx(conn, output):
    """Export all tables as sheets in an XLSX workbook (file path or file-like)."""
    from openpyxl import Workbook
    workbook = Workbook()
    first = True
    for table, columns, rows in _each_table(conn):
        if first:
            sheet = workbook.active
            sheet.title = table[:31]
            first = False
        else:
            sheet = workbook.create_sheet(title=table[:31])
        sheet.append(columns)
        for row in rows:
            sheet.append(row)
    workbook.save(output)


def export_to_ods(conn, output):
    """Export all tables as sheets in an ODS spreadsheet (file path or file-like)."""
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableRow, TableCell
    from odf.text import P
    document = OpenDocumentSpreadsheet()
    for table, columns, rows in _each_table(conn):
        sheet = Table(name=table[:31])
        document.spreadsheet.addElement(sheet)
        for row_data in [columns] + rows:
            row = TableRow()
            for value in row_data:
                cell = TableCell()
                cell.addElement(P(text=str(value) if value is not None else ""))
                row.addElement(cell)
            sheet.addElement(row)
    document.save(output)
