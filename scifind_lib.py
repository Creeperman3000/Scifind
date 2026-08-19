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
    # Malformed JSON — some symbol_overwrite entries in seed.sql embed raw
    # LaTeX like `{"en-us": "\\lambda"}` (double-backslash from SQL escaping
    # becoming invalid `\l` JSON). Recover the first "..." value.
    if d is None and s.endswith("}"):
        _, _, raw = s[s.find("{") + 1 : s.rfind("}")].partition(":")
        raw = raw.strip()
        if raw.startswith('"') and raw.endswith('"'):
            return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return s


def localise_english(value):
    return localise(value, "en-us")


# ---------------------------------------------------------------------------
# Science tree
# ---------------------------------------------------------------------------

_PROJECT_DIR = Path(__file__).resolve().parent
TREE_PATH = _PROJECT_DIR / "tree.json"
_TREE_CACHE = {}


def load_tree():
    """Load the sciences/branch/topic tree from tree.json (cached)."""
    if "tree" not in _TREE_CACHE:
        try:
            with open(TREE_PATH, encoding="utf-8") as f:
                _TREE_CACHE["tree"] = json.load(f).get("sciences", [])
        except (OSError, ValueError):
            _TREE_CACHE["tree"] = []
    return _TREE_CACHE["tree"]


def _walk_tree(tree, visit):
    """Depth-first walk; visit(node) is called for each node."""
    for root in tree:
        visit(root)
        for child in (root.get("children") or []):
            _walk_tree([child], visit)


def _collect_ids(tree, predicate):
    out = set()

    def visit(node):
        if predicate(node):
            out.add(node["id"])
    _walk_tree(tree, visit)
    return out


def all_tree_ids(tree):
    return _collect_ids(tree, lambda n: True)


def topic_name_map(tree, locale="en-us"):
    """Flat {id: localised name} for every node in the tree."""
    out = {}

    def visit(node):
        out[node["id"]] = localise(node.get("translations") or {}, locale)
    _walk_tree(tree, visit)
    return out


def topic_name(topic_id, tree=None, locale="en-us"):
    """Resolve a topic ID to its localised display name (en-us fallback)."""
    if not topic_id:
        return None
    if tree is None:
        tree = load_tree()
    name_map = topic_name_map(tree, locale)
    if topic_id in name_map:
        return name_map[topic_id]
    return topic_id.replace("_", " ").title()


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

_NAME_PICK_SQL = (
    "COALESCE("
    "CASE WHEN LOWER(json_extract(name, '$.cs-cz')) LIKE ? THEN json_extract(name, '$.cs-cz') END,"
    "CASE WHEN LOWER(json_extract(name, '$.en-us')) LIKE ? THEN json_extract(name, '$.en-us') END,"
    "json_extract(name, '$.en-us')"
    ")"
)


def search_headings(conn, query, limit=30):
    """Search entity names, symbols, and IDs via SQL LIKE substring match."""
    if not query or not query.strip():
        return []
    q = query.strip().lower()
    pat = f"%{q}%"
    # (table, kind, extra LIKE column) tuples; the leading name LIKE clause is
    # always present, plus `id`, plus a kind-specific extra column.
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
        # _NAME_PICK_SQL uses the pattern 2 times; the WHERE clause adds 3.
        params.extend([pat] * 5)
        if extra:
            where.append(f"LOWER({extra}) LIKE ?")
            params.append(pat)
        union_parts.append(
            f"SELECT id, '{kind}' AS kind, {_NAME_PICK_SQL} AS display_name "
            f"FROM {table} WHERE {' OR '.join(where)}"
        )
    sql = (
        f"SELECT * FROM ({f' UNION ALL '.join(union_parts)}) "
        f"ORDER BY CASE WHEN LOWER(display_name) = LOWER(?) THEN 0 ELSE 1 END, LENGTH(display_name)"
    )
    rows = conn.execute(sql, params + [q]).fetchall()
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
    return " · ".join(parts) if parts else "\\varnothing"


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
    return " \\cdot ".join(parts) if parts else "\\varnothing"


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
    r"""A node in the parsed formula tree.

    Four kinds: operand leaves (quantity, constant, number) and operator
    nodes that carry children + precedence metadata. Two fields drive
    the renderer's paren wrapping:

    - `paren_arg` (operator nodes only): per-operand opt-in copied from
      `operator.paren_arg` at construction. Length == arity; True means
      the operand may be wrapped in \left(...\right) by the precedence
      rule or a source `(...)` group, False means the operator's macro
      syntax already scopes the operand (e.g. \frac{a}{b}, \sqrt{a},
      a^{b}) and no wrap is allowed.
    - `_paren_wrap`: True when this node's source position was inside a
      `(...)` group. Used by `_wrap` to force-wrap a multi-token child
      even if the precedence rule wouldn't otherwise ask for it.
    """
    kind: str  # "quantity" | "constant" | "number" | "operator"
    children: list["_Node"] = field(default_factory=list)
    # operand metadata
    quantity_id: Optional[str] = None
    constant_id: Optional[str] = None
    value: Optional[float] = None
    label: Optional[str] = None
    symbol_overwrite: Optional[str] = None
    name_overwrite: Optional[str] = None
    name_overwrite: Optional[str] = None
    # operator metadata
    operator_id: Optional[str] = None
    symbol: Optional[str] = None
    arity: int = 0
    precedence: int = 0
    associativity: str = "left"
    operator_type: str = "infix"
    paren_arg: Optional[list] = None
    _paren_wrap: bool = False


def _fetch(conn, table: str, columns: str, key: str) -> dict:
    row = conn.execute(
        f"SELECT {columns} FROM {table} WHERE id = ?", (key,)
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown {table.rstrip('s')}: {key!r}")
    return dict(row)


def _load_operator(conn, operator_id: str) -> dict:
    return _fetch(conn, "operator",
                  "id, symbol, arity, precedence, associativity, operator_type, paren_arg",
                  operator_id)


def _load_constant(conn, constant_id: str) -> dict:
    return _fetch(conn, "constant",
                  "id, name, symbol, value, default_unit",
                  constant_id)


def _load_quantity(conn, quantity_id: str) -> dict:
    return _fetch(conn, "quantity",
                  "id, name, symbol, symbol_overwrite, default_unit",
                  quantity_id)


def _parse_paren_arg(raw, arity, op_id):
    """Parse the operator.paren_arg JSON column into [bool].

    Returns the parsed list of length == arity. The column has a NOT NULL
    DEFAULT '[1]' and a json_valid CHECK at the schema level, so a malformed
    value here is a programmer error and raises loudly.
    """
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise ValueError(
            f"paren_arg for {op_id} must be a JSON list of {arity} 0/1 values; got {raw!r}"
        )
    if not isinstance(parsed, list) or len(parsed) != arity:
        raise ValueError(
            f"paren_arg for {op_id} must be a JSON list of {arity} 0/1 values; got {raw!r}"
        )
    if not all(p in (0, 1, True, False) for p in parsed):
        raise ValueError(
            f"paren_arg for {op_id} must contain only 0/1; got {parsed!r}"
        )
    return [bool(p) for p in parsed]


# Per-connection caches for the equation parser. These are populated lazily on
# first use; the caller must hand us the same connection each time. Keys:
#   "qty_ids"     -> set of quantity ids
#   "const_ids"   -> set of constant ids
#   "operators"   -> (op_by_id dict, symbol_to_id dict)
_PARSER_CACHE = {}


def _parser_caches(conn):
    cache = _PARSER_CACHE.setdefault(id(conn), {})
    if "qty_ids" not in cache:
        cache["qty_ids"] = {r["id"] for r in conn.execute("SELECT id FROM quantity")}
        cache["const_ids"] = {r["id"] for r in conn.execute("SELECT id FROM constant")}
        by_id = {}
        symbol_to_id = {}
        for r in conn.execute(
            "SELECT id, symbol, math, arity, precedence, associativity, operator_type, paren_arg "
            "FROM operator"
        ):
            by_id[r["id"]] = dict(r)
            if r["symbol"]:
                symbol_to_id[r["symbol"]] = r["id"]
        cache["operators"] = (by_id, symbol_to_id)
    return cache


def parse_equation(conn, equation):
    """Tokenize an infix equation string and convert to RPN (Shunting-yard).

    Returns a list of token dicts in the same shape as formula_token rows:
    {token_kind, position is implicit, quantity_id|constant_id|operator_id|value}.

    Raises ValueError on a parse error. Operator matching is driven by the
    `operator` table: an identifier like 'sin' is treated as the operator
    'sin' if one exists in the table, otherwise as a quantity/constant id.
    """
    cache = _parser_caches(conn)
    op_by_id, symbol_to_id = cache["operators"]
    qty_ids = cache["qty_ids"]
    const_ids = cache["const_ids"]

    def match_operator():
        for length in (4, 3, 2, 1):
            if i + length > n:
                continue
            piece = s[i:i + length]
            op_id = symbol_to_id.get(piece)
            if op_id is None:
                continue
            return op_id, length
        return None, 0

    if not equation or not equation.strip():
        return []

    s = equation
    i, n = 0, len(s)
    tokens = []

    while i < n:
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and s[i + 1].isdigit()):
            j = i
            seen_dot = False
            seen_exp = False
            while j < n:
                c = s[j]
                if c.isdigit():
                    j += 1
                elif c == "." and not seen_dot and not seen_exp:
                    seen_dot = True
                    j += 1
                elif c in ("e", "E") and not seen_exp:
                    seen_exp = True
                    j += 1
                    if j < n and s[j] in "+-":
                        j += 1
                else:
                    break
            num_str = s[i:j]
            try:
                value = float(num_str)
            except ValueError as e:
                raise ValueError(f"bad number: {num_str!r}") from e
            tokens.append({"token_kind": "number", "value": value})
            i = j
            continue
        if ch.isalpha() or ch == "_":
            op_id, op_len = match_operator()
            if op_id is not None:
                tokens.append({"token_kind": "operator", "operator_id": op_id})
                i += op_len
                continue
            j = i
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            ident = s[i:j]
            alias = None
            if j < n and s[j] == "[":
                k = s.find("]", j + 1)
                if k == -1:
                    raise ValueError(f"unterminated alias for {ident!r}")
                alias = s[j + 1:k] or None
                j = k + 1
            if ident in op_by_id:
                tok = {"token_kind": "operator", "operator_id": ident}
                if alias is not None:
                    raise ValueError(f"operator {ident} cannot have an alias")
                tokens.append(tok)
            else:
                if ident in qty_ids:
                    tok = {"token_kind": "quantity", "quantity_id": ident}
                elif ident in const_ids:
                    tok = {"token_kind": "constant", "constant_id": ident}
                else:
                    raise ValueError(f"unknown identifier: {ident!r}")
                if alias is not None:
                    tok["label"] = alias
                tokens.append(tok)
            i = j
            continue
        if ch == "(":
            tokens.append({"token_kind": "operator", "operator_id": "paren_open"})
            i += 1
            continue
        if ch == ")":
            tokens.append({"token_kind": "operator", "operator_id": "paren_close"})
            i += 1
            continue
        op_id, op_len = match_operator()
        if op_id is not None:
            tokens.append({"token_kind": "operator", "operator_id": op_id})
            i += op_len
            continue
        raise ValueError(f"unexpected character: {ch!r} at position {i}")

    return _shunting_yard_to_rpn(tokens, op_by_id)


def _shunting_yard_to_rpn(tokens, op_by_id):
    """Convert a flat token list (already in infix order) to RPN.

    Implements the shunting-yard algorithm with the operator precedence and
    associativity from the operator table. Prefix operators are pushed
    directly onto the operator stack; relational operators (which form
    equations) terminate the LHS at the first one we encounter.

    Paren-group tracking: when `)` closes a `(...)` group, the result of
    the group (the outermost token emitted for that group) gets a
    `_paren_wrap=True` marker on the token dict. The RPN evaluator copies
    that marker onto the resulting `_Node`; the renderer (`_wrap`) uses
    it to force-wrap a multi-token child operand — preserving the user's
    explicit parens end-to-end as long as `paren_arg` allows`.

    Operand-count tracking: each operator stack entry carries a `consumed`
    counter. An operator is "complete" once `consumed == arity`; only
    complete operators are eligible to be popped by the precedence rule.
    Without this, an n-ary infix operator (e.g. arity-2 `log base arg`,
    arity-3 `sum from to body`) would greedily steal the first few
    operands, then be popped as soon as the next lower-precedence infix
    operator arrived — leaving later operands stranded and silently
    re-binding to operators below it. With the gate, `log euler_e amount
    1 add` parses as `add(log(e, n), 1)` (the textbook binary behaviour
    once `log` is complete) rather than `add(e, log(n, 1))`. To group
    the right operand the user must write parens: `log euler_e (amount
    1 add)` -> `add(1, log(e, n))`.

    An operand emitted to `output` is also bound to the topmost "open"
    operator on the stack (the one immediately above `paren_open`,
    skipping prefix/postfix ops which consume their operands directly).
    Only open, non-complete operators receive the bump.
    """
    output = []
    stack = []

    def _bump_operand_count():
        """The operand just emitted on `output` belongs to the topmost
        operator stack entry that isn't `paren_open` AND isn't already
        complete. Operators that have already consumed `arity` operands
        are no longer accepting more, so the operand skips them and
        binds to the next open operator below. This is what makes
        `log euler_e amount 1 add` parse as `add(log_b(n), 1)` rather
        than `add(e, log(n, 1))`."""
        for entry in reversed(stack):
            if entry["operator_id"] == "paren_open":
                continue
            op_meta = op_by_id.get(entry["operator_id"])
            if op_meta is None:
                continue
            if entry["consumed"] >= op_meta["arity"]:
                # Already complete; skip to the next open operator below.
                continue
            entry["consumed"] += 1
            return

    for tok in tokens:
        kind = tok["token_kind"]
        if kind in ("number", "quantity", "constant"):
            output.append(tok)
            # A freshly emitted operand belongs to the topmost "open"
            # operator on the stack. Eagerly drain any prefix/postfix
            # operators sitting on top of that — they consume the operand
            # immediately. The operand's slot on the topmost open infix/
            # relational operator is bumped via _bump_operand_count
            # (called below).
            while stack and stack[-1]["operator_id"] in op_by_id:
                top = op_by_id[stack[-1]["operator_id"]]
                if top["operator_type"] not in ("prefix", "postfix"):
                    break
                output.append(stack.pop())
            _bump_operand_count()
            continue
        op_id = tok["operator_id"]
        if op_id == "paren_open":
            stack.append({**tok, "consumed": 0})
            continue
        if op_id == "paren_close":
            while stack and stack[-1]["operator_id"] != "paren_open":
                output.append(stack.pop())
            if not stack:
                raise ValueError("unmatched ')'")
            stack.pop()
            # Mark the outermost token of the group as source-wrapped.
            # `output[-1]` is the group's result after draining the operators
            # between the matching `(` and `)`.
            if output:
                output[-1]["_paren_wrap"] = True
            # A prefix (function) operator pushed just before the '(' has
            # now consumed its parenthesized argument and must be applied
            # before any following infix/relational operator. Without this
            # step, "sqrt(2) + 1" would parse as "sqrt(2 + 1)".
            while stack:
                top_id = stack[-1]["operator_id"]
                if top_id == "paren_open":
                    break
                top_op = op_by_id.get(top_id)
                if top_op is None or top_op["operator_type"] != "prefix":
                    break
                output.append(stack.pop())
            # The (...) group's result counts as one operand for whichever
            # operator is now on top of the stack.
            _bump_operand_count()
            continue
        op = op_by_id.get(op_id)
        if op is None:
            raise ValueError(f"unknown operator: {op_id!r}")
        op_type = op["operator_type"]
        prec = op["precedence"]
        assoc = op["associativity"]
        if op_type in ("prefix", "postfix"):
            stack.append({**tok, "consumed": 0})
            continue
        if assoc == "none" and op_type == "relational":
            while stack and stack[-1]["operator_id"] != "paren_open":
                top_id = stack[-1]["operator_id"]
                top = op_by_id.get(top_id)
                if top and top["operator_type"] == "relational":
                    break
                output.append(stack.pop())
            stack.append({**tok, "consumed": 0})
            continue
        while stack:
            top_entry = stack[-1]
            top_id = top_entry["operator_id"]
            if top_id == "paren_open":
                break
            top = op_by_id.get(top_id)
            if top is None or top["operator_type"] in ("prefix", "postfix"):
                break
            # Only a complete operator (consumed == arity) is eligible to
            # be popped by the precedence rule. An incomplete operator on
            # top of the stack is still waiting for more operands — let it
            # stay so its later operand(s) can be read.
            if top_entry["consumed"] < top["arity"]:
                break
            if top["precedence"] > prec or (
                top["precedence"] == prec and assoc == "left"
            ):
                output.append(stack.pop())
            else:
                break
        # Push the new infix operator. By the textbook shunting-yard
        # contract, an infix operator on the stack "owns" the LAST
        # `arity` operands already on the output queue — they are its
        # arguments, popped together when the operator is later moved to
        # output. Initialise `consumed` to `arity` so:
        #   * The completeness gate above treats this operator as ready
        #     to be popped as soon as the next operator arrives (or at end
        #     of input), instead of greedily consuming additional operands
        #     that belong to operators later in the source.
        #   * The next operand arrival correctly skips this operator and
        #     bumps the operator below it (when there is one).
        # Without this, an n-ary infix operator (sqrt, log, sum, ...)
        # would arrive AFTER more operands than its arity and the
        # bump logic would silently assign them all to it, leaving the
        # real operands orphaned on the output.
        # The actual arity-aware claiming still happens at pop time in
        # `_evaluate_rpn`, which pops exactly `arity` operands from the
        # tail of the output queue; this initial `consumed = arity` just
        # makes the completeness gate and the operand-bump loop agree
        # with that contract.
        stack.append({**tok, "consumed": 0})

    while stack:
        top = stack.pop()
        if top["operator_id"] in ("paren_open", "paren_close"):
            raise ValueError("unmatched parenthesis")
        output.append(top)

    return output


def preview_equation(conn, equation, locale="en-us", dim_caches=None, overrides=None, dim_mode="dim"):
    """Parse an equation and return a preview dict (no DB writes).

    `overrides` is an optional mapping keyed by "quantity_id|alias" with
    {symbol, name, label} values. When provided they are applied to the
    quantity tokens before rendering, so the LaTeX and the variables list
    reflect what the user is currently typing in the /create override inputs.

    Returns {tokens, latex, dim_latex, variables, error}.
    On parse error returns {error: str} and tokens=[].
    """
    if not equation or not equation.strip():
        return {"tokens": [], "latex": "", "dim_latex": "",
                "variables": [], "error": ""}
    try:
        tokens = parse_equation(conn, equation)
    except ValueError as e:
        return {"tokens": [], "latex": "", "dim_latex": "",
                "variables": [], "error": str(e)}
    if not tokens:
        return {"tokens": [], "latex": "", "dim_latex": "",
                "variables": [], "error": ""}

    for pos, tok in enumerate(tokens, start=1):
        if tok["token_kind"] != "quantity":
            continue
        tok["pos"] = pos
        key = tok["quantity_id"] + "|" + (tok.get("label") or "") + "|" + str(pos)
        if overrides:
            ov = overrides.get(key) or {}
            if ov.get("symbol"):
                tok["symbol_overwrite"] = ov["symbol"]
            if ov.get("label"):
                tok["label"] = ov["label"]

    try:
        tree = _evaluate_rpn(conn, tokens)
    except ValueError as e:
        return {"tokens": tokens, "latex": "", "dim_latex": "",
                "variables": [], "error": str(e)}

    latex = _latex_node(tree, conn, locale)

    dims = compute_rpn_dimensions(conn, tokens)
    if dim_caches is None:
        var_map, unit_map, dim_map = build_dimension_symbol_maps(conn)
    else:
        var_map = dim_caches.get("var", {})
        unit_map = dim_caches.get("unit", {})
        dim_map = dim_caches.get("dim", {})
    dim_latex = format_dimensions_latex(
        *dims,
        variable_symbols=var_map,
        unit_symbols=unit_map,
        dimension_symbols=dim_map,
        mode=dim_mode,
    )

    seen = []
    for tok in tokens:
        if tok["token_kind"] != "quantity":
            continue
        qid = tok["quantity_id"]
        # The `drop` sentinel is a placeholder for an operand slot the user
        # wants to blank out — it has no real quantity to surface in the UI.
        if qid == "drop":
            continue
        pos = tok["pos"]
        qrow = _load_quantity(conn, qid)
        key = qid + "|" + (tok.get("label") or "") + "|" + str(pos)
        ov = (overrides or {}).get(key) or {}
        seen.append({
            "id": qid,
            "alias": tok.get("label") or "",
            "pos": pos,
            "key": key,
            "symbol": qrow["symbol"],
            "name": qrow["name"],
            "symbol_overwrite": ov.get("symbol", ""),
            "name_overwrite": ov.get("name", ""),
        })

    return {
        "tokens": tokens,
        "latex": latex,
        "dim_latex": dim_latex,
        "variables": seen,
        "error": "",
    }


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
            new_node = _Node(
                kind="operator",
                children=args,
                operator_id=op["id"],
                symbol=op["symbol"],
                arity=op["arity"],
                precedence=op["precedence"],
                associativity=op["associativity"],
                operator_type=op["operator_type"],
                paren_arg=_parse_paren_arg(op["paren_arg"], op["arity"], op["id"]),
                # Propagate the source-group wrap marker from the token
                # (the parser marks only the outermost token of each (...)).
                _paren_wrap=bool(t.get("_paren_wrap")),
            )
            # Chainable relationals: with `assoc='none'` the shunting-yard
            # treats `a = b = c` as `a = (b = c)` in source, which after RPN
            # reduction becomes `eq(a, eq(b, c))` — the inner eq is the
            # RIGHT operand. Flatten such nested chains into a single node
            # with N children so the renderer emits `a = b = c` instead of
            # `a = (b = c)`. The list of chainable operators lives here
            # (not in the DB) because the semantics are "this operator is
            # associative in the rendering sense" — true for every
            # relational we ship today.
            if (
                op["operator_type"] == "relational"
                and op["id"] in _CHAINABLE_RELATIONALS
                and len(args) == 2
                and args[1].kind == "operator"
                and args[1].operator_id == op["id"]
                and args[1].operator_type == "relational"
            ):
                # new children in source order: leftmost operand first, then
                # the inner chain's terms. The inner chain preserves its own
                # source order; the new leftmost becomes index 0.
                inner = args[1]
                new_node.children = [args[0]] + list(inner.children)
                new_node.arity = len(new_node.children)
                new_node._paren_wrap = inner._paren_wrap
            stack.append(new_node)
        elif kind == "quantity":
            stack.append(_Node(
                kind="quantity",
                quantity_id=t["quantity_id"],
                label=t.get("label"),
                symbol_overwrite=t.get("symbol_overwrite"),
                name_overwrite=t.get("name_overwrite"),
                _paren_wrap=bool(t.get("_paren_wrap")),
            ))
        elif kind == "constant":
            stack.append(_Node(
                kind="constant",
                constant_id=t["constant_id"],
                _paren_wrap=bool(t.get("_paren_wrap")),
            ))
        elif kind == "number":
            stack.append(_Node(
                kind="number",
                value=t["value"],
                _paren_wrap=bool(t.get("_paren_wrap")),
            ))
        else:
            raise ValueError(f"unknown token kind: {t!r}")
    if not stack:
        return None
    if len(stack) > 1:
        raise ValueError(f"RPN did not reduce: {len(stack)} items left on stack")
    return stack[0]


# Relational operators that chain associatively in source (a OP b OP c is
# interpreted as a chain of equalities/inequalities, not as a nested binary
# tree). This matches the convention used by `law_of_sines`,
# `bernoulli_pressure_velocity_horizontal`, `kelvin_planck_statement`, etc.
_CHAINABLE_RELATIONALS = {
    "eq", "approx", "neq", "ngeq", "sim", "perp", "parallel",
    "lt", "gt", "leq", "geq",
}


def _latex_quantity(node: _Node, conn, locale: str) -> str:
    if not node.quantity_id:
        return "?"
    # `drop` is a sentinel quantity whose only purpose is to blank out an
    # operand slot in the rendered output. It has an empty symbol and zero
    # dimensions, so it contributes nothing to either the LaTeX or the
    # dimensional analysis. The caller (operator-specific render paths like
    # log/sum) is responsible for collapsing the surrounding braces and
    # subscript/superscript markers when an operand is dropped.
    if node.quantity_id == "drop":
        return ""
    q = _load_quantity(conn, node.quantity_id)
    var = localise(node.symbol_overwrite or "", locale) or q["symbol"] or node.quantity_id
    label = localise(node.label or "", locale)
    if label and "_" not in var:
        var += "_{" + label + "}"
    # If the quantity row has no default symbol (e.g. `dimensionless` is
    # intentionally a slot-only quantity for the dimensional analysis)
    # and no override was supplied, drop the literal id token in the
    # rendered output. Treating it as `drop`-style empty is the only
    # thing that makes sense for a row with no glyph: its job is to consume
    # a slot in the dimensional analysis without contributing a visible
    # character.
    if not (localise(node.symbol_overwrite or "", locale) or q["symbol"]):
        return ""
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
    """Should this child be wrapped by the precedence rule under `parent`?

    Pure precedence/associativity check — returns True only when leaving
    the child bare would make the rendered output ambiguous (e.g. a + b * c
    needs parens around `b * c` when it's the right operand of `+`).

    The actual wrap is gated by `parent.paren_arg[i]` in `_wrap`, so this
    function does not need to know about operator-specific scoping; it just
    reports what the precedence rule says.
    """
    if child.kind != "operator":
        return False
    # Equations (`a = b`, `a ∝ b`) need parens around sub-equations, since
    # `a = b = c` is genuinely ambiguous. Wrap any relational child.
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
    """Wrap child in \\left(...\\right) per `paren_arg` and the precedence rule.

    Three gates, in order:
      1. `paren_arg[i]` — per-operand opt-in from the operator. False means
         the operator's macro syntax already scopes this operand
         (\\frac{a}{b}, \\sqrt{a}, a^{b}, \\overline{a}, \\sum); never wrap.
      2. Precedence rule (`_needs_paren`) — demands parens for unambiguous
         reading (e.g. a * (b + c)).
      3. Source-group override — child came from a `(...)` group in the
         source equation (`child._paren_wrap`), so the user asked for parens;
         force-wrap a multi-token child. Atomic operands (single quantity /
         number) are left bare since wrapping would be visual noise.
    """
    # Map side to the operand index in paren_arg. "child" is used by
    # arity-1 prefix/postfix operators — their only operand sits at index 0.
    side_idx = 0 if side == "child" else (0 if side == "left" else 1)
    paren_arg = parent.paren_arg or [True] * parent.arity
    if side_idx >= len(paren_arg) or not paren_arg[side_idx]:
        return child_str
    if _needs_paren(child, parent, side):
        return "\\left(" + child_str + "\\right)"
    if child._paren_wrap and child.kind == "operator" \
            and not child_str.startswith("\\left("):
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
    # sqrt: arity-2 infix that emits \sqrt{radicand} (square root) or
    # \sqrt[index]{radicand} (n-th root). Children: [radicand, index].
    # paren_arg=[0,0]: both operands are inside the macro's {...} scopes.
    # Implicit 2-omission: if the index is the literal number 2 (or `drop`),
    # emit `\sqrt{radicand}` rather than `\sqrt[2]{radicand}`. The math
    # template `a**(1/b if b != 2 else 0.5)` short-circuits to .5 (= 1/2)
    # when b is 2, so the same shape covers both square and n-th roots.
    if node.operator_id == "sqrt":
        radicand = _latex_node(node.children[0], conn, locale)
        index = node.children[1]
        if not radicand:
            return ""
        # Implicit 2-omission: skip the [2] when the index is the literal 2.
        is_default = (index.kind == "number" and index.value == 2)
        if is_default:
            return f"\\sqrt{{{radicand}}}"
        idx = _latex_node(index, conn, locale)
        if not idx:
            return f"\\sqrt{{{radicand}}}"
        return f"\\sqrt[{idx}]{{{radicand}}}"
    # sub: arity-2 infix emitting `a - b`. When the left operand is the
    # `drop` sentinel quantity this is the unary minus (replaces the old
    # `neg` prefix operator): `drop x sub` -> `-x`. Children: [a, b].
    if node.operator_id == "sub":
        left, right = node.children
        l = _latex_node(left, conn, locale)
        r = _latex_node(right, conn, locale)
        if left.kind == "quantity" and left.quantity_id == "drop":
            r = _wrap(r, right, node, "right")
            return f"-{r}"
        l = _wrap(l, left, node, "left")
        r = _wrap(r, right, node, "right")
        return f"{l} - {r}"
    # log: arity-2 infix that emits \log_{base}{arg}. Children: [base, arg].
    # paren_arg=[0,0]: both operands are inside the macro's {...} scopes, never
    # auto-wrapped. Either operand may be the `drop` quantity, which renders
    # to an empty string — so `log drop x` -> \log x and `log b drop` ->
    # \log_{b}. When both operands are dropped, both braces collapse and we
    # emit just `\log{arg}` to avoid `_{}^{}`. Implicit euler-omission
    # (mirroring sqrt's implicit 2-omission): a base of the `euler_e`
    # constant emits `\ln{arg}` rather than `\log_{e}{arg}` — so
    # `log euler_e length` -> \ln l.
    if node.operator_id == "log":
        base_node = node.children[0]
        arg = _latex_node(node.children[1], conn, locale)
        if not arg:
            return ""
        if base_node.kind == "constant" and base_node.constant_id == "euler_e":
            return f"\\ln{{{arg}}}"
        base = _latex_node(base_node, conn, locale)
        if not base:
            return f"\\log{{{arg}}}"
        return f"\\log_{{{base}}}{{{arg}}}"
    # sum: arity-3 infix that emits \sum_{from}^{to}{body}. Children:
    # [from, to, body]. paren_arg=[0,0,0]: all three operands are inside
    # the macro's {...} scopes. Any operand may be the `drop` quantity,
    # which renders to an empty string — so `sum 1 drop x` -> \sum_{1}{x},
    # `sum drop 5 x` -> \sum^{5}{x}, `sum drop drop x` -> \sum{x}.
    if node.operator_id == "sum":
        lo = _latex_node(node.children[0], conn, locale)
        hi = _latex_node(node.children[1], conn, locale)
        body = _latex_node(node.children[2], conn, locale)
        if not body:
            return ""
        if not lo and not hi:
            return f"\\sum{{{body}}}"
        if not lo:
            return f"\\sum^{{{hi}}}{{{body}}}"
        if not hi:
            return f"\\sum_{{{lo}}}{{{body}}}"
        return f"\\sum_{{{lo}}}^{{{hi}}}{{{body}}}"
    # lim: arity-3 infix that emits \lim_{var \to val}{body}. Children:
    # [var, val, body]. paren_arg=[0,0,0]: all three operands are inside
    # the macro's {...} scopes. Either var or val may be `drop` — if any
    # part of the subscript is missing, the subscript is dropped entirely.
    # A one-sided limit like `\lim_{x \to}` is malformed LaTeX, so we
    # prefer `\lim{body}` over emitting a broken arrow.
    if node.operator_id == "lim":
        var = _latex_node(node.children[0], conn, locale)
        val = _latex_node(node.children[1], conn, locale)
        body = _latex_node(node.children[2], conn, locale)
        if not body:
            return ""
        if not var or not val:
            return f"\\lim{{{body}}}"
        return f"\\lim_{{{var} \\to {val}}}{{{body}}}"
    # int: arity-3 infix that emits \int_{from}^{to}{body}. Children:
    # [from, to, body]. paren_arg=[0,0,0]: all three operands are inside
    # the macro's {...} scopes. Symmetric with `sum`: any operand may be
    # `drop` to blank it out.
    if node.operator_id == "int":
        lo = _latex_node(node.children[0], conn, locale)
        hi = _latex_node(node.children[1], conn, locale)
        body = _latex_node(node.children[2], conn, locale)
        if not body:
            return ""
        if not lo and not hi:
            return f"\\int{{{body}}}"
        if not lo:
            return f"\\int^{{{hi}}}{{{body}}}"
        if not hi:
            return f"\\int_{{{lo}}}{{{body}}}"
        return f"\\int_{{{lo}}}^{{{hi}}}{{{body}}}"
    # prod: arity-3 infix that emits \prod_{from}^{to}{body}. Children:
    # [from, to, body]. paren_arg=[0,0,0]: same shape as `sum` and `int`.
    if node.operator_id == "prod":
        lo = _latex_node(node.children[0], conn, locale)
        hi = _latex_node(node.children[1], conn, locale)
        body = _latex_node(node.children[2], conn, locale)
        if not body:
            return ""
        if not lo and not hi:
            return f"\\prod{{{body}}}"
        if not lo:
            return f"\\prod^{{{hi}}}{{{body}}}"
        if not hi:
            return f"\\prod_{{{lo}}}{{{body}}}"
        return f"\\prod_{{{lo}}}^{{{hi}}}{{{body}}}"
    # oint: arity-3 infix that emits \oint_{from}^{to}{body}. Children:
    # [from, to, body]. paren_arg=[0,0,0]: same shape as `int`, the
    # contour-integral counterpart.
    if node.operator_id == "oint":
        lo = _latex_node(node.children[0], conn, locale)
        hi = _latex_node(node.children[1], conn, locale)
        body = _latex_node(node.children[2], conn, locale)
        if not body:
            return ""
        if not lo and not hi:
            return f"\\oint{{{body}}}"
        if not lo:
            return f"\\oint^{{{hi}}}{{{body}}}"
        if not hi:
            return f"\\oint_{{{lo}}}{{{body}}}"
        return f"\\oint_{{{lo}}}^{{{hi}}}{{{body}}}"
    left, right = node.children
    # frac self-delimits via macro syntax (\frac{a}{b}) — both operands are
    # in {...}, never wrapped. paren_arg=[0,0] encodes this.
    if node.operator_id == "frac":
        l = _latex_node(left, conn, locale)
        r = _latex_node(right, conn, locale)
        return f"\\frac{{{l}}}{{{r}}}"
    # pow: base takes the next token (paren_arg[0]=1, may wrap for the
    # `add` base case like (m+m)^c). Exponent is in ^{...} (paren_arg[1]=0,
    # never auto-wrap); the braces are sufficient scope. Both are still
    # subject to _wrap so source (a+b)^(c+d) wraps both per user intent.
    if node.operator_id == "pow":
        l = _latex_node(left, conn, locale)
        r = _latex_node(right, conn, locale)
        l = _wrap(l, left, node, "left")
        r = _wrap(r, right, node, "right")
        return f"{l}^{{{r}}}"
    l, r = _render_binary(node, conn, locale)
    if node.symbol:
        return f"{l} {node.symbol} {r}"
    # Implicit multiplication (the `mul` operator with no symbol). Render per
    # the situation table:
    #   number × number  -> a \times b
    #   number × fraction / function / constant / variable / expression
    #                     -> concat (optionally with thin space for \frac)
    #   variable × variable / constant -> concat
    #   expression × ... -> concat (no inner parens added; caller-controlled)
    if left.kind == "number" and right.kind == "number":
        return f"{l} \\times {r}"
    if left.kind == "number":
        if right.kind == "operator" and right.operator_id == "frac":
            return f"{l}\\,\\frac{{{_latex_node(right.children[0], conn, locale)}}}{{{_latex_node(right.children[1], conn, locale)}}}"
        # Constants/quantities whose LaTeX form ends in a control sequence
        # (e.g. `\pi`, `\theta`) need a thin space after a leading number
        # so the result reads `2 \pi` rather than `2\pi` (which visually
        # collides the digit with the symbol).
        if right.kind in ("constant", "quantity") and r.startswith("\\"):
            return f"{l}\\,{r}"
        return f"{l}{r}"
    if right.kind == "number":
        # If the left operand is a constant or quantity (whose LaTeX form
        # is a single symbol like G or a control sequence like \pi) and the
        # right is a number, the digit would visually collide with the
        # symbol — insert a thin space. (e.g. `\pi 2` rather than `\pi2`,
        # `G 2` rather than `G2`).
        if left.kind in ("constant", "quantity"):
            return f"{l}\\,{r}"
        return f"{l}{r}"
    return f"{l} {r}"


def _render_child(node: _Node, conn, locale: str) -> str:
    a = _latex_node(node.children[0], conn, locale)
    return _wrap(a, node.children[0], node, "child")


def _latex_prefix(node: _Node, conn, locale: str) -> str:
    # `abs` has no symbol and its operand must be scoped by `\left|...\right|`
    # rather than the usual `{...}` macro brace — `\left|` is itself an
    # opening delimiter, so wrapping the operand again would emit `\left|{{x}}\right|`.
    if node.operator_id == "abs":
        a = _render_child(node, conn, locale)
        return f"\\left|{a}\\right|"
    a = _render_child(node, conn, locale)
    sym = node.symbol or ""
    if sym == "-":
        return f"-{a}"
    # All prefix operators in the seed (\sin, \cos, \Delta,
    # \nabla, \mathrm{d}, \overline, \exp, ...) are LaTeX macros whose
    # argument is the next token (single char or `{...}`). Without braces,
    # `\sin \left(a+b\right)` would greedily grab `\left` and leave the real
    # argument dangling outside the macro's scope. Wrap the argument in
    # `{...}` so the macro always sees the correct scope. Redundant braces
    # (when the argument is already a single token like `\sin a`) are
    # stripped by TeX at render time.
    return f"{sym} {{{a}}}"


def _latex_postfix(node: _Node, conn, locale: str) -> str:
    a = _render_child(node, conn, locale)
    return f"{a}{node.symbol or ''}"


def _latex_relational(node: _Node, conn, locale: str) -> str:
    sym = node.symbol or "="
    # Chain (N-ary relational): emit `child0 sym child1 sym child2 ...` with
    # _wrap applied per pair. Operands wrap individually per the precedence
    # rule; the operator itself never wraps (it's just text between terms).
    if len(node.children) > 2:
        parts = []
        for i, child in enumerate(node.children):
            child_str = _latex_node(child, conn, locale)
            child_str = _wrap(child_str, child, node, "left" if i == 0 else "right")
            parts.append(child_str)
            if i < len(node.children) - 1:
                parts.append(f" {sym} ")
        return "".join(parts)
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
    """Return all formula_token rows for a formula, joined with quantity metadata.

    The `drop` sentinel quantity is filtered out — it has no real symbol,
    name, or unit to surface in the detail table; it only exists to blank
    out an operand slot in the rendered LaTeX.
    """
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


def _collect_qid_dimensions(conn):
    """Return {quantity_id: [dim_M, dim_L, ...]} for all quantities."""
    cols = DIMENSION_COLUMNS()
    return {
        r["id"]: [r[c] for c in cols]
        for r in conn.execute(f"SELECT id, {', '.join(cols)} FROM quantity")
    }


def _walk_dimensions(node, qid_to_dims, dims):
    """Sum dimensional exponents of every quantity under `node` into `dims`.

    Division/frac: inverts the right operand's sign.
    Pow: scales the base by the numeric exponent (defaulting to 1).
    add/sub: dimensions unchanged — only the first operand is walked.
    sin/cos/tan: dimensionless — nothing added.
    sqrt: halves the result of walking its argument.
    """
    if node.kind != "operator":
        if node.kind == "quantity":
            for i, v in enumerate(qid_to_dims.get(node.quantity_id, [])):
                dims[i] += v
        return
    op = node.operator_id
    if op in ("div", "frac"):
        _walk_dimensions(node.children[0], qid_to_dims, dims)
        # Flip sign on a snapshot, then add — keeps dims in-place.
        before = list(dims)
        _walk_dimensions(node.children[1], qid_to_dims, dims)
        for i in range(len(dims)):
            dims[i] = before[i] - (dims[i] - before[i])
    elif op == "pow":
        base, exp = node.children
        scale = exp.value if exp.kind == "number" and exp.value is not None else 1
        sub_dims = [0.0] * len(dims)
        _walk_dimensions(base, qid_to_dims, sub_dims)
        for i, v in enumerate(sub_dims):
            dims[i] += v * scale
    elif op in ("add", "sub"):
        _walk_dimensions(node.children[0], qid_to_dims, dims)
    elif op in ("sin", "cos", "tan"):
        pass
    elif op == "sqrt":
        sub_dims = [0.0] * len(dims)
        _walk_dimensions(node.children[0], qid_to_dims, sub_dims)
        for i, range_i in enumerate(dims):
            dims[i] += sub_dims[i] * 0.5
    else:
        for c in node.children:
            _walk_dimensions(c, qid_to_dims, dims)


def _lhs_dimensions(tree, qid_to_dims):
    """Sum dimensions on the LHS of a relational tree."""
    node = tree
    while node.kind == "operator" and node.operator_type == "relational":
        node = node.children[0]
    dims = [0.0] * len(DIMENSION_COLUMNS())
    _walk_dimensions(node, qid_to_dims, dims)
    return [int(round(d)) for d in dims]


def _compute_dimensions(conn, tree, empty_default):
    """Run LHS-dimensions on a parsed RPN tree; return `empty_default` on no tree."""
    if tree is None:
        return empty_default
    return _lhs_dimensions(tree, _collect_qid_dimensions(conn))


def compute_formula_dimensions(conn, formula_id):
    """Compute dimensions from the LHS of a stored formula.

    The LHS is identified by walking the RPN tree and taking the first
    operand of the topmost `=` operator.
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
    return _compute_dimensions(conn, tree, [])


def compute_rpn_dimensions(conn, tokens):
    """Like compute_formula_dimensions, but works on an in-memory RPN token list."""
    if not tokens:
        return [0.0] * len(DIMENSION_COLUMNS())
    try:
        tree = _evaluate_rpn(conn, tokens)
    except Exception:
        return [0.0] * len(DIMENSION_COLUMNS())
    return _compute_dimensions(conn, tree, [0.0] * len(DIMENSION_COLUMNS()))


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


def fetch_all_constants(conn):
    """Return all constants with id, name, and symbol."""
    return conn.execute(
        """
        SELECT id, name, symbol, value
        FROM constant
        ORDER BY id
        """
    ).fetchall()


def fetch_all_operators(conn):
    """Return all operators with id, symbol, arity, precedence, etc."""
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


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

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


def fetch_formula_qty_const_tokens(conn):
    """Return {formula_id: [id, id, ...]} of quantity/constant tokens in
    position order. Each id is `quantity:<id>` or `constant:<id>` so the two
    namespaces never collide when sorting."""
    rows = conn.execute(
        """
        SELECT formula_id, position, token_kind, quantity_id, constant_id
        FROM formula_token
        WHERE token_kind IN ('quantity', 'constant')
        ORDER BY formula_id, position
        """
    ).fetchall()
    out = {}
    for r in rows:
        if r["token_kind"] == "quantity":
            token = f"quantity:{r['quantity_id']}"
        else:
            token = f"constant:{r['constant_id']}"
        out.setdefault(r["formula_id"], []).append(token)
    return out


def _formula_sort_key(row, sort_key, locale, qty_const_tokens, tree_order):
    """Return a sort key for a formula row given the chosen sort mode."""
    if sort_key == "id":
        return (row["id"],)
    if sort_key == "name":
        return (localise(row["name"], locale).lower(), row["id"])
    if sort_key == "diff_asc":
        return (row.get("difficulty") or 0, row["id"])
    if sort_key == "diff_desc":
        return (-(row.get("difficulty") or 0), row["id"])
    if sort_key in ("topic_tree", "topic_alpha"):
        topic = row.get("topic_id") or ""
        if sort_key == "topic_tree":
            topic_index = tree_order.get(topic, 10 ** 9)
            return (topic_index, topic, row["id"])
        return (topic, row["id"])
    if sort_key == "qty":
        tokens = qty_const_tokens.get(row["id"], [])
        return (tokens, row["id"])
    return (row["id"],)


def sort_formulas(conn, rows, sort_key, locale="en-us"):
    """Sort formula dict-rows in-place and return the list."""
    if sort_key not in FORMULA_SORT_KEYS:
        sort_key = DEFAULT_FORMULA_SORT
    qty_const_tokens = fetch_formula_qty_const_tokens(conn)
    if sort_key == "topic_tree":
        tree_order = _topic_tree_order()
    else:
        tree_order = {}
    key_fn = lambda r: _formula_sort_key(r, sort_key, locale, qty_const_tokens, tree_order)
    return sorted(rows, key=key_fn)


def _topic_tree_order():
    """{topic_id: depth-first index} over the science tree."""
    tree = load_tree()
    order = {}
    counter = [0]

    def visit(node):
        order[node["id"]] = counter[0]
        counter[0] += 1
        for child in (node.get("children") or []):
            visit(child)

    for root in tree:
        visit(root)
    return order


def _quantity_sort_key(row, sort_key, locale, tree_order):
    if sort_key == "id":
        return (row["id"],)
    if sort_key == "name":
        return (localise(row["name"], locale).lower(), row["id"])
    if sort_key == "diff_asc":
        return (row.get("difficulty") or 0, row["id"])
    if sort_key == "diff_desc":
        return (-(row.get("difficulty") or 0), row["id"])
    if sort_key in ("topic_tree", "topic_alpha"):
        topic = row.get("topic_id") or ""
        if sort_key == "topic_tree":
            topic_index = tree_order.get(topic, 10 ** 9)
            return (topic_index, topic, row["id"])
        return (topic, row["id"])
    return (row["id"],)


def sort_quantities(rows, sort_key, locale="en-us"):
    """Sort quantity dict-rows in-place and return the list."""
    if sort_key not in QUANTITY_SORT_KEYS:
        sort_key = DEFAULT_QUANTITY_SORT
    if sort_key == "topic_tree":
        tree_order = _topic_tree_order()
    else:
        tree_order = {}
    key_fn = lambda r: _quantity_sort_key(r, sort_key, locale, tree_order)
    return sorted(rows, key=key_fn)


def sort_search_rows(conn, rows, sort_key, locale="en-us"):
    """Sort mixed search hits (kind, id, display_name). The default
    `relevance` preserves the SQL order (caller passes rows already ranked).
    For other keys, look up the underlying entity for fields like difficulty
    and topic, plus quantity/constant tokens for the `qty` key.
    """
    if sort_key not in SEARCH_SORT_KEYS:
        sort_key = DEFAULT_SEARCH_SORT
    if sort_key == "relevance":
        return list(rows)

    formula_ids = [r[1] for r in rows if r[0] == "formula"]
    quantity_ids = [r[1] for r in rows if r[0] == "quantity"]
    unit_ids = [r[1] for r in rows if r[0] == "unit"]

    formula_meta = {}
    if formula_ids:
        for fr in conn.execute(
            "SELECT id, name, topic, difficulty FROM formula WHERE id IN ({})".format(
                ",".join("?" for _ in formula_ids)
            ),
            formula_ids,
        ).fetchall():
            formula_meta[fr["id"]] = dict(fr)

    quantity_meta = {}
    if quantity_ids:
        for qr in conn.execute(
            "SELECT id, name, topic, difficulty FROM quantity WHERE id IN ({})".format(
                ",".join("?" for _ in quantity_ids)
            ),
            quantity_ids,
        ).fetchall():
            quantity_meta[qr["id"]] = dict(qr)

    unit_meta = {}
    if unit_ids:
        for ur in conn.execute(
            """
            SELECT u.id, u.name, u.quantity_id, q.name AS quantity_name,
                   q.topic AS quantity_topic, q.difficulty AS quantity_difficulty
            FROM unit u LEFT JOIN quantity q ON q.id = u.quantity_id
            WHERE u.id IN ({})
            """.format(",".join("?" for _ in unit_ids)),
            unit_ids,
        ).fetchall():
            unit_meta[ur["id"]] = dict(ur)

    qty_const_tokens = fetch_formula_qty_const_tokens(conn)
    tree_order = _topic_tree_order() if sort_key in ("topic_tree", "topic_alpha") else {}

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

    return sorted(rows, key=key)


def compute_all_formula_dimensions(conn, formula_ids=None):
    """Return {formula_id: {dim_M, dim_L, ...}} for all or given formulas.

    If *formula_ids* is provided, only those IDs are computed (useful
    when preceding filters have already narrowed the set). Otherwise
    every formula in the database is evaluated.

    Evaluates the RPN tree for each formula to correctly compute
    LHS dimensions (handles frac, pow, etc.). Formulas without a
    valid LHS or with no tokens get all-zero dimensions.
    """
    cols = DIMENSION_COLUMNS()
    if formula_ids is not None:
        all_ids = formula_ids
    else:
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


def build_create_sql(conn, name_en, topic, difficulty, equation, overrides=None, description=None, links=None, translations=None):
    """Build the two INSERT SQL strings for a brand-new formula.

    `overrides` is a mapping keyed by "quantity_id|alias" (matching what the
    /create page uses) and containing {symbol, name, label} strings which
    are stored as JSON i18n blobs.

    `links` is an optional list of URL strings; it is stored as a plain
    JSON array (not per-locale).

    `translations` is an optional mapping of locale code → {
        name, description, overrides
    }. Each entry's non-empty fields are merged into the per-row i18n
    blobs so the stored JSON looks like {"en-us": ..., "<locale>": ...}.
    The English (en-us) values are always sourced from the top-level
    `name_en`/`description`/`links`/`overrides` arguments and are not
    re-overwritten by a translations["en-us"] entry.

    Returns (formula_sql, token_sql) on success. Raises ValueError with a
    user-friendly message if name/topic/equation are missing or the
    equation fails to parse.
    """
    if not name_en or not name_en.strip():
        raise ValueError("name is required")
    if not topic or not topic.strip():
        raise ValueError("topic is required")
    if not equation or not equation.strip():
        raise ValueError("equation is required")
    difficulty = int(difficulty) if difficulty not in (None, "") else 2
    if difficulty < 1 or difficulty > 10:
        raise ValueError("difficulty must be 1..10")

    formula_id = re.sub(r"[^a-z0-9]+", "_", name_en.strip().lower()).strip("_")
    if not formula_id:
        raise ValueError("name must contain at least one alphanumeric character")

    tokens = parse_equation(conn, equation)
    overrides = overrides or {}
    translations = translations or {}

    # The formula-level i18n blobs are dicts of {locale: value}. en-us comes
    # from the top-level arguments; other locales are merged in from translations.
    def sql_str(s):
        return "NULL" if s is None else "'" + str(s).replace("'", "''") + "'"

    def add_locale(blob, value, locale):
        """Return a JSON dict string with `locale: value` merged into `blob`."""
        obj = {}
        if blob:
            try:
                parsed = json.loads(blob)
                if isinstance(parsed, dict):
                    obj = parsed
            except (ValueError, TypeError):
                obj = {}
        obj[locale] = value
        return json.dumps(obj, ensure_ascii=False)

    name_json = json.dumps({"en-us": name_en.strip()}, ensure_ascii=False) if name_en else None
    desc_json = json.dumps({"en-us": description}, ensure_ascii=False) if description else None
    # Links are stored as a plain JSON array of URL strings, e.g.
    # ["https://en.wikipedia.org/wiki/Force", ...].
    links_json = json.dumps(links, ensure_ascii=False) if links else None
    tr_overrides_by_loc = {}
    if translations:
        for loc, tr in translations.items():
            if not isinstance(tr, dict) or loc == "en-us":
                continue
            t_name = tr.get("name")
            if t_name:
                name_json = add_locale(name_json, t_name.strip(), loc)
            t_desc = tr.get("description")
            if t_desc:
                desc_json = add_locale(desc_json, t_desc, loc)
            t_ov = tr.get("overrides") or {}
            if t_ov:
                tr_overrides_by_loc[loc] = t_ov

    formula_sql = (
        "INSERT OR IGNORE INTO formula (id, name, topic, difficulty, description, links) VALUES\n"
        f"({sql_str(formula_id)}, {sql_str(name_json)}, "
        f"{sql_str(topic)}, {difficulty}, {sql_str(desc_json)}, "
        f"{sql_str(links_json)});"
    )

    # Per-token overrides merge en-us (from `overrides`) with each locale's
    # value (from `tr_overrides_by_loc`); an English value is never overridden
    # by a translation entry.
    def i18n_override(field, key):
        base = (overrides.get(key) or {}).get(field)
        per_locale = {loc: (t_ov.get(key) or {}).get(field)
                      for loc, t_ov in tr_overrides_by_loc.items()
                      if (t_ov.get(key) or {}).get(field)}
        if not base and not per_locale:
            return "NULL"
        obj = {}
        if base:
            obj["en-us"] = base
        obj.update(per_locale)
        return sql_str(json.dumps(obj, ensure_ascii=False))

    # fields indexed by position in the quantity INSERT column list
    QTY_OVERRIDE_FIELDS = ("label", "symbol", "name")

    rows = []
    for pos, tok in enumerate(tokens, start=1):
        kind = tok["token_kind"]
        if kind == "number":
            rows.append(
                f"({sql_str(formula_id)}, {pos}, 'number', "
                f"NULL, NULL, NULL, {tok['value']}, NULL, NULL, NULL)"
            )
        elif kind == "quantity":
            qid = tok["quantity_id"]
            key = qid + "|" + (tok.get("label") or "") + "|" + str(pos)
            overrides_sql = ", ".join(
                i18n_override(field, key) for field in QTY_OVERRIDE_FIELDS
            )
            rows.append(
                f"({sql_str(formula_id)}, {pos}, 'quantity', "
                f"{sql_str(qid)}, NULL, NULL, NULL, {overrides_sql})"
            )
        elif kind == "constant":
            rows.append(
                f"({sql_str(formula_id)}, {pos}, 'constant', "
                f"NULL, {sql_str(tok['constant_id'])}, NULL, NULL, NULL, NULL, NULL)"
            )
        else:  # operator
            op_id = tok["operator_id"]
            if op_id in ("paren_open", "paren_close"):
                raise ValueError("unbalanced parentheses")
            rows.append(
                f"({sql_str(formula_id)}, {pos}, 'operator', "
                f"NULL, NULL, {sql_str(op_id)}, NULL, NULL, NULL, NULL)"
            )

    token_sql = (
        "INSERT OR IGNORE INTO formula_token\n"
        "  (formula_id, position, token_kind, quantity_id, constant_id,\n"
        "   operator_id, value, label, symbol_overwrite, quantity_name_overwrite)\n"
        "VALUES\n"
        + ",\n".join(rows)
        + ";"
    )
    return formula_sql, token_sql


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
