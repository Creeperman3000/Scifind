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
    fetch_all_constants,
    fetch_all_operators,
    fetch_all_formulas,
    search_headings,
    suggest_headings,
    export_to_csv_directory,
    export_to_xlsx,
    export_to_ods,
    preview_equation,
    build_create_sql,
    _unit_name_map,
    _unit_symbol_map,
    _unit_quantity_map,
    render_symbol,
    _dimension_matches,
    DIMENSION_SYMBOLS,
    dimension_quantity_ids,
    extract_dimensions_from_row,
    locale_sibilants,
    DIMENSION_COLUMNS,
    load_tree,
    topic_name_map,
    all_tree_ids,
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


def _leaf_ids(node):
    """Every leaf id under a node (a leaf has no children)."""
    if not node.get("children"):
        return {node["id"]}
    leaves = set()
    for child in node["children"]:
        leaves |= _leaf_ids(child)
    return leaves


def _descendant_ids(node):
    """All descendant node ids including the node itself."""
    ids = {node["id"]}
    for child in (node.get("children") or []):
        ids |= _descendant_ids(child)
    return ids


def _walk_tree(tree, visit):
    """Depth-first walk; visit(node) is called for every node."""
    for root in tree:
        visit(root)
        _walk_tree(root.get("children") or [], visit)


def _walk_tree_skip(tree, visit):
    """Depth-first walk; visit(node) returning False skips recursion into children."""
    for root in tree:
        if visit(root):
            _walk_tree_skip(root.get("children") or [], visit)


def _expand_selection(tree, ids):
    """Expand a set of tree-level ids to all leaf ids they cover.

    Unknown ids in the input are silently dropped.
    """
    idset = set(ids)
    covered = set()
    def visit(node):
        if node["id"] in idset:
            covered.update(_descendant_ids(node))
    _walk_tree(tree, visit)
    return covered


def _compress_selection(tree, ids):
    """Replace a set of leaf ids with the minimal ancestor covering set."""
    idset = set(ids)
    covered_leaves = set()
    def visit_collect(node):
        if node["id"] in idset:
            covered_leaves.update(_leaf_ids(node))
    _walk_tree(tree, visit_collect)

    out = set()
    def visit_collapse(node):
        if _leaf_ids(node) <= covered_leaves:
            out.add(node["id"])
            return False
        return True
    _walk_tree_skip(tree, visit_collapse)
    return out


def _topic_path(tree, topic):
    """Return the ids along the path to a topic, or None if not in the tree."""
    def visit(node, ancestors=()):
        if node["id"] == topic:
            return ancestors + (topic,)
        for child in (node.get("children") or []):
            result = visit(child, ancestors + (node["id"],))
            if result:
                return result
    for root in tree:
        if result := visit(root):
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
    tree = load_tree()
    name_map = topic_name_map(tree, locale)
    topic = row.get("topic_id")
    path = _topic_path(tree, topic)
    if path:
        row["breadcrumbs"] = [{"id": n, "name": name_map.get(n, n)} for n in path]
    else:
        row["breadcrumbs"] = []
    return row


def _filtered_ids_for_query(tree, ids):
    """Convert a set of tree-level ids into the full set of leaf topic ids."""
    valid = [i for i in ids if i in all_tree_ids(tree)]
    return _expand_selection(tree, valid)


def _all_tree_root_ids(tree):
    return {r["id"] for r in tree}


def _localised_quantity_names(db, quantity_ids, locale):
    """Localised names for the given quantity ids (preserves input order)."""
    if not quantity_ids:
        return []
    names_by_id = fetch_quantities_by_ids(db, quantity_ids)
    return [localise(names_by_id[qid], locale) for qid in quantity_ids
            if qid in names_by_id]


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
    def visit(node):
        order[node["id"]] = counter[0]
        counter[0] += 1
    _walk_tree(tree, visit)
    return order


def _tree_gen_map(tree):
    """Map of node id → 'cs-cz-gen' translation (Czech genitive form)."""
    out = {}
    def visit(node):
        g = (node.get("translations") or {}).get("cs-cz-gen")
        if g:
            out[node["id"]] = g
    _walk_tree(tree, visit)
    return out


def _render_list_heading(view_label, tree, compressed, fs, db, locale):
    """Render the /quantities or /formulas page heading from filter state."""
    return _heading_from_compressed(
        view_label, compressed, topic_name_map(tree, locale), locale, fs,
        dim_mode=g.get("dim_mode", "dim"), dimension_caches=_get_dimension_caches(),
        active_quantity_names=_localised_quantity_names(db, fs.quantity_ids, locale),
    )


def _heading_from_compressed(view_label, compressed, name_map, locale, fs,
                             dim_mode="dim", dimension_caches=None,
                             active_quantity_names=None):
    """Render the page heading.

    Format: {view_label} from {topics} with {quantity_label} {quantities}
            where difficulty is {difficulty} and {dimensions}
    """
    ui = lambda key: _ui_lookup(locale, key)
    parts = [view_label]

    if compressed:
        tree = load_tree()
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
            prep = _sibilant_prep(joined, ui("heading.from"), locale)
            parts.append(f"{prep} {joined}")

    if active_quantity_names:
        q_label = ui("heading.quantity" if len(active_quantity_names) == 1
                     else "heading.quantities")
        q_conj = "heading.or" if fs.quantity_mode == "or" else "heading.and"
        joined = _join_names(active_quantity_names, locale, q_conj)
        prep = _sibilant_prep(joined, ui("heading.with"), locale)
        parts.append(f"{prep} {q_label} {joined}")

    clauses = []
    if fs.diff_min > MIN_DIFFICULTY or fs.diff_max < MAX_DIFFICULTY:
        where = ui("heading.where_difficulty_is")
        if fs.diff_min == fs.diff_max:
            clauses.append(f"{where} {fs.diff_min}")
        else:
            clauses.append(f"{where} {fs.diff_min}\u2013{fs.diff_max}")

    if dimension_caches is None:
        dimension_caches = {}
    x_map = dimension_caches.get("var" if dim_mode == "unit" else dim_mode, {})
    y_map = dimension_caches.get("unit", {})
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
    if dim_parts:
        d_conj = "heading.or" if fs.dim_mode == "or" else "heading.and"
        joined = _join_names(dim_parts, locale, d_conj)
        clauses.append(f"{ui('heading.where_dimensions_are')} {joined}")

    if clauses:
        parts.append(f" {ui('heading.and')} ".join(clauses))

    text = " ".join(parts)
    return text[0].upper() + text[1:] if text else f"{ui('heading.all')} {view_label}"


# ---------------------------------------------------------------------------
# Locale
# ---------------------------------------------------------------------------

DEFAULT_LOCALE = "en-us"
DEFAULT_LOCALE_FALLBACK = {
    "meta": {"name": "US English", "acceptLanguage": "en-US"},
    "ui": {},
}

# (locale → loaded dict, lang → locale)
_LOCALES: dict | None = None


def _load_locales():
    """Read all locales/*.json files. Cached after first call."""
    global _LOCALES
    if _LOCALES is not None:
        return _LOCALES
    data = {}
    lang_map = {}
    if _LOCALE_DIR.is_dir():
        for path in sorted(_LOCALE_DIR.glob("*.json")):
            locale = path.stem
            try:
                with open(path, encoding="utf-8") as f:
                    payload = json.load(f)
            except (OSError, ValueError):
                continue
            data[locale] = payload
            lang = payload.get("meta", {}).get("acceptLanguage", locale)
            lang_map[lang] = locale
    if DEFAULT_LOCALE not in data:
        data[DEFAULT_LOCALE] = DEFAULT_LOCALE_FALLBACK
    lang_map.setdefault("en-US", DEFAULT_LOCALE)
    lang_map.setdefault("en", DEFAULT_LOCALE)
    _LOCALES = (data, lang_map)
    return _LOCALES


def _available_locales():
    return _load_locales()[0]


def _lang_to_locale():
    return _load_locales()[1]


def _locale_chain(start):
    """Locale code → list of codes walking the fallback chain (deduped)."""
    data, _ = _load_locales()
    chain = []
    seen = set()
    locale = start
    while locale and locale not in seen:
        seen.add(locale)
        chain.append(locale)
        locale = data.get(locale, {}).get("meta", {}).get("fallback")
    return chain


def _resolve_locale(header):
    """Pick the best locale from an Accept-Language header (or default)."""
    if not header:
        return DEFAULT_LOCALE
    lang_map = _lang_to_locale()
    for part in header.split(","):
        code = part.split(";")[0].strip()[:5]
        if code in lang_map:
            return lang_map[code]
        base = code[:2]
        if base in lang_map:
            return lang_map[base]
    return DEFAULT_LOCALE


def _build_ui_with_fallback(locale):
    """Deep-merge UI dict along the fallback chain (current locale wins)."""
    data = _available_locales()
    merged = {}
    for loc in reversed(_locale_chain(locale)):
        ui = data.get(loc, {}).get("ui", {})
        for cat, children in ui.items():
            merged.setdefault(cat, {}).update(children)
    return merged


def _ui_lookup(locale, key):
    """Look up a dotted UI key ('category.child') in the nested locale ui dict,
    following the fallback chain (e.g. cs-cz -> en-us)."""
    data = _available_locales()
    parts = key.split(".", 1)
    if len(parts) != 2:
        return key
    cat, child = parts
    for loc in _locale_chain(locale):
        val = data.get(loc, {}).get("ui", {}).get(cat, {}).get(child)
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
    loc = getattr(g, "locale", DEFAULT_LOCALE)
    if data and data.strip().startswith("{"):
        result = localise(data, loc)
        if result:
            return result
    return _ui_lookup(loc, data)


app.template_global()(render_symbol)


@app.before_request
def detect_locale():
    locale = request.args.get("locale") or request.cookies.get("sf_locale")
    if locale and locale in _available_locales():
        session["locale"] = locale
    if session.get("locale") in _available_locales():
        g.locale = session["locale"]
    else:
        g.locale = _resolve_locale(request.headers.get("Accept-Language", ""))

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
        if not _database_is_initialised(conn):
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
    tree = load_tree()
    db = None
    try:
        db = get_db()
    except sqlite3.OperationalError as exc:
        logger.warning("Database unavailable: %s", exc)
    fs = parse_filter_state(request.args, request.path)
    name_map = topic_name_map(tree, locale)
    compressed = _compress_selection(tree, fs.ids)

    all_quantities_for_filter = []
    dimension_caches = {"var": {}, "unit": {}, "dim": {}}
    if db is not None:
        try:
            all_quantities_for_filter = [
                {"id": q["id"], "name": localise(q["name"], locale), "symbol": q["symbol"] or ""}
                for q in fetch_all_quantities(db)
            ]
        except sqlite3.OperationalError as exc:
            logger.warning("Quantity table unavailable: %s", exc)
        dimension_caches = _get_dimension_caches()

    dim_mode = g.get("dim_mode", "dim")
    dim_symbols = dimension_caches.get(dim_mode, dimension_caches.get("dim", {}))

    locale_list = [
        {"code": code, "name": data.get("meta", {}).get("name", code)}
        for code, data in _available_locales().items()
    ]
    locale_ui = _build_ui_with_fallback(locale)
    is_qty_page = (request.path == "/quantities"
                   or request.path.startswith(("/quantity/", "/unit/")))

    return dict(
        tree_json=_jstree_data(tree, name_map, compressed, fs.exclude_all, ids_provided=fs.ids_provided),
        diff_min=fs.diff_min,
        diff_max=fs.diff_max,
        current_view="quantities" if is_qty_page else "formulas",
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


@app.route("/create")
def create_formula():
    return render_template("create.html")


def _items_from_tokens(db, tokens):
    """Build detail-items-shaped dicts from in-memory RPN tokens + overrides.

    Resolves quantity metadata (name/symbol/default_unit) once via IN-clause
    query, then one dict per quantity token (operators/constants skipped).
    """
    qids = {tok["quantity_id"] for tok in tokens
            if tok.get("token_kind") == "quantity"}
    if not qids:
        return []
    placeholder = ",".join("?" for _ in qids)
    qrows = {
        r["id"]: r for r in db.execute(
            f"SELECT id, name, symbol, default_unit FROM quantity "
            f"WHERE id IN ({placeholder})", list(qids)
        ).fetchall()
    }
    items = []
    for tok in tokens:
        if tok.get("token_kind") != "quantity":
            continue
        qrow = qrows.get(tok["quantity_id"])
        if not qrow:
            continue
        qid = tok["quantity_id"]
        qty_name = localise(qrow["name"], "en-us") or qid.replace("_", " ").title()
        items.append({
            "quantity_id": qid,
            "quantity_symbol": qrow["symbol"],
            "quantity_name": qty_name,
            "symbol_overwrite": tok.get("symbol_overwrite") or "",
            "quantity_name_overwrite": tok.get("quantity_name_overwrite") or "",
            "label": tok.get("label") or "",
            "default_unit": qrow["default_unit"],
        })
    return items


def _build_formula_detail_items(db, formula_id, locale, tokens=None):
    """Build the formula detail table data.

    Pass either `formula_id` (to fetch from formula_token) or `tokens` (the
    in-memory output of `parse_equation`, with overrides already applied).
    Both paths produce the same shape — the /create preview flow uses
    `tokens` to skip the round-trip through formula_token.
    """
    if tokens is None:
        items = [dict(r) for r in fetch_formula_detail_items(db, formula_id)]
    else:
        items = _items_from_tokens(db, tokens)

    result = []
    for item in items:
        qid = item.get("quantity_id")
        if not qid:
            continue

        symbol_latex = render_variable_base(item, locale)
        qty_name = item.get("quantity_name") or qid.replace("_", " ").title()
        orig_symbol = (item.get("quantity_symbol") or "").strip()
        overwrite = localise(item.get("symbol_overwrite") or "", locale)
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
                name_html = parse_quantity_name_markers(qno_raw)
            else:
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
        if du:
            du_ids = {e["unit"] for e in du}
            placeholders = ",".join("?" for _ in du)
            unit_system_row = db.execute(
                f"SELECT unit_system FROM unit WHERE id IN ({placeholders}) "
                f"AND unit_system != 'SI' LIMIT 1",
                tuple(e["unit"] for e in du),
            ).fetchone()
            unit_system = unit_system_row["unit_system"] if unit_system_row else "SI"
            units.append({
                "symbol_latex": default_unit_symbol_latex,
                "name_html": default_unit_html,
                "unit_system": unit_system,
                "factor": 1,
                "offset": 0,
                "latex_factor": None,
            })
        else:
            unit_system = "SI"
    else:
        unit_system = "SI"

    for eu in (dict(u) for u in fetch_quantity_units(db, quantity_id)):
        if eu["id"] in du_ids:
            continue
        units.append({
            "symbol_latex": Markup(render_symbol(eu["symbol"])),
            "name_html": _unit_name_link(eu["id"]),
            "unit_system": eu.get("unit_system") or "any",
            "factor": eu.get("factor", 1),
            "offset": eu.get("offset", 0),
            "latex_factor": eu.get("latex_factor"),
        })
    show_offset = any(u["offset"] != 0 for u in units)
    show_factor = any(u["factor"] != 1 for u in units)

    dim_caches = _get_dimension_caches()
    dim_latex = format_dimensions_latex(
        *extract_dimensions_from_row(q),
        variable_symbols=dim_caches["var"],
        unit_symbols=dim_caches["unit"],
        dimension_symbols=dim_caches["dim"],
        mode=g.get("dim_mode", "dim"),
    )
    return render_template(
        "quantity.html",
        q={**q, "default_unit_html": default_unit_html},
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


@app.route("/api/token-dictionary")
def token_dictionary():
    """All quantities, constants, and operators — used by the formula
    builder UI for autocomplete, validation, and rendering."""
    db = get_db()
    dim_cols = DIMENSION_COLUMNS()
    quantities = [
        {
            "id": r["id"],
            "name": r["name"],
            "symbol": r["symbol"],
            **{c: r[c] for c in dim_cols},
        }
        for r in fetch_all_quantities(db)
    ]
    constants = [
        {"id": r["id"], "name": r["name"], "symbol": r["symbol"]}
        for r in fetch_all_constants(db)
    ]
    operators = [
        {
            "id": r["id"],
            "symbol": r["symbol"],
            "math": r["math"],
            "arity": r["arity"],
            "precedence": r["precedence"],
            "associativity": r["associativity"],
            "operator_type": r["operator_type"],
        }
        for r in fetch_all_operators(db)
    ]
    return {
        "quantities": quantities,
        "constants": constants,
        "operators": operators,
    }


@app.route("/api/preview")
def preview_equation_api():
    """Parse an equation and return preview data (LaTeX, dims, variables).

    Used by the /create page to render the live preview and dimensions as
    the user types. Returns 200 even on parse error so the client can show
    a friendly message; the `error` field is non-empty in that case.
    """
    db = get_db()
    equation = (request.args.get("equation") or "").strip()
    locale = g.locale
    caches = _get_dimension_caches()
    result = preview_equation(db, equation, locale=locale, dim_caches=caches, dim_mode=g.get("dim_mode", "dim"))
    return result


def _parse_override_form_keys():
    """Walk ``request.form`` and return a dict keyed by
    ``"<quantity_id>|<alias>"`` with ``{symbol, name, label}`` entries,
    matching the keys the /create page uses for its override inputs.
    """
    overrides = {}
    sep = "]["
    for key, values in request.form.lists():
        if not key.startswith("override[") or not key.endswith("]"):
            continue
        body = key[len("override["):-1]
        if sep not in body:
            continue
        ov_key, field = body.rsplit(sep, 1)
        if field not in ("symbol", "name", "label"):
            continue
        value = next((v for v in reversed(values) if v.strip()), "")
        if not value:
            continue
        overrides.setdefault(ov_key, {})[field] = value
    return overrides


@app.route("/create/preview-render", methods=["POST"])
def create_preview_render():
    """Form-POST version of ``/api/preview`` that also accepts per-quantity
    overrides and returns the rendered ``detail_items`` HTML (the same shape
    used by /formula). Used by the /create page to keep the live preview
    and the "Quantity Overrides" table in sync with whatever the user is
    typing.
    """
    db = get_db()
    locale = g.locale
    equation = (request.form.get("equation") or "").strip()
    overrides = _parse_override_form_keys()
    caches = _get_dimension_caches()
    result = preview_equation(db, equation, locale=locale, dim_caches=caches, overrides=overrides, dim_mode=g.get("dim_mode", "dim"))
    if result.get("error") or not result.get("latex"):
        return result
    items = _build_formula_detail_items(db, None, locale, tokens=result["tokens"])
    result["detail_items"] = items
    return result


@app.route("/api/build-sql", methods=["POST"])
def build_sql_api():
    """Generate the INSERT SQL strings for a new formula.

    Accepts JSON: {name_en, topic, difficulty, equation, overrides?,
                   translations?}.
    Returns {formula_sql, token_sql} on success or {error: str} on failure.
    """
    db = get_db()
    payload = request.get_json(silent=True) or {}
    try:
        formula_sql, token_sql = build_create_sql(
            db,
            name_en=payload.get("name_en", ""),
            topic=payload.get("topic", ""),
            difficulty=payload.get("difficulty", 2),
            equation=payload.get("equation", ""),
            overrides=payload.get("overrides") or {},
            translations=payload.get("translations") or {},
        )
    except ValueError as e:
        return {"error": str(e)}, 400
    return {"formula_sql": formula_sql, "token_sql": token_sql}


# ---------------------------------------------------------------------------
# /create page server-rendered fragments
#
# The create page used to ship ~500 lines of client JS that re-rendered the
# token sidebar, the variable override table, and the topic breadcrumb on
# every keystroke. Each of those concerns now has a dedicated endpoint that
# returns ready-to-insert HTML; the page just sets innerHTML and wires a
# handful of delegated listeners.
# ---------------------------------------------------------------------------


def _operator_latex(item):
    """Generate LaTeX for an operator in the token sidebar.

    Placeholder arguments are x, y, then a, b, c, ... (so the prefix
    "x, y, z" reads like the canonical math notation).
    """
    op_id = item["id"]
    symbol = item.get("symbol") or ""
    op_type = item["operator_type"]
    placeholders = list("xyz") + [chr(c) for c in range(ord("a"), ord("z"))]
    x, y = placeholders[0], placeholders[1]
    if op_type in ("infix", "relational"):
        if op_id == "frac":
            return f"\\frac{{{x}}}{{{y}}}"
        if op_id == "pow":
            return f"{x}^{{{y}}}"
        if symbol:
            return f"{x} {symbol} {y}"
        return f"{x} {y}"
    if op_type == "prefix":
        return f"-{x}" if symbol == "-" else f"{symbol} {x}"
    if op_type == "postfix":
        return f"{x}{symbol}" if symbol else x
    return ""


def _render_token_item(item, kind, locale):
    """One <div class="qty-result"> for the token sidebar."""
    item = dict(item)
    if kind == "op":
        sym_text = _operator_latex(item)
        name = item["id"]
        insert = item.get("symbol") or item["id"]
        search = " ".join([item["id"], item.get("symbol") or ""]).lower()
    else:
        sym_text = item.get("symbol") or ""
        name = localise(item.get("name") or "", locale, default="en-us") or item["id"]
        insert = item["id"]
        search = " ".join([
            item["id"], item.get("symbol") or "", str(item.get("name") or ""),
        ]).lower()

    sym_html = f'<span class="qty-result-sym">${html_module.escape(sym_text)}$</span>' if sym_text else '<span class="qty-result-sym"></span>'
    return (
        f'<div class="qty-result" data-kind="{kind}" data-insert="{html_module.escape(insert)}"'
        f' data-search="{html_module.escape(search)}">'
        f'{sym_html}'
        f'<span class="qty-result-name">{html_module.escape(name)}</span>'
        f'</div>'
    )


def _render_token_section(label, target_id, items, kind, locale, no_match_label):
    """One labelled <section> of token items with a collapse toggle."""
    body = "".join(_render_token_item(it, kind, locale) for it in items)
    return (
        f'<div class="section-label-row">'
        f'<div class="section-label">{html_module.escape(label)}</div>'
        f'<div class="filter-buttons">'
        f'<button class="filter-btn" data-action="toggle-token-section" data-target="{target_id}" type="button">'
        f'<span class="token-section-icon"><i data-lucide="chevron-up" width="16" height="16"></i></span>'
        f'</button>'
        f'</div></div>'
        f'<div class="token-list" id="{target_id}">{body}</div>'
        f'<div class="token-empty">{html_module.escape(no_match_label)}</div>'
    )


@app.route("/create/token-sidebar")
def create_token_sidebar():
    """Server-rendered Q/C/O token sidebar for the /create page."""
    db = get_db()
    locale = g.locale
    no_results = _("create.no_results")
    sections = [
        _render_token_section(
            _("detail.quantities"), "token-qty",
            fetch_all_quantities(db), "qty", locale, no_results,
        ),
        _render_token_section(
            _("nav.constants"), "token-const",
            fetch_all_constants(db), "const", locale, no_results,
        ),
        _render_token_section(
            _("nav.operators"), "token-op",
            fetch_all_operators(db), "op", locale, no_results,
        ),
    ]

    return Markup(
        '<div class="filter-qty-search-wrap">'
        f'<div class="qty-search-wrap"><input type="text" class="qty-search text-field" id="token-search" placeholder="{html_module.escape(_("create.search_placeholder"))}" autocomplete="off"></div>'
        '</div>'
        f'<div class="token-sidebar">{"".join(sections)}</div>'
    )


def _render_breadcrumb(selected_id, tree, name_map):
    """Server-rendered topic breadcrumb (root > ... > selected > child trigger)."""
    selected_node = _find_node(tree, selected_id) if selected_id else None
    if selected_node is not None:
        current_kids = [c["id"] for c in (selected_node.get("children") or [])]
        path = _topic_path(tree, selected_id) or [selected_id]
    else:
        current_kids = [r["id"] for r in tree]
        path = None

    parts = []
    if path:
        for i, tid in enumerate(path):
            if i > 0:
                parts.append(' <span class="breadcrumb-sep">&gt;</span> ')
            parts.append(
                f'<span class="topic-current"'
                f' data-id="{html_module.escape(tid)}">'
                f'{html_module.escape(name_map.get(tid, tid))}</span>'
            )

    if current_kids:
        if parts:
            parts.append(' <span class="breadcrumb-sep">&gt;</span> ')
        trigger_label = _("create.topic")
        menu_items = "".join(
            _render_menu_item(cid, tree, name_map) for cid in current_kids
        )
        parts.append(
            f'<span class="topic-current has-menu" data-text="{html_module.escape(trigger_label)}">'
            f'<button class="topic-dropdown-trigger" type="button">'
            f'{html_module.escape(trigger_label)}</button>'
            f'<div class="topic-children-menu">{menu_items}</div>'
            f'</span>'
        )

    parts.append(
        f'<input type="hidden" id="topic" name="topic" form="create-form"'
        f' value="{html_module.escape(selected_id or "")}">'
    )
    return Markup("".join(parts))


def _find_node(tree, node_id):
    found = []
    def visit(node):
        if node["id"] == node_id:
            found.append(node)
    _walk_tree(tree, visit)
    return found[0] if found else None


def _render_menu_item(node_id, tree, name_map):
    node = _find_node(tree, node_id)
    name = name_map.get(node_id, node_id) if node else node_id
    kids = (node.get("children") or []) if node else []
    if kids:
        sub = "".join(_render_menu_item(c["id"], tree, name_map) for c in kids)
        return (
            f'<div class="topic-menu-item" data-id="{html_module.escape(node_id)}">'
            f'<span>{html_module.escape(name)}</span>'
            f'<span class="caret"></span>'
            f'<div class="topic-submenu">{sub}</div>'
            f'</div>'
        )
    return (
        f'<button type="button" class="topic-menu-item" data-id="{html_module.escape(node_id)}">'
        f'<span>{html_module.escape(name)}</span>'
        f'</button>'
    )


@app.route("/create/breadcrumb")
def create_breadcrumb():
    """Return the server-rendered breadcrumb for the given topic id."""
    topic = (request.args.get("topic") or "").strip() or None
    tree = load_tree()
    name_map = topic_name_map(tree, g.locale)
    return _render_breadcrumb(topic, tree, name_map)


@app.route("/create/languages")
def create_languages():
    """Return the list of available locales for the /create translation flow.

    Each entry is `{"code": "en-us", "name": "US English"}`. The current
    document language is included as `current` so the front-end can default
    the "skip English" checkbox. The `repo` field carries the GitHub
    `owner/repo` slug the new-issue link should point to (overridable via
    the SCIFIND_GITHUB_REPO env var).
    """
    items = [
        {"code": code, "name": data.get("meta", {}).get("name", code)}
        for code, data in sorted(_available_locales().items())
    ]
    repo = os.environ.get("SCIFIND_GITHUB_REPO", "Creeperman3000/Scifind")
    return {"current": getattr(g, "locale", DEFAULT_LOCALE), "locales": items, "repo": repo}


def _parse_translation_block(prefix):
    """Parse a FormData block shaped like `<prefix>[<locale>][<field>]`.

    Returns `{locale: {field: value, ...}, ...}`. Values that are blank
    strings are omitted so callers can use "field present" to decide whether
    to merge the value into the i18n blob.
    """
    out = {}
    pattern = re.compile(r"^" + re.escape(prefix) + r"\[([^\]]+)\]\[([^\]]+)\]$")
    for key, val in request.form.items(multi=True):
        m = pattern.match(key)
        if not m:
            continue
        loc, field = m.group(1), m.group(2)
        if not val or not str(val).strip():
            continue
        out.setdefault(loc, {})[field] = str(val).strip()
    return out


def _parse_translation_links_block(prefix):
    """Parse a FormData block shaped like `<prefix>[<locale>][links][]`.

    Returns `{locale: [{"url": ..., "label": ...}, ...], ...}`.
    """
    out = {}
    pattern = re.compile(r"^" + re.escape(prefix) + r"\[([^\]]+)\]\[links\]\[\]$")
    for key, val in request.form.items(multi=True):
        m = pattern.match(key)
        if not m:
            continue
        loc = m.group(1)
        if not val or not str(val).strip():
            continue
        out.setdefault(loc, []).append({"url": str(val).strip()})
    return out


def _build_create_sql_payload(db, form):
    """Parse the /create form fields and return (formula_sql, token_sql).

    Raises ValueError for user-input errors that should be shown in the UI.
    """
    def scalar(name):
        return (form.get(name) or "").strip()

    name_en = scalar("name_en")
    topic = scalar("topic")
    difficulty = scalar("difficulty") or "2"
    equation = form.get("equation") or ""
    description = scalar("description") or None
    links_raw = scalar("links")
    # One URL per line; blank lines skipped.
    links = None
    if links_raw:
        url_lines = [p.strip() for p in links_raw.splitlines() if p.strip()]
        if url_lines:
            links = [{"url": p} for p in url_lines]

    overrides = _parse_override_form_keys()

    # Per-language fields are submitted as `tr[<locale>][name|description]`,
    # `tr[<locale>][links][]`, and `tr_overrides[<locale>][<key>][field]`.
    tr_top = _parse_translation_block("tr")
    tr_links = _parse_translation_links_block("tr")
    tr_ov = _parse_translation_block("tr_overrides")
    translations = {}
    for loc in set(tr_top) | set(tr_links) | set(tr_ov):
        entry = {}
        top = tr_top.get(loc, {})
        if "name" in top:
            entry["name"] = top["name"]
        if "description" in top:
            entry["description"] = top["description"]
        if loc in tr_links:
            entry["links"] = tr_links[loc]
        if loc in tr_ov:
            entry["overrides"] = tr_ov[loc]
        if entry:
            translations[loc] = entry

    return build_create_sql(
        db,
        name_en=name_en,
        topic=topic,
        difficulty=difficulty,
        equation=equation,
        overrides=overrides,
        description=description,
        links=links,
        translations=translations,
    )


def _render_sql_modal_html(formula_sql, token_sql):
    # Icon-only copy button in the top-right of each .sql-block. Matches
    # the .formula-copy-btn look used in the main formula preview.
    return Markup(
        '<div class="sql-block">'
        f'<button class="formula-copy-btn sql-copy-btn" type="button" data-action="copy-formula-sql" title="Copy">'
        f'<i data-lucide="copy" width="16" height="16"></i>'
        f'</button>'
        f'<pre id="formula-sql">{html_module.escape(formula_sql)}</pre>'
        f'</div>'
        '<h3>' + html_module.escape(_("create.token_inserts")) + '</h3>'
        '<div class="sql-block">'
        f'<button class="formula-copy-btn sql-copy-btn" type="button" data-action="copy-token-sql" title="Copy">'
        f'<i data-lucide="copy" width="16" height="16"></i>'
        f'</button>'
        f'<pre id="token-sql">{html_module.escape(token_sql)}</pre>'
        f'</div>'
    )


@app.route("/create/build-sql", methods=["POST"])
def create_build_sql():
    """Form-POST equivalent of /api/build-sql.

    Accepts the same fields as the create form, including `override[<key>]`
    arrays for variable overrides and `tr[<locale>][...]` blocks for
    per-language translations. Returns the rendered modal HTML on
    success and a JSON `{error}` with 400 on failure.
    """
    db = get_db()
    try:
        formula_sql, token_sql = _build_create_sql_payload(db, request.form)
    except ValueError as e:
        body = (
            f'<p class="detail-desc" data-error="{html_module.escape(str(e))}">'
            f'{html_module.escape(str(e))}</p>'
        )
        return Markup(body), 400
    return _render_sql_modal_html(formula_sql, token_sql)


@app.route("/quantities")
def all_quantities():
    db = get_db()
    locale = g.locale
    fs = parse_filter_state(request.args, request.path)
    fs.quantity_mode = "or"
    tree = load_tree()
    compressed = _compress_selection(tree, fs.ids)
    if compressed == _all_tree_root_ids(tree):
        return redirect("/quantities")

    if fs.exclude_all or (fs.ids_provided and not fs.ids):
        return render_template(
            "quantities.html",
            quantities=[],
            heading=_("list.quantities_no_results"),
        )

    raw_quantities = list(fetch_all_quantities(db))
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

    heading = _render_list_heading(
        _("detail.quantities"), tree, compressed, fs, db, locale,
    )
    if fs.base_quantity_only:
        heading = _("detail.base_quantities")
    return render_template("quantities.html", quantities=filtered, heading=heading)


@app.route("/formulas")
def all_formulas():
    db = get_db()
    locale = g.locale
    fs = parse_filter_state(request.args, request.path)
    tree = load_tree()
    compressed = _compress_selection(tree, fs.ids)
    if compressed == _all_tree_root_ids(tree):
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
        formulas = [f for f in formulas if f["topic_id"] in topic_filter]
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

    heading = _render_list_heading(
        _("nav.formulas"), tree, compressed, fs, db, locale,
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
