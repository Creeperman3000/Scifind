#!/usr/bin/env python3
"""Scifind web app — Flask interface to the formula database."""

import gzip
import html as html_module
import io
import json
import logging
import os
import re
import secrets
import sqlite3
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from flask import Flask, render_template, request, g, Response, redirect, session
from markupsafe import Markup

_PROJECT_DIR = Path(__file__).resolve().parent
_LOCALE_DIR = _PROJECT_DIR / "locales"
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from scifind_lib import (
    open_database,
    database_path,
    render_formula,
    format_dimensions_latex,
    format_default_unit_html,
    format_default_unit_symbol,
    localise,
    fetch_formula,
    fetch_formula_related,
    fetch_formula_detail_items,
    render_variable_base,
    parse_quantity_name_markers,
    fetch_quantity,
    fetch_quantity_units,
    fetch_quantity_formulas_by_side,
    fetch_quantity_related_formulas,
    fetch_quantities_by_ids,
    compute_formula_dimensions,
    compute_all_formula_dimensions,
    fetch_formulas_with_all_quantities,
    fetch_formulas_with_any_quantity,
    fetch_si_unit_symbol,
    fetch_unit,
    build_dimension_symbol_maps,
    fetch_all_quantities,
    fetch_all_formulas,
    search_headings,
    suggest_headings,
    export_to_csv_directory,
    export_to_xlsx,
    export_to_ods,
    _unit_name_map,
    _unit_symbol_map,
    _unit_quantity_map,
    render_symbol,
    _dimension_matches,
    DIMENSION_SYMBOLS,
    dimension_quantity_ids,
    extract_dimensions_from_row,
    locale_sibilants,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SCIFIND_SECRET_KEY") or secrets.token_hex(24)
app.config["MAX_CONTENT_LENGTH"] = (
    int(os.environ.get("SCIFIND_MAX_UPLOAD_MB", "32")) * 1024 * 1024
)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 365 * 86400


_GZIP_TYPES = ('text/', 'application/json', 'application/javascript')


@app.after_request
def gzip_response(response):
    accept = request.headers.get('Accept-Encoding', '')
    if 'gzip' not in accept:
        return response
    ct = response.content_type or ''
    if not ct.startswith(_GZIP_TYPES):
        return response
    response.direct_passthrough = False
    original = response.get_data()
    if len(original) < 200:
        return response
    compressed = gzip.compress(original)
    response.set_data(compressed)
    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Content-Length'] = len(compressed)
    return response


MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 10
SEARCH_QUERY_MAX_LENGTH = 200
SUGGEST_QUERY_MAX_LENGTH = 50

logger = logging.getLogger("scifind")


# ---------------------------------------------------------------------------
# Filter parsing
# ---------------------------------------------------------------------------

@dataclass
class FilterState:
    ids: list = field(default_factory=list)
    ids_provided: bool = False
    exclude_all: bool = False
    quantity_ids: list = field(default_factory=list)
    quantity_mode: str = "and"
    diff_min: int = MIN_DIFFICULTY
    diff_max: int = MAX_DIFFICULTY
    dimension_filter: dict = field(default_factory=dict)
    dim_mode: str = "and"
    base_quantity_only: int = 0

    @property
    def has_dimension_filter(self) -> bool:
        return any(d.get("val") is not None for d in self.dimension_filter.values())


def _safe_int(value, default=None):
    if not value:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _csv_list(value):
    """Split a comma-separated query value into a list of stripped non-empty parts."""
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_filter_state(args, path="") -> FilterState:
    mode_switched_raw = args.get("mode_switched", "")
    mode_switched = set(_csv_list(mode_switched_raw)) if mode_switched_raw else set()
    is_qty_page = "/quantities" in path or "/quantity/" in path or "/unit/" in path
    if mode_switched:
        dim_mode = "or" if "dim" in mode_switched else "and"
        quantity_mode = "or" if ("qty" if is_qty_page else "fml") in mode_switched else "and"
    else:
        dim_mode = args.get("dim_mode", "and")
        if dim_mode not in ("and", "or"):
            dim_mode = "and"
        quantity_mode = args.get("qty_mode", "and")
        if quantity_mode not in ("and", "or"):
            quantity_mode = "and"

    dimension_filter = {}
    for symbol in DIMENSION_SYMBOLS():
        dimension_filter[symbol] = {"op": "eq", "val": None}
        for op in ("eq", "geq", "leq"):
            v = _safe_int(args.get(f"{symbol}_{op}"))
            if v is not None:
                dimension_filter[symbol] = {"op": op, "val": v}
                break

    ids_raw = args.get("ids")
    return FilterState(
        ids=_csv_list(ids_raw) if ids_raw is not None else [],
        ids_provided=ids_raw is not None,
        exclude_all=args.get("exclude_all") == "1",
        quantity_ids=_csv_list(args.get("qty", "")),
        quantity_mode=quantity_mode,
        diff_min=_safe_int(args.get("diff_min"), MIN_DIFFICULTY),
        diff_max=_safe_int(args.get("diff_max"), MAX_DIFFICULTY),
        dimension_filter=dimension_filter,
        dim_mode=dim_mode,
        base_quantity_only=_safe_int(args.get("is_dim"), 0) or 0,
    )


# ---------------------------------------------------------------------------
# Science tree helpers
# ---------------------------------------------------------------------------

TREE_PATH = _PROJECT_DIR / "tree.json"
_tree_cache = None


def _sciences_tree():
    global _tree_cache
    if _tree_cache is None:
        try:
            with open(TREE_PATH) as f:
                _tree_cache = json.load(f).get("sciences", [])
        except (OSError, ValueError) as exc:
            logger.warning("Failed to load tree.json: %s", exc)
            _tree_cache = []
    return _tree_cache


def _all_ids(tree):
    """Return every id anywhere in the sciences tree."""
    out = set()
    def walk(node):
        out.add(node["id"])
        for child in (node.get("children") or []):
            walk(child)
    for root in tree:
        walk(root)
    return out


def _leaf_ids(node):
    """Return every leaf id under a node (a leaf has no children)."""
    if not node.get("children"):
        return {node["id"]}
    leaves = set()
    for child in node["children"]:
        leaves |= _leaf_ids(child)
    return leaves


def _all_descendant_ids(node):
    """Return all descendant node ids including the node itself."""
    ids = {node["id"]}
    for child in (node.get("children") or []):
        ids |= _all_descendant_ids(child)
    return ids


def _expand_to_topics(tree, ids):
    """Expand a set of tree-level ids to all leaf ids they cover.

    Unknown ids in the input are silently dropped.
    """
    idset = set(ids)
    covered = set()

    def walk(node):
        nonlocal covered
        if node["id"] in idset:
            covered |= _all_descendant_ids(node)
            return
        for child in (node.get("children") or []):
            walk(child)

    for root in tree:
        walk(root)
    return covered


def _compress_selection(tree, ids):
    """Replace a set of leaf ids with the minimal ancestor covering set."""
    idset = set(ids)
    covered_leaves = set()

    def gather(node):
        nonlocal covered_leaves
        if node["id"] in idset:
            covered_leaves |= _leaf_ids(node)
            return
        for child in (node.get("children") or []):
            gather(child)

    for root in tree:
        gather(root)

    out = set()

    def collapse(node):
        nonlocal out
        leaves = _leaf_ids(node)
        if leaves <= covered_leaves:
            out.add(node["id"])
            return
        for child in (node.get("children") or []):
            collapse(child)

    for root in tree:
        collapse(root)
    return out


def _tree_name_map(tree, locale):
    """Flatten (id → localised name) using the current locale."""
    out = {}
    def walk(node):
        out[node["id"]] = localise(
            node.get("translations") or {}, locale,
        )
        for child in (node.get("children") or []):
            walk(child)
    for root in tree:
        walk(root)
    return out


def _topic_path(tree, topic):
    """Return the ids along the path to a topic, or None if not in the tree."""
    def find(node, ancestors=()):
        if node["id"] == topic:
            return ancestors + (topic,)
        for child in (node.get("children") or []):
            result = find(child, ancestors + (node["id"],))
            if result:
                return result
    for root in tree:
        result = find(root)
        if result:
            return result
    return None


def _jstree_data(tree, name_map, compressed, exclude_all=False, ids_provided=False):
    """Build JSON for the sidebar's jsTree widget."""
    if not compressed and not exclude_all and not ids_provided:
        compressed = {r["id"] for r in tree} if tree else set()
    def conv(node):
        return {
            "id": node["id"],
            "text": name_map.get(node["id"], node["id"]),
            "state": {"checked": node["id"] in compressed, "opened": True},
            "children": [conv(c) for c in (node.get("children") or [])],
        }
    return [conv(r) for r in tree] if tree else []


def _attach_breadcrumbs(row, locale):
    """Add a breadcrumbs list to a row (root-first ordered ancestor chain)."""
    tree = _sciences_tree()
    name_map = _tree_name_map(tree, locale)
    topic = row.get("topic_id")
    path = _topic_path(tree, topic)
    if path:
        row["breadcrumbs"] = [{"id": n, "name": name_map.get(n, n)} for n in path]
    else:
        row["breadcrumbs"] = []
    return row


def _filtered_ids_for_query(tree, ids):
    """Convert a set of tree-level ids into the full set of leaf topic ids."""
    valid = [i for i in ids if i in _all_ids(tree)]
    return _expand_to_topics(tree, valid)


# ---------------------------------------------------------------------------
# Heading text
# ---------------------------------------------------------------------------

SUPERSCRIPT_DIGITS = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")

_LATEX_TEXTCMD_RE = re.compile(r"\\(?:mathrm|text)\{([^}]*)\}")


def _strip_textcmd(text):
    return _LATEX_TEXTCMD_RE.sub(r"\1", text)


def _join_names(names, locale="en-us", conj_key="heading.and"):
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    conj = _ui_lookup(locale, conj_key)
    if conj == conj_key:
        conj = "and"
    if len(names) == 2:
        return f"{names[0]} {conj} {names[1]}"
    return f"{', '.join(names[:-1])} {conj} {names[-1]}"

def _sibilant_prep(word, prep, locale):
    sibs = locale_sibilants(locale)
    chars = sibs.get("chars", [])
    suffix = sibs.get("preposition", {}).get("suffix", "")
    if chars and suffix and word and word[0].lower() in chars:
        return prep + suffix
    return prep


def _tree_order(tree):
    """Depth-first index for each tree node id (used to sort compressed ids)."""
    order = {}
    counter = [0]
    def walk(node):
        order[node["id"]] = counter[0]
        counter[0] += 1
        for c in (node.get("children") or []):
            walk(c)
    for root in tree:
        walk(root)
    return order


def _tree_gen_map(tree):
    """Map of node id → 'cs-cz-gen' translation (Czech genitive form)."""
    out = {}
    def walk(node):
        g = (node.get("translations") or {}).get("cs-cz-gen")
        if g:
            out[node["id"]] = g
        for c in (node.get("children") or []):
            walk(c)
    for root in tree:
        walk(root)
    return out


def _heading_from_compressed(view_label, compressed, name_map, locale, fs,
                             dim_mode="dim", dimension_caches=None,
                             active_quantity_names=None):
    """Render the page heading.

    Format: {view_label} from {topics} with {quantity_label} {quantities}
            where difficulty is {difficulty} and {dimensions}
    """
    def _loc_ui(key):
        return _ui_lookup(locale, key)

    parts = [view_label]

    # --- topics ---
    if compressed:
        tree = _sciences_tree()
        order = _tree_order(tree)
        gen_map = _tree_gen_map(tree) if locale == "cs-cz" else {}
        seen = set()
        topic_names = []
        for nid in sorted(compressed, key=lambda x: order.get(x, 9**9)):
            n = gen_map.get(nid) or name_map.get(nid, nid)
            if n not in seen:
                topic_names.append(n)
                seen.add(n)
        if topic_names:
            joined = _join_names(topic_names, locale)
            prep = _sibilant_prep(joined, _loc_ui("heading.from"), locale)
            parts.append(f"{prep} {joined}")

    # --- quantities ---
    if active_quantity_names:
        count = len(active_quantity_names)
        q_label = _loc_ui("heading.quantity") if count == 1 else _loc_ui("heading.quantities")
        q_conj = "heading.or" if fs.quantity_mode == "or" else "heading.and"
        joined = _join_names(active_quantity_names, locale, q_conj)
        prep = _sibilant_prep(joined, _loc_ui("heading.with"), locale)
        parts.append(f"{prep} {q_label} {joined}")

    # --- difficulty ---
    diff_str = ""
    if fs.diff_min > MIN_DIFFICULTY or fs.diff_max < MAX_DIFFICULTY:
        where = _loc_ui("heading.where_difficulty_is")
        if fs.diff_min == fs.diff_max:
            diff_str = f"{where} {fs.diff_min}"
        else:
            diff_str = f"{where} {fs.diff_min}\u2013{fs.diff_max}"

    # --- dimensions ---
    caches = dimension_caches or {}
    x_map = caches.get("var" if dim_mode == "unit" else dim_mode, {})
    y_map = caches.get("unit", {})
    op_syms = {"eq": "=", "geq": "\u2265", "leq": "\u2264"}
    dim_parts = []
    for symbol in DIMENSION_SYMBOLS():
        d = fs.dimension_filter.get(symbol, {})
        value = d.get("val")
        if value is None:
            continue
        op = d.get("op", "eq")
        x_sym = _strip_textcmd(x_map.get(symbol, symbol))
        y_sym = _strip_textcmd(y_map.get(symbol, symbol))
        dv = str(value).translate(SUPERSCRIPT_DIGITS)
        dim_parts.append(f"{x_sym} {op_syms[op]} {y_sym}{dv}")
    dim_str = ""
    if dim_parts:
        d_conj = "heading.or" if fs.dim_mode == "or" else "heading.and"
        joined = _join_names(dim_parts, locale, d_conj)
        dim_str = f"{_loc_ui('heading.where_dimensions_are')} {joined}"

    # --- combine difficulty + dimensions ---
    if diff_str and dim_str:
        parts.append(f"{diff_str} {_loc_ui('heading.and')} {dim_str}")
    elif diff_str:
        parts.append(diff_str)
    elif dim_str:
        parts.append(dim_str)

    text = " ".join(parts)
    return text[0].upper() + text[1:] if text else f"{_loc_ui('heading.all')} {view_label}"


# ---------------------------------------------------------------------------
# Locale
# ---------------------------------------------------------------------------

_available_locales = None
_lang_to_locale = None

DEFAULT_LOCALE_FALLBACK = {
    "meta": {"name": "US English", "acceptLanguage": "en-US"},
    "ui": {},
}


def _scan_locales():
    """Discover available locale files and build Accept-Language mapping."""
    global _available_locales, _lang_to_locale
    if _available_locales is not None:
        return
    _available_locales = {}
    _lang_to_locale = {}
    if _LOCALE_DIR.is_dir():
        for path in sorted(_LOCALE_DIR.glob("*.json")):
            locale = path.stem
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue
            meta = data.get("meta", {})
            _available_locales[locale] = data
            lang = meta.get("acceptLanguage", locale)
            _lang_to_locale[lang] = locale
    if "en-us" not in _available_locales:
        _available_locales["en-us"] = DEFAULT_LOCALE_FALLBACK
    _lang_to_locale.setdefault("en-US", "en-us")
    _lang_to_locale.setdefault("en", "en-us")


def _resolve_locale_from_header(header):
    """Match Accept-Language header to best available locale."""
    if not header:
        return "en-us"
    for part in header.split(","):
        code = part.split(";")[0].strip()[:5]
        if code in _lang_to_locale:
            return _lang_to_locale[code]
        base = code[:2]
        if base in _lang_to_locale:
            return _lang_to_locale[base]
    return "en-us"


@app.before_request
def detect_locale():
    _scan_locales()
    locale = request.args.get("locale") or request.cookies.get("sf_locale")
    if locale and locale in _available_locales:
        session["locale"] = locale
    if session.get("locale") in _available_locales:
        g.locale = session["locale"]
    else:
        g.locale = _resolve_locale_from_header(
            request.headers.get("Accept-Language", "")
        )

    dim_mode = request.args.get("dim_mode") or request.cookies.get("sf_dim_mode")
    if dim_mode in ("dim", "var", "unit"):
        session["dim_mode"] = dim_mode
    g.dim_mode = session.get("dim_mode", "dim")


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------

_NOT_INITIALISED = (
    "<h1>Database not initialised</h1>"
    "<p>The SQLite database at <code>{}</code> could not be opened or has no tables.</p>"
    "<p>Run <code>python scifind_cli.py init</code> to create and seed it, "
    "then refresh this page.</p>"
)


def _database_is_initialised(db):
    try:
        row = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='formula'"
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return bool(row)


def _bootstrap_database():
    """Apply schema and seed data on first run when the DB has no tables."""
    conn = open_database()
    try:
        if _database_is_initialised(conn):
            return
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript((_PROJECT_DIR / "schema.sql").read_text(encoding="utf-8"))
        conn.executescript((_PROJECT_DIR / "seed.sql").read_text(encoding="utf-8"))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        logger.info("Database initialised at %s", database_path())
    finally:
        conn.close()


_bootstrap_database()


def get_db():
    if "db" not in g:
        g.db = open_database()
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.before_request
def ensure_db_open():
    if request.endpoint in (None, "static"):
        return
    try:
        db = get_db()
    except sqlite3.DatabaseError as exc:
        logger.warning("Database open failed: %s", exc)
        return _uninitialised_response()
    if not _database_is_initialised(db):
        return _uninitialised_response()


def _uninitialised_response():
    return (_NOT_INITIALISED.format(os.environ.get("SCIFIND_DB", "scifind.db")), 503)


# ---------------------------------------------------------------------------
# Template globals
# ---------------------------------------------------------------------------

def _ui_lookup(locale, key):
    """Look up a dotted UI key ('category.child') in the nested locale ui dict."""
    _scan_locales()
    parts = key.split(".", 1)
    if len(parts) == 2:
        cat, child = parts
        for ui in (_available_locales.get(locale, {}).get("ui", {}),
                   _available_locales.get("en-us", {}).get("ui", {})):
            val = ui.get(cat, {}).get(child)
            if val is not None:
                return val
    return key


@app.template_global()
def _(data):
    """Resolve a localized string.

    If *data* looks like JSON (starts with ``{``), it is treated as a DB
    i18n object (``{"en-us": "...", "cs-cz": "..."}``) and resolved against
    the current locale.  Otherwise it is treated as a UI-string key looked
    up in the current locale file.  Falls back to en-us, then to the raw
    value.
    """
    loc = g.locale if hasattr(g, "locale") else "en-us"
    s = (data or "").strip()
    if s.startswith("{"):
        result = localise(s, loc)
        if result:
            return result
    return _ui_lookup(loc, data)


app.template_global()(render_symbol)


def _get_dimension_caches():
    if 'dim_caches' not in g:
        try:
            var_map, unit_map, dim_map = build_dimension_symbol_maps(get_db())
            g.dim_caches = {"var": var_map, "unit": unit_map, "dim": dim_map}
        except sqlite3.OperationalError as exc:
            logger.warning("Dimension symbol lookup failed: %s", exc)
            g.dim_caches = {"var": {}, "unit": {}, "dim": {}}
    return g.dim_caches


def _get_unit_name_map():
    if 'unit_name_map' not in g:
        locale = g.get("locale", "en-us")
        g.unit_name_map = _unit_name_map(get_db(), locale)
    return g.unit_name_map


def _get_unit_symbol_map():
    if 'unit_symbol_map' not in g:
        g.unit_symbol_map = _unit_symbol_map(get_db())
    return g.unit_symbol_map


def _unit_name_link(unit_id):
    """Render a unit id as an HTML link to its detail page, with a localised name."""
    names = _get_unit_name_map()
    if unit_id in names:
        return Markup(f'<a href="/unit/{html_module.escape(unit_id)}">{html_module.escape(names[unit_id])}</a>')
    return Markup(html_module.escape(unit_id.replace("_", " ").title()))


def _render_unit_html(default_unit, locale):
    names = _get_unit_name_map()
    first = [True]
    def unit_name(uid):
        name = names.get(uid, uid.replace("_", " ")).lower()
        if first[0]:
            first[0] = False
            return name[0].upper() + name[1:]
        return name
    return format_default_unit_html(
        default_unit,
        unit_url=lambda uid: f"/unit/{uid}",
        unit_name=unit_name,
        locale=locale,
        unit_quantity_map=_unit_quantity_map(get_db()),
    )


def _render_unit_symbol(default_unit):
    symbols = _get_unit_symbol_map()
    return format_default_unit_symbol(
        default_unit,
        unit_symbol=lambda uid: render_symbol(symbols.get(uid, uid)),
    )


# ---------------------------------------------------------------------------
# Context processor
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    locale = g.get("locale", "en-us")
    tree = _sciences_tree()
    db = None
    try:
        db = get_db()
    except sqlite3.OperationalError as exc:
        logger.warning("Database unavailable: %s", exc)
    fs = parse_filter_state(request.args, request.path)
    name_map = _tree_name_map(tree, locale)
    compressed = _compress_selection(tree, fs.ids)
    tree_json = _jstree_data(tree, name_map, compressed, fs.exclude_all, ids_provided=fs.ids_provided)
    path = request.path
    current_view = (
        "quantities"
        if path == "/quantities" or path.startswith(("/quantity/", "/unit/"))
        else "formulas"
    )
    all_quantities_for_filter = []
    dimension_caches = {"var": {}, "unit": {}, "dim": {}}
    if db is not None:
        try:
            for q in fetch_all_quantities(db):
                all_quantities_for_filter.append({
                    "id": q["id"],
                    "name": localise(q["name"], locale),
                    "symbol": q["symbol"] or "",
                })
        except sqlite3.OperationalError as exc:
            logger.warning("Quantity table unavailable: %s", exc)
        dimension_caches = _get_dimension_caches()

    dim_mode = g.get("dim_mode", "dim")
    dim_symbols = dimension_caches.get(dim_mode, dimension_caches.get("dim", {}))

    _scan_locales()
    locale_list = [
        {"code": code, "name": data.get("meta", {}).get("name", code)}
        for code, data in _available_locales.items()
    ]
    locale_ui = _available_locales.get(locale, {}).get("ui", {})

    return dict(
        tree_json=tree_json,
        diff_min=fs.diff_min,
        diff_max=fs.diff_max,
        current_view=current_view,
        dim_filter=fs.dimension_filter,
        dim_mode=fs.dim_mode,
        qty_mode=fs.quantity_mode,
        all_quantities_for_filter=all_quantities_for_filter,
        dim_symbols=dim_symbols,
        dimension_symbol_list=DIMENSION_SYMBOLS() if db else [],
        available_locales=locale_list,
        locale_ui=locale_ui,
    )


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect("/formulas")


@app.route("/base-units")
def base_units_page():
    return redirect("/quantities?is_dim=1")


def _build_formula_detail_items(db, formula_id, locale):
    """Build the formula detail table data from formula_token rows."""
    result = []
    for item in fetch_formula_detail_items(db, formula_id):
        item = dict(item)
        qid = item.get("quantity_id")
        if not qid:
            continue

        symbol_latex = render_variable_base(item, locale)

        qty_name = item.get("quantity_name") or qid.replace("_", " ").title()
        orig_symbol = (item.get("quantity_symbol") or "").strip()
        overwrite_raw = item.get("symbol_overwrite") or ""
        overwrite = localise(overwrite_raw, locale)
        has_overwrite = bool(overwrite and orig_symbol and overwrite != orig_symbol)

        qno_raw = localise(item.get("quantity_name_overwrite") or "", locale)

        qlink = (
            f'<a href="/quantity/{html_module.escape(qid)}">'
            f"{html_module.escape(qty_name)}</a>"
        )

        paren_parts = []
        if has_overwrite and orig_symbol:
            paren_parts.append(f"${orig_symbol}$")

        if qno_raw:
            marker_ids = {m.split('|')[0].lower().replace(' ', '_')
                          for m in re.findall(r'\[([^\]]+)\]', qno_raw)}
            if qid in marker_ids:
                # qno has [quantity_id] marker — resolve links
                name_html = parse_quantity_name_markers(qno_raw)
            else:
                # qno is plain text — use as name, show orig symbol + quantity name in parens
                name_html = html_module.escape(qno_raw)
                if has_overwrite and orig_symbol:
                    paren_parts.append(qlink)
        else:
            name_html = qlink

        paren_html = f"({' '.join(paren_parts)})" if paren_parts else ""
        default_unit = item.get("default_unit")

        result.append({
            "symbol_latex": symbol_latex,
            "name_html": Markup(name_html) if name_html else "",
            "paren_html": Markup(paren_html) if paren_html else "",
            "default_unit_html": Markup(_render_unit_html(default_unit, locale)) if default_unit else "",
            "default_unit_symbol_latex": _render_unit_symbol(default_unit) if default_unit else "",
        })

    return result


@app.route("/formula/<formula_id>")
def formula_detail(formula_id):
    db = get_db()
    locale = g.locale
    row = fetch_formula(db, formula_id)
    if not row:
        return "Formula not found", 404
    row = dict(row)
    _attach_breadcrumbs(row, locale)
    latex = render_formula(db, formula_id, locale=locale)
    related = []
    for r in fetch_formula_related(db, formula_id):
        r = dict(r)
        r["latex"] = render_formula(db, r["related_id"], locale=locale)
        related.append(r)
    detail_items = _build_formula_detail_items(db, formula_id, locale)

    dim_caches = _get_dimension_caches()
    dimensions = compute_formula_dimensions(db, formula_id)
    dim_latex = format_dimensions_latex(
        *dimensions,
        variable_symbols=dim_caches["var"],
        unit_symbols=dim_caches["unit"],
        dimension_symbols=dim_caches["dim"],
        mode=g.get("dim_mode", "dim"),
    )
    return render_template(
        "formula.html",
        formula=row, latex=latex,
        relations=related, detail_items=detail_items,
        dim_latex=dim_latex,
    )


@app.route("/quantity/<quantity_id>")
def quantity_detail(quantity_id):
    db = get_db()
    locale = g.locale
    q = fetch_quantity(db, quantity_id)
    if not q:
        return "Quantity not found", 404
    q = dict(q)
    _attach_breadcrumbs(q, locale)
    primary_formulas, non_primary_formulas = fetch_quantity_formulas_by_side(db, quantity_id)
    primary_formulas = [dict(f) for f in primary_formulas]
    non_primary_formulas = [dict(f) for f in non_primary_formulas]
    for formulas in (primary_formulas, non_primary_formulas):
        for f in formulas:
            f["latex"] = render_formula(db, f["id"], locale=locale) or ""
    related_formulas = []
    for r in fetch_quantity_related_formulas(db, quantity_id):
        r = dict(r)
        r["latex"] = render_formula(db, r["id"], locale=locale)
        related_formulas.append(r)

    default_unit_html = Markup(
        _render_unit_html(q["default_unit"], locale)
    ) if q.get("default_unit") else ""

    default_unit_symbol_latex = Markup(
        _render_unit_symbol(q["default_unit"])
    ) if q.get("default_unit") else ""

    # Build units table: default_unit row + any non-composite units in the unit table
    units = []
    du_ids = set()
    if q.get("default_unit"):
        try:
            du = json.loads(q["default_unit"])
        except (json.JSONDecodeError, TypeError):
            du = []
        du_ids = {e["unit"] for e in du}
        if du:
            placeholders = ",".join("?" for _ in du)
            unit_system_row = db.execute(
                f"SELECT unit_system FROM unit WHERE id IN ({placeholders}) "
                f"AND unit_system != 'SI' LIMIT 1",
                tuple(e["unit"] for e in du),
            ).fetchone()
            unit_system = unit_system_row["unit_system"] if unit_system_row else "SI"
        else:
            unit_system = "SI"
        units.append({
            "symbol_latex": default_unit_symbol_latex,
            "name_html": default_unit_html,
            "unit_system": unit_system,
            "factor": 1,
            "offset": 0,
            "latex_factor": None,
        })

    extra_units = [dict(u) for u in fetch_quantity_units(db, quantity_id) if u["id"] not in du_ids]
    for eu in extra_units:
        units.append({
            "symbol_latex": Markup(render_symbol(eu["symbol"])),
            "name_html": _unit_name_link(eu["id"]),
            "unit_system": eu.get("unit_system") or "any",
            "factor": eu.get("factor", 1),
            "offset": eu.get("offset", 0),
            "latex_factor": eu.get("latex_factor"),
        })
    show_offset = any(u.get("offset", 0) != 0 for u in units)
    show_factor = any(u.get("factor", 1) != 1 for u in units)

    dim_caches = _get_dimension_caches()
    quantity_dims = extract_dimensions_from_row(q)
    dim_latex = format_dimensions_latex(
        *quantity_dims,
        variable_symbols=dim_caches["var"],
        unit_symbols=dim_caches["unit"],
        dimension_symbols=dim_caches["dim"],
        mode=g.get("dim_mode", "dim"),
    )
    return render_template(
        "quantity.html",
        q=dict(q, default_unit_html=default_unit_html),
        units=units,
        primary_formulas=primary_formulas,
        nonprimary_formulas=non_primary_formulas,
        related_formulas=related_formulas,
        dim_latex=dim_latex,
        show_factor=show_factor,
        show_offset=show_offset,
        default_unit_symbol_latex=default_unit_symbol_latex,
    )


@app.route("/unit/<unit_id>")
def unit_detail(unit_id):
    db = get_db()
    unit = fetch_unit(db, unit_id)
    if not unit:
        return "Unit not found", 404
    unit = dict(unit)
    locale = g.locale
    qty = db.execute("SELECT name FROM quantity WHERE id = ?", (unit["quantity_id"],)).fetchone()
    unit["quantity_name_localized"] = localise(qty["name"], locale) if qty else unit.get("quantity_id", "")
    _attach_breadcrumbs(unit, locale)
    si_unit_symbol = fetch_si_unit_symbol(db, unit["quantity_id"])
    return render_template("unit.html", unit=unit, si_unit_symbol=si_unit_symbol)


@app.route("/search")
def search_page():
    query = request.args.get("q", "").strip()[:SEARCH_QUERY_MAX_LENGTH]
    results = search_headings(get_db(), query) if query else []
    return render_template("search.html", query=query, results=results)


@app.route("/api/search-suggestions")
def search_suggestions():
    query = request.args.get("q", "").strip()[:SUGGEST_QUERY_MAX_LENGTH]
    suggestions = suggest_headings(get_db(), query) if query else []
    return {"suggestions": [
        {"id": s[1], "kind": s[2], "heading": s[3]} for s in suggestions
    ]}


@app.route("/quantities")
def all_quantities():
    db = get_db()
    locale = g.locale
    fs = parse_filter_state(request.args, request.path)
    fs.quantity_mode = "or"
    tree = _sciences_tree()
    compressed = _compress_selection(tree, fs.ids)
    if compressed == {r["id"] for r in tree}:
        return redirect("/quantities")

    if fs.exclude_all or (fs.ids_provided and not fs.ids):
        return render_template(
            "quantities.html",
            quantities=[],
            heading=_("list.quantities_no_results"),
        )

    raw_quantities = fetch_all_quantities(db)
    topic_filter = _filtered_ids_for_query(tree, fs.ids)
    dim_qty_ids = set(dimension_quantity_ids().values()) if fs.base_quantity_only else None
    filtered = []
    for q in raw_quantities:
        q = dict(q)
        _attach_breadcrumbs(q, locale)

        if topic_filter and q.get("topic_id") not in topic_filter:
            continue
        if (q.get("difficulty") or 0) < fs.diff_min or (q.get("difficulty") or 0) > fs.diff_max:
            continue
        if fs.has_dimension_filter and not _dimension_matches(q, fs.dimension_filter, fs.dim_mode):
            continue
        if fs.quantity_ids and q["id"] not in fs.quantity_ids:
            continue
        if dim_qty_ids is not None and q["id"] not in dim_qty_ids:
            continue

        q["default_unit_html"] = Markup(
            _render_unit_html(q["default_unit"], locale)
        )
        q["default_unit_symbol_latex"] = _render_unit_symbol(q["default_unit"])
        filtered.append(q)

    name_map = _tree_name_map(tree, locale)
    dim_caches = _get_dimension_caches()
    quantity_names = []
    if fs.quantity_ids:
        names_by_id = fetch_quantities_by_ids(db, fs.quantity_ids)
        quantity_names = [localise(names_by_id[qid], locale) for qid in fs.quantity_ids
                          if qid in names_by_id]
    heading = _heading_from_compressed(
        _("nav.quantities"), compressed, name_map, locale, fs,
        dim_mode=g.get("dim_mode", "dim"), dimension_caches=dim_caches,
        active_quantity_names=quantity_names,
    )
    if fs.base_quantity_only:
        heading = _("list.base_quantities")
    return render_template("quantities.html", quantities=filtered, heading=heading)


@app.route("/formulas")
def all_formulas():
    db = get_db()
    locale = g.locale
    fs = parse_filter_state(request.args, request.path)
    tree = _sciences_tree()
    compressed = _compress_selection(tree, fs.ids)
    if compressed == {r["id"] for r in tree}:
        return redirect("/formulas")

    if fs.exclude_all or (fs.ids_provided and not fs.ids):
        return render_template(
            "formulas.html",
            formulas=[],
            heading=_("list.formulas_no_results"),
        )

    formulas = [dict(f) for f in fetch_all_formulas(db)]
    topic_filter = _filtered_ids_for_query(tree, fs.ids)
    if topic_filter:
        formulas = [f for f in formulas if f.get("topic_id") in topic_filter]
    formulas = [
        f for f in formulas
        if fs.diff_min <= (f.get("difficulty") or 0) <= fs.diff_max
    ]

    if fs.has_dimension_filter:
        formula_ids = {f["id"] for f in formulas}
        dim_map = compute_all_formula_dimensions(db, formula_ids)
        formulas = [
            f for f in formulas
            if _dimension_matches(dim_map.get(f["id"], {}), fs.dimension_filter, fs.dim_mode)
        ]

    if fs.quantity_ids:
        quantity_match = (
            fetch_formulas_with_any_quantity
            if fs.quantity_mode == "or"
            else fetch_formulas_with_all_quantities
        )
        matching_ids = quantity_match(db, fs.quantity_ids)
        if matching_ids is not None:
            formulas = [f for f in formulas if f["id"] in matching_ids]

    for f in formulas:
        _attach_breadcrumbs(f, locale)
        f["latex"] = render_formula(db, f["id"], locale=locale)

    quantity_names = []
    if fs.quantity_ids:
        names_by_id = fetch_quantities_by_ids(db, fs.quantity_ids)
        quantity_names = [localise(names_by_id[qid], locale) for qid in fs.quantity_ids
                          if qid in names_by_id]

    name_map = _tree_name_map(tree, locale)
    dim_caches = _get_dimension_caches()
    heading = _heading_from_compressed(
        _("nav.formulas"), compressed, name_map, locale, fs,
        dim_mode=g.get("dim_mode", "dim"), dimension_caches=dim_caches,
        active_quantity_names=quantity_names,
    )
    return render_template("formulas.html", formulas=formulas, heading=heading)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@app.route("/export")
def export():
    fmt = request.args.get("format") or request.cookies.get("sf_export_format", "csv")
    db = get_db()

    def _respond(data, mimetype, filename):
        resp = Response(data, mimetype=mimetype, headers={"Content-Disposition": f"attachment; filename={filename}"})
        resp.set_cookie("sf_export_format", fmt, max_age=365*24*3600, path="/")
        return resp

    def _binary_export(export_fn, mimetype, filename):
        buffer = io.BytesIO()
        export_fn(db, buffer)
        buffer.seek(0)
        return _respond(buffer.getvalue(), mimetype, filename)

    if fmt == "xlsx":
        return _binary_export(export_to_xlsx,
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              "scifind.xlsx")
    if fmt == "ods":
        return _binary_export(export_to_ods,
                              "application/vnd.oasis.opendocument.spreadsheet",
                              "scifind.ods")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        with tempfile.TemporaryDirectory() as tmp:
            export_to_csv_directory(db, tmp)
            for p in Path(tmp).iterdir():
                zf.write(p, p.name)
    buffer.seek(0)
    return _respond(buffer.getvalue(), "application/zip", "scifind_csv.zip")


if __name__ == "__main__":
    host = os.environ.get("SCIFIND_HOST", "127.0.0.1")
    port = int(os.environ.get("SCIFIND_PORT", "5000"))
    debug = os.environ.get("SCIFIND_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
