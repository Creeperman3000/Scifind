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
from collections import defaultdict
from fractions import Fraction
from io import StringIO
from pathlib import Path


DEFAULT_DATABASE_PATH = str(Path(__file__).resolve().parent / "scifind.db")

def fetch_dimensions(conn):
    """Return dimension rows from formula_item (merged dimension table)."""
    return conn.execute(
        """
        SELECT fi.*, q.id AS quantity_id, q.name AS quantity_name,
               json_extract(q.name, '$.en-us') AS name_en
        FROM formula_item fi
        JOIN quantity q ON q.id = fi.quantity_id
        WHERE fi.formula_id = 'dimensions'
        ORDER BY fi.sort_order
        """
    ).fetchall()

def DIMENSION_SYMBOLS(conn):
    return [r["symbol_overwrite"] for r in conn.execute(
        "SELECT symbol_overwrite FROM formula_item WHERE formula_id = 'dimensions' ORDER BY sort_order"
    )]

def DIMENSION_COLUMNS(conn):
    return [f"dim_{r['symbol_overwrite']}" for r in conn.execute(
        "SELECT symbol_overwrite FROM formula_item WHERE formula_id = 'dimensions' ORDER BY sort_order"
    )]


# ---------------------------------------------------------------------------
# Locale helpers
# ---------------------------------------------------------------------------

_LOCALE_DIR = Path(__file__).resolve().parent / "locales"
_locale_configs = {}


def _load_locale_config(locale):
    """Load locale metadata (unit words, ordinal format, etc.) from file."""
    if locale not in _locale_configs:
        path = _LOCALE_DIR / f"{locale}.json"
        try:
            with open(path, encoding="utf-8") as f:
                _locale_configs[locale] = json.load(f).get("meta", {})
        except (OSError, ValueError):
            _locale_configs[locale] = {}
    return _locale_configs[locale]


def localise(value, locale, default="en-us"):
    """Resolve a value that may be a JSON i18n string, a dict, or plain text.

    Returns the localised string, falling back to ``default`` and finally to
    the raw value if neither key is present.
    """
    if not value:
        return ""
    if isinstance(value, dict):
        return value.get(locale) or value.get(default) or ""
    if not isinstance(value, str):
        return str(value)
    s = value.strip()
    if s.startswith("{"):
        try:
            d = json.loads(s)
            if isinstance(d, dict):
                return d.get(locale) or d.get(default) or s
            return s
        except (json.JSONDecodeError, TypeError):
            return s
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
    """Search entity names, symbols, and IDs via SQL LIKE substring match.

    Returns a list of (kind, id, name_en).
    """
    if not query or not query.strip():
        return []
    q = query.strip().lower()
    pat = f"%{q}%"
    rows = conn.execute("""
        SELECT * FROM (
            SELECT id, 'formula' AS kind, json_extract(name, '$.en-us') AS name_en
            FROM formula WHERE LOWER(json_extract(name, '$.en-us')) LIKE ? OR LOWER(id) LIKE ?
            UNION ALL
            SELECT id, 'quantity' AS kind, json_extract(name, '$.en-us') AS name_en
            FROM quantity WHERE LOWER(json_extract(name, '$.en-us')) LIKE ? OR LOWER(symbol) LIKE ? OR LOWER(id) LIKE ?
            UNION ALL
            SELECT id, 'unit' AS kind, json_extract(name, '$.en-us') AS name_en
            FROM unit WHERE LOWER(json_extract(name, '$.en-us')) LIKE ? OR LOWER(symbol) LIKE ? OR LOWER(id) LIKE ?
        ) ORDER BY CASE WHEN LOWER(name_en) = LOWER(?) THEN 0 ELSE 1 END, LENGTH(name_en)
    """, (pat, pat, pat, pat, pat, pat, pat, pat, q)).fetchall()
    return [(r["kind"], r["id"], r["name_en"]) for r in rows]


def suggest_headings(conn, query, limit=8):
    """Prefix-matched autocomplete suggestions (same as search_headings)."""
    return [(100, r[1], r[0], r[2]) for r in search_headings(conn, query, limit=limit)]


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------

def format_number(n):
    if n == int(n):
        return str(int(n))
    s = f"{n:.10f}".rstrip("0")
    return s.rstrip(".")


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

def dimension_quantity_ids(conn):
    """Build {dim_symbol: quantity_id} from formula_item dimension rows."""
    rows = conn.execute(
        "SELECT fi.symbol_overwrite, fi.quantity_id "
        "FROM formula_item fi "
        "WHERE fi.formula_id = 'dimensions' "
        "ORDER BY fi.sort_order"
    ).fetchall()
    return {r["symbol_overwrite"]: r["quantity_id"] for r in rows}


def format_dimensions_plain(*values, conn):
    """Render dimension exponents as a human-readable string like M·L²·T⁻¹."""
    parts = []
    for symbol, exponent in zip(DIMENSION_SYMBOLS(conn), values):
        if exponent is None:
            exponent = 0
        if exponent == 0:
            continue
        part = symbol if exponent == 1 else f"{symbol}^{format_number(exponent)}"
        parts.append(part)
    return " · ".join(parts) if parts else "dimensionless"


def format_dimensions_latex(
    *values,
    conn=None, variable_symbols=None, unit_symbols=None, dimension_symbols=None, mode="var",
):
    """Render dimension exponents as LaTeX.

    variable_symbols: {dim_symbol: quantity-symbol LaTeX}
    unit_symbols:     {dim_symbol: unit-symbol LaTeX}
    dimension_symbols:{dim_symbol: dimension-symbol LaTeX}
    mode: "dim", "var" (default), or "unit"
    """
    if mode == "dim" and dimension_symbols:
        lookup = dimension_symbols
    elif mode == "var" and variable_symbols:
        lookup = variable_symbols
    else:
        lookup = unit_symbols
    parts = []
    for symbol, exponent in zip(DIMENSION_SYMBOLS(conn), values):
        if not exponent:
            continue
        sym = lookup.get(symbol) if lookup else None
        if sym is None:
            sym = symbol
        if exponent == 1:
            parts.append(sym)
        else:
            e = str(int(exponent)) if exponent == int(exponent) else str(exponent)
            parts.append(f"{sym}^{{{e}}}")
    if not parts:
        return "\\text{dimensionless}"
    return " \\cdot ".join(parts)


def extract_dimensions_from_row(row, conn):
    """Return dimension values from a row (dict or sqlite3.Row)."""
    return [dict(row).get(c, 0) or 0 for c in DIMENSION_COLUMNS(conn)]


def _dimension_matches(row_dimensions, dimension_filter, dim_mode="and", conn=None):
    syms = DIMENSION_SYMBOLS(conn)
    cols = DIMENSION_COLUMNS(conn)
    sym_to_col = dict(zip(syms, cols))
    active = [(symbol, df) for symbol, df in dimension_filter.items() if df["val"] is not None]
    if not active:
        return True
    if dim_mode == "or":
        for symbol, df in active:
            actual = row_dimensions.get(sym_to_col.get(symbol, f"dim_{symbol}")) or 0
            op = df["op"]
            value = df["val"]
            if op == "eq" and actual == value:
                return True
            if op == "geq" and actual >= value:
                return True
            if op == "leq" and actual <= value:
                return True
        return False
    for symbol, df in active:
        actual = row_dimensions.get(sym_to_col.get(symbol, f"dim_{symbol}")) or 0
        op = df["op"]
        value = df["val"]
        if op == "eq" and actual != value:
            return False
        if op == "geq" and actual < value:
            return False
        if op == "leq" and actual > value:
            return False
    return True


# ---------------------------------------------------------------------------
# Default unit
# ---------------------------------------------------------------------------

def parse_default_unit(json_text):
    """Parse default_unit JSON and return [(unit_id, exponent)]."""
    if not json_text:
        return []
    try:
        parts = json.loads(json_text)
        return [(p["unit"], p["exponent"]) for p in parts]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def split_numerator_denominator(parts):
    numerators, denominators = [], []
    for unit_id, exponent in parts:
        if exponent >= 0:
            numerators.append((unit_id, exponent))
        else:
            denominators.append((unit_id, -exponent))
    return numerators, denominators


def format_default_unit_html(
    json_text, unit_url=None, unit_name=None, locale="en-us",
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
    den_html = render_unit_group(denominators, unit_url, unit_name, locale)
    if not num_html:
        return f"{words['reciprocal']} {den_html}"
    return f"{num_html} {words['per']} {den_html}"


def format_default_unit_symbol(json_text, unit_symbol=None):
    """Render default_unit JSON as a LaTeX symbol expression."""
    parts = parse_default_unit(json_text)
    if not parts:
        return ""
    numerators, denominators = split_numerator_denominator(parts)

    def render(parts_):
        items = []
        for unit_id, exponent in parts_:
            sym = unit_symbol(unit_id) if unit_symbol else unit_id
            items.append(sym if exponent == 1 else f"{sym}^{{{int(exponent)}}}")
        return " \\cdot ".join(items) if items else ""

    num_str = render(numerators)
    den_str = render(denominators)
    if not den_str:
        return num_str
    if not num_str:
        return f"1 / ({den_str})" if len(denominators) > 1 else f"1 / {den_str}"
    return f"{num_str} / ({den_str})" if len(denominators) > 1 else f"{num_str} / {den_str}"


def render_unit_group(parts, url_func, name_func=None, locale="en-us"):
    """Render [(unit_id, exponent)] as HTML with natural-language exponents."""
    items = []
    for unit_id, exponent in parts:
        label = name_func(unit_id) if name_func else unit_id.replace("_", " ").title()
        word = exponent_word(exponent, locale)
        if url_func:
            text = f'<a href="{html.escape(url_func(unit_id))}">{html.escape(label)}</a>'
        else:
            text = html.escape(label)
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


def _ordinal(n, locale="en-us"):
    config = _load_locale_config(locale)
    suffix = config.get("ordinalSuffix", "th")
    if suffix == ".":
        return f"{n}."
    last_two = n % 100
    if last_two in (11, 12, 13):
        return f"{n}{suffix}"
    return f"{n}{suffix}"


def exponent_word(exp, locale="en-us"):
    """Return the natural-language word for a unit exponent."""
    words = locale_words(locale)
    if exp == 2:
        return words.get("squared", "squared")
    if exp == 3:
        return words.get("cubed", "cubed")
    if exp == 1:
        return ""
    if exp == -1:
        return words.get("inverse", "inverse")
    if exp > 3:
        return f"{words.get('toThe', 'to the')} {_ordinal(exp, locale)}"
    return ""


def difficulty_to_stars(difficulty, max_dots=5):
    """Render a difficulty (1-10) as a string of filled + empty stars."""
    filled = min(int(difficulty or 0), max_dots)
    return "\u2605" * filled + "\u2606" * (max_dots - filled)


# ---------------------------------------------------------------------------
# LaTeX rendering
# ---------------------------------------------------------------------------

def _render_with_exponent(exponent, base):
    """Render a base string with an exponent in LaTeX form."""
    if exponent is None or exponent == 1:
        return base

    if exponent == int(exponent):
        integer_exp = int(exponent)
        if integer_exp < 0:
            inner = base
            if integer_exp != -1:
                inner += "^{" + format_number(-integer_exp) + "}"
            return "\\frac{1}{" + inner + "}"
        return base + "^{" + format_number(integer_exp) + "}"

    try:
        fraction = Fraction(exponent).limit_denominator(100)
        num, den = fraction.numerator, fraction.denominator
    except (ValueError, ZeroDivisionError):
        return base + "^{" + format_number(exponent) + "}"

    if num == 1:
        if den == 2:
            return "\\sqrt{" + base + "}"
        return "\\sqrt[" + str(den) + "]{" + base + "}"
    if num == -1:
        if den == 2:
            return "\\frac{1}{\\sqrt{" + base + "}}"
        return "\\frac{1}{\\sqrt[" + str(den) + "]{" + base + "}}"
    inner = base + "^{" + format_number(num) + "}"
    if den == 2:
        return "\\sqrt{" + inner + "}"
    return "\\sqrt[" + str(den) + "]{" + inner + "}"


def render_symbol(symbol):
    if not symbol:
        return ""
    s = symbol.strip()
    if not s or "\\" in s:
        return s
    s = s.replace("_", "\\_")
    return re.sub(r"[A-Za-z]+", lambda m: f"\\mathrm{{{m.group(0)}}}", s)


def render_variable(item, flipped, locale="en-us"):
    """Render a formula_item variable as LaTeX."""
    raw_overwrite = item["symbol_overwrite"] or ""
    var = localise(raw_overwrite, locale) or item["quantity_symbol"] or item["quantity_id"] or "?"
    prefix = item["latex_prefix"] or ""
    suffix = item["latex_suffix"] or ""

    if prefix:
        # Insert {} between prefix and var if both are alphabetic, so LaTeX
        # doesn't read the variable as part of the command name.
        if prefix[-1].isalpha() and var[0].isalpha():
            var = prefix + "{}" + var
        else:
            var = prefix + var

    if suffix:
        if var[-1].isalpha() and suffix[0].isalpha():
            var = var + "{}" + suffix
        else:
            var = var + suffix

    label = localise(item["label"] or "", locale)
    if label and "_" not in var:
        var += "_{" + label + "}"

    exponent = item["var_exponent"] if item["var_exponent"] is not None else 1
    if flipped:
        exponent = -exponent

    return _render_with_exponent(exponent, var)


def render_coefficient(item, is_first_in_term):
    """Render a formula_item coefficient as LaTeX. Returns (body, is_negative)."""
    body = None
    is_negative = False
    latex_coef = item["latex_coef"] or None
    coeff_value = item["coeff_value"]
    coeff_exponent = item["coeff_exponent"] if item["coeff_exponent"] is not None else 1

    if latex_coef:
        body = latex_coef
    elif coeff_value is not None:
        value = coeff_value
        if value < 0:
            is_negative = True
            value = abs(value)
        body = format_number(value) if value != 1 else None

    if body is not None:
        body = _render_with_exponent(coeff_exponent, body)
        if not latex_coef and body == "1":
            body = None
    elif coeff_exponent not in (None, 1):
        body = _render_with_exponent(coeff_exponent, "1")

    if is_first_in_term and is_negative and body in (None, "", "1"):
        body = ""
        is_negative = False

    return (body if body else None), is_negative


def _join_latex_parts(parts):
    """Join LaTeX parts, inserting {} between a command and a following letter."""
    result = []
    for i, p in enumerate(parts):
        result.append(p)
        if i < len(parts) - 1:
            last = result[-1]
            nxt = parts[i + 1]
            if nxt and nxt[0].isalpha():
                j = len(last) - 1
                while j >= 0 and last[j].isalpha():
                    j -= 1
                if j >= 0 and last[j] == "\\" and j < len(last) - 1:
                    result.append("{}")
    return "".join(result)


def _render_items_group(items, flipped, locale="en-us"):
    """Render a list of items as (numerator_latex, denominator_latex)."""
    num_parts = []
    den_parts = []
    for i, item in enumerate(items):
        coefficient, is_negative = render_coefficient(item, is_first_in_term=(i == 0))

        if item["quantity_id"]:
            exponent = item["var_exponent"] if item["var_exponent"] is not None else 1
            if flipped:
                exponent = -exponent
            if is_negative and coefficient:
                coefficient = "-" + coefficient
            if exponent < 0:
                rendered_var = render_variable(
                    dict(item, var_exponent=abs(exponent)),
                    flipped=False,
                    locale=locale,
                )
                if coefficient:
                    den_parts.append(coefficient)
                den_parts.append(rendered_var)
            else:
                rendered_var = render_variable(item, flipped=flipped, locale=locale)
                if coefficient:
                    num_parts.append(coefficient)
                num_parts.append(rendered_var)
        elif coefficient:
            if is_negative:
                den_parts.append(coefficient)
            else:
                num_parts.append(coefficient)

    return _join_latex_parts(num_parts), _join_latex_parts(den_parts)


def render_formula_items(items, locale="en-us"):
    """Build a LaTeX string from formula_item rows. Handles fractions for negatives."""
    by_term = defaultdict(list)
    for item in items:
        by_term[item["term"]].append(item)

    left_hand_terms = []
    right_hand_terms = []

    for term_number in sorted(by_term):
        term_items = sorted(
            by_term[term_number],
            key=lambda x: (not x["is_primary"], x["sort_order"]),
        )
        primary = [item for item in term_items if item["is_primary"]]
        non_primary = [item for item in term_items if not item["is_primary"]]

        num, den = _render_items_group(primary, flipped=True, locale=locale)
        if num or den:
            if den:
                has_neg = num.startswith("-")
                clean_num = num.lstrip("-")
                if has_neg:
                    term_str = f"-\\frac{{{clean_num}}}{{{den}}}"
                else:
                    term_str = f"\\frac{{{num}}}{{{den}}}" if num else f"\\frac{{1}}{{{den}}}"
                if term_str == "\\frac{}{}":
                    term_str = "\\frac{1}{" + den + "}"
            else:
                term_str = num
            if term_str:
                left_hand_terms.append(term_str)

        num, den = _render_items_group(non_primary, flipped=False, locale=locale)
        if num or den:
            if den:
                has_neg = num.startswith("-")
                clean_num = num.lstrip("-")
                if has_neg:
                    term_str = f"-\\frac{{{clean_num}}}{{{den}}}"
                else:
                    term_str = f"\\frac{{{num}}}{{{den}}}" if num else f"\\frac{{1}}{{{den}}}"
                if term_str == "\\frac{}{}":
                    term_str = "\\frac{1}{" + den + "}"
            else:
                term_str = num
            if term_str:
                sign = "+"
                for item in non_primary:
                    coeff = item["coeff_value"]
                    if coeff is not None and coeff < 0:
                        sign = "-"
                        break
                right_hand_terms.append((sign, term_str))

    left_hand = " + ".join(left_hand_terms) if left_hand_terms else "1"
    right_parts = []
    for i, (sign, term_str) in enumerate(right_hand_terms):
        if i == 0:
            right_parts.append(f"- {term_str}" if sign == "-" else term_str)
        else:
            right_parts.append(f"{sign} {term_str}")
    right_hand = " ".join(right_parts)
    return f"{left_hand} = {right_hand}"


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


def fetch_formula_items(conn, formula_id):
    return conn.execute(
        """
        SELECT fi.*, q.symbol AS quantity_symbol
        FROM formula_item fi
        LEFT JOIN quantity q ON q.id = fi.quantity_id
        WHERE fi.formula_id = ?
        ORDER BY fi.term, fi.is_primary DESC, fi.sort_order
        """,
        (formula_id,),
    ).fetchall()


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
    """Return all formula items with quantity info for the detail table.

    Each row includes formula_item fields plus quantity_symbol, default_unit,
    and quantity_name (en-us).  Only items that have a quantity_id are relevant
    for the table, but the caller should filter if needed.
    """
    return conn.execute(
        """
        SELECT fi.*, q.symbol AS quantity_symbol, q.default_unit,
               json_extract(q.name, '$.en-us') AS quantity_name
        FROM formula_item fi
        LEFT JOIN quantity q ON q.id = fi.quantity_id
        WHERE fi.formula_id = ?
        ORDER BY fi.term, fi.is_primary DESC, fi.sort_order
        """,
        (formula_id,),
    ).fetchall()


def render_variable_base(item, locale="en-us"):
    """Render the base variable symbol (without exponent) for display tables."""
    raw_overwrite = item.get("symbol_overwrite") or ""
    var = localise(raw_overwrite, locale) or item.get("quantity_symbol") or item.get("quantity_id") or "?"
    prefix = item.get("latex_prefix") or ""
    suffix = item.get("latex_suffix") or ""

    if prefix:
        if prefix[-1].isalpha() and var[0].isalpha():
            var = prefix + "{}" + var
        else:
            var = prefix + var

    if suffix:
        if var[-1].isalpha() and suffix[0].isalpha():
            var = var + "{}" + suffix
        else:
            var = var + suffix

    label = localise(item.get("label") or "", locale)
    if label and "_" not in var:
        var += "_{" + label + "}"

    return var


def parse_quantity_name_markers(text):
    """Replace [quantity_id] markers within a string with <a> links.

    The marker text is lowercased and spaces are converted to underscores
    to look up the quantity ID; the display text of the link is the raw
    marker text (preserving original casing).  For example:

    ``"Initial [velocity]"`` →
    ``'Initial <a href="/quantity/velocity">velocity</a>'``

    ``"Specific [Specific heat capacity]"`` →
    ``'Specific <a href="/quantity/specific_heat_capacity">Specific heat capacity</a>'``
    """
    def _repl(m):
        raw = m.group(1)
        qid = raw.lower().replace(' ', '_')
        return f'<a href="/quantity/{html.escape(qid)}">{html.escape(raw)}</a>'
    return re.sub(r'\[([^\]]+)\]', _repl, text)


def fetch_formula_quantities(conn, formula_id):
    dim_cols = DIMENSION_COLUMNS(conn)
    rows = conn.execute(
        f"""
        SELECT DISTINCT q.id, q.name, q.symbol,
               json_extract(q.name, '$.en-us') AS name_en,
               COALESCE(json_extract(fi.quantity_name_overwrite, '$.en-us'),
                        json_extract(q.name, '$.en-us')) AS display_name,
               q.default_unit,
               {', '.join(f'q.{c}' for c in dim_cols)}
        FROM formula_item fi
        JOIN quantity q ON q.id = fi.quantity_id
        WHERE fi.formula_id = ?
        """,
        (formula_id,),
    ).fetchall()
    return sort_quantities_by_dimension(rows, conn)


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
        SELECT u.*,
               json_extract(u.name, '$.en-us') AS name_en
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
        FROM formula_item fi
        JOIN formula f ON f.id = fi.formula_id
        WHERE fi.quantity_id = ? AND f.id != 'dimensions'
        ORDER BY f.topic, f.difficulty, f.id
        """,
        (quantity_id,),
    ).fetchall()


def fetch_quantity_formulas_by_side(conn, quantity_id):
    """Return (primary_formulas, non_primary_formulas) for a quantity.

    Primary: formula has this quantity on the left (is_primary=1).
    Non-primary: formula references this quantity but never as left-side primary.
    """
    primary = conn.execute(
        """
        SELECT DISTINCT f.id, f.name,
               json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty
        FROM formula_item fi
        JOIN formula f ON f.id = fi.formula_id
        WHERE fi.quantity_id = ? AND fi.is_primary = 1 AND f.id != 'dimensions'
        ORDER BY f.topic, f.difficulty, f.id
        """,
        (quantity_id,),
    ).fetchall()
    non_primary = conn.execute(
        """
        SELECT DISTINCT f.id, f.name,
               json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty
        FROM formula_item fi
        JOIN formula f ON f.id = fi.formula_id
        WHERE fi.quantity_id = ? AND f.id != 'dimensions'
          AND f.id NOT IN (
            SELECT formula_id FROM formula_item
            WHERE quantity_id = ? AND is_primary = 1
          )
        ORDER BY f.topic, f.difficulty, f.id
        """,
        (quantity_id, quantity_id),
    ).fetchall()
    return primary, non_primary


def compute_formula_dimensions(conn, formula_id):
    """Compute dimensions from primary-term quantities."""
    cols = DIMENSION_COLUMNS(conn)
    dims = [0.0] * len(cols)
    if not cols:
        return []
    items = conn.execute(
        f"""
        SELECT fi.var_exponent, {', '.join(f'q.{c}' for c in cols)}
        FROM formula_item fi
        JOIN quantity q ON q.id = fi.quantity_id
        WHERE fi.formula_id = ? AND fi.is_primary = 1
        """,
        (formula_id,),
    ).fetchall()
    for r in items:
        exp = abs(r["var_exponent"] or 1)
        for i, column in enumerate(cols):
            dims[i] += r[column] * exp
    return [int(d) for d in dims]


def fetch_si_unit_symbol(conn, quantity_id):
    """Get the SI base unit symbol for a quantity."""
    row = conn.execute(
        """
        SELECT u.symbol FROM unit u
        WHERE u.quantity_id = ? AND u.default_unit = 1
        LIMIT 1
        """,
        (quantity_id,),
    ).fetchone()
    return row["symbol"] if row else ""


def fetch_quantity_related_formulas(conn, quantity_id):
    """Get formulas related via formula_relation that use this quantity."""
    return conn.execute(
        """
        SELECT DISTINCT f.id, f.name,
               json_extract(f.name, '$.en-us') AS name_en,
               fr.relation_type
        FROM formula_relation fr
        JOIN formula f ON f.id = fr.related_id
        JOIN formula_item fi ON fi.formula_id = f.id
        WHERE fi.quantity_id = ?
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
    rows = db.execute("SELECT id, name FROM unit").fetchall()
    return {r["id"]: localise(r["name"], locale) for r in rows}


def _unit_symbol_map(db):
    rows = db.execute("SELECT id, symbol FROM unit").fetchall()
    return {r["id"]: r["symbol"] for r in rows}


def build_dimension_symbol_maps(conn):
    """Return (variable_map, unit_map, dim_map) for dimension display."""
    dimension_qty_ids = dimension_quantity_ids(conn)
    variable_map, unit_map, dim_map = {}, {}, {}
    for symbol in DIMENSION_SYMBOLS(conn):
        quantity_id = dimension_qty_ids.get(symbol)
        if not quantity_id:
            variable_map[symbol] = symbol
            unit_map[symbol] = symbol
            dim_map[symbol] = symbol
            continue
        row = conn.execute(
            "SELECT symbol, symbol_overwrite, default_unit FROM quantity WHERE id=?",
            (quantity_id,),
        ).fetchone()
        variable_map[symbol] = row["symbol"] if row and row["symbol"] else symbol

        unit_symbol = None
        if row and row["default_unit"]:
            try:
                default_unit = json.loads(row["default_unit"])
                if isinstance(default_unit, list) and default_unit:
                    uid = default_unit[0].get("unit", "")
                    if uid:
                        unit_row = conn.execute(
                            "SELECT symbol FROM unit WHERE id=?", (uid,),
                        ).fetchone()
                        if unit_row:
                            unit_symbol = unit_row["symbol"]
            except (ValueError, TypeError, IndexError):
                pass
        if unit_symbol:
            unit_map[symbol] = f"\\mathrm{{{unit_symbol}}}" if "\\" not in unit_symbol else unit_symbol
        else:
            unit_map[symbol] = variable_map[symbol]

        dim_map[symbol] = symbol

    # dimension symbols come from formula_item.symbol_overwrite (merged dimension table)
    for dim in fetch_dimensions(conn):
        sym = dim["symbol_overwrite"]
        if sym:
            dim_map[sym] = sym

    return variable_map, unit_map, dim_map


def _base_dimension_order(conn=None):
    """Return {quantity_id: sort_order} for base dimensions from formula_item."""
    order = {}
    for d in conn.execute(
        "SELECT quantity_id, sort_order FROM formula_item WHERE formula_id = 'dimensions' ORDER BY sort_order"
    ).fetchall():
        order[d["quantity_id"]] = d["sort_order"]
    return order


def sort_quantities_by_dimension(quantity_rows, conn=None):
    """Sort quantities: base dimensions from formula_item first, rest by id."""
    base_order = _base_dimension_order(conn)
    def key(quantity):
        base_index = base_order.get(quantity["id"], 99)
        return (0 if base_index < 99 else 1, base_index, quantity["id"])
    return sorted(quantity_rows, key=key)


def fetch_all_quantities(conn):
    """Return all quantities with default_unit parsed and dimensions."""
    dim_cols = DIMENSION_COLUMNS(conn)
    rows = conn.execute(
        f"""
        SELECT q.id, q.name, q.symbol,
               json_extract(q.name, '$.en-us') AS name_en,
               q.topic AS topic_id, q.difficulty, q.default_unit,
               {', '.join(f'q.{c}' for c in dim_cols)}
        FROM quantity q
        ORDER BY q.id
        """
    ).fetchall()
    return sort_quantities_by_dimension(rows, conn)


def fetch_all_formulas(conn):
    """Return all formulas (excluding the internal 'dimensions' formula)."""
    return conn.execute(
        """
        SELECT f.id, f.name, json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty
        FROM formula f
        WHERE f.id != 'dimensions'
        ORDER BY f.topic, f.difficulty, f.id
        """
    ).fetchall()


def compute_all_formula_dimensions(conn):
    """Return {formula_id: {dim_M, dim_L, ...}} for all formulas."""
    cols = DIMENSION_COLUMNS(conn)
    if not cols:
        return {}
    selects = [
        f"CAST(SUM(ABS(COALESCE(fi.var_exponent, 1)) * q.{c}) AS INTEGER) AS {c}"
        for c in cols
    ]
    rows = conn.execute(
        f"""
        SELECT fi.formula_id,
               {', '.join(selects)}
        FROM formula_item fi
        JOIN quantity q ON q.id = fi.quantity_id
        WHERE fi.is_primary = 1
        GROUP BY fi.formula_id
        """
    ).fetchall()
    return {
        r["formula_id"]: {c: int(r[c] or 0) for c in cols}
        for r in rows
    }


def fetch_formulas_with_any_quantity(conn, quantity_ids):
    """Return formula_ids that reference ANY of the given quantity IDs (OR)."""
    if not quantity_ids:
        return None
    placeholders = ",".join("?" for _ in quantity_ids)
    rows = conn.execute(
        f"""
        SELECT DISTINCT formula_id FROM formula_item
        WHERE quantity_id IN ({placeholders})
        """,
        quantity_ids,
    ).fetchall()
    return {r["formula_id"] for r in rows}


def fetch_formulas_with_all_quantities(conn, quantity_ids):
    """Return formula_ids that reference ALL of the given quantity IDs (AND)."""
    if not quantity_ids:
        return None
    n = len(quantity_ids)
    placeholders = ",".join("?" for _ in quantity_ids)
    rows = conn.execute(
        f"""
        SELECT formula_id, COUNT(DISTINCT quantity_id) AS match_count
        FROM formula_item
        WHERE quantity_id IN ({placeholders})
        GROUP BY formula_id
        HAVING match_count = ?
        """,
        quantity_ids + [n],
    ).fetchall()
    return {r["formula_id"] for r in rows}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

EXPORT_TABLE_ORDER = [
    "formula", "formula_item", "formula_relation",
    "quantity", "unit",
]

EXPORT_TABLE_COLUMNS = {
    "formula": [
        "id", "name", "topic", "difficulty", "description", "links",
    ],
    "formula_item": [
        "formula_id", "term", "is_primary", "sort_order",
        "coeff_value", "latex_coef", "coeff_exponent",
        "quantity_id", "var_exponent", "label",
        "symbol_overwrite", "quantity_name_overwrite",
        "latex_prefix", "latex_suffix",
    ],
    "formula_relation": [
        "formula_id", "related_id", "relation_type",
        "description",
    ],
    "quantity": [
        "id", "name", "symbol", "symbol_overwrite", "topic",
        "difficulty", "description", "links", "default_unit",
        # dim_M, dim_L, ... added dynamically in _each_table
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
        if table == 'quantity':
            dim_cols = DIMENSION_COLUMNS(conn)
            # Insert after default_unit (index 8)
            columns[9:9] = dim_cols
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
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    for table, columns, rows in _each_table(conn):
        with open(path / f"{table}.csv", "w", newline="") as f:
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

