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
    database_has_formula_table,
    init_database,
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
    FORMULA_SORT_KEYS,
    QUANTITY_SORT_KEYS,
    SEARCH_SORT_KEYS,
    DEFAULT_FORMULA_SORT,
    DEFAULT_QUANTITY_SORT,
    DEFAULT_SEARCH_SORT,
    sort_formulas,
    sort_quantities,
    sort_search_rows,
    export_to_csv_directory,
    export_to_xlsx,
    export_to_ods,
    export_to_sql,
    preview_equation,
    build_create_sql,
    unit_name_map,
    unit_symbol_map,
    unit_quantity_map,
    render_symbol,
    dimension_matches,
    dimension_symbols,
    dimension_quantity_ids,
    extract_dimensions_from_row,
    is_hidden_quantity,
    locale_sibilants,
    load_tree,
    topic_name_map,
    all_tree_ids,
    compress_selection,
    expand_selection,
    topic_path,
    topic_tree_order,
    walk_tree,
    _in_clause,
)
from scifind_lib.filter import (
    MIN_DIFFICULTY, MAX_DIFFICULTY,
    parse_filter_state,
    csv_list, safe_int,
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


SEARCH_QUERY_MAX_LENGTH = 200
SUGGEST_QUERY_MAX_LENGTH = 50

logger = logging.getLogger("scifind")


def _resolve_sort(value, allowed, default):
    if value and value in allowed:
        return value
    return default


def _jstree_data(tree, name_map, compressed, exclude_all=False, ids_provided=False):
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
    tree = load_tree()
    name_map = topic_name_map(tree, locale)
    topic = row.get("topic_id")
    path = topic_path(tree, topic)
    if path:
        row["breadcrumbs"] = [{"id": n, "name": name_map.get(n, n)} for n in path]
    else:
        row["breadcrumbs"] = []
    return row


def _filtered_ids_for_query(tree, ids):
    valid = [i for i in ids if i in all_tree_ids(tree)]
    return expand_selection(tree, valid)


def _all_tree_root_ids(tree):
    return {r["id"] for r in tree}


def _localised_quantity_names(db, quantity_ids, locale):
    if not quantity_ids:
        return []
    names_by_id = fetch_quantities_by_ids(db, quantity_ids)
    return [localise(names_by_id[qid], locale) for qid in quantity_ids
            if qid in names_by_id]


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


def _tree_gen_map(tree):
    out = {}
    def visit(node):
        g = (node.get("translations") or {}).get("cs-cz-gen")
        if g:
            out[node["id"]] = g
    walk_tree(tree, visit)
    return out


def _render_list_heading(view_label, tree, compressed, fs, db, locale):
    return _heading_from_compressed(
        view_label, compressed, topic_name_map(tree, locale), locale, fs,
        dim_mode=g.get("dim_mode", "dim"), dimension_caches=_get_dimension_caches(),
        active_quantity_names=_localised_quantity_names(db, fs.quantity_ids, locale),
    )


def _heading_from_compressed(view_label, compressed, name_map, locale, fs,
                             dim_mode="dim", dimension_caches=None,
                             active_quantity_names=None):
    ui = lambda key: _ui_lookup(locale, key)
    parts = [view_label]

    if compressed:
        tree = load_tree()
        order = topic_tree_order()
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
    for symbol in dimension_symbols():
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


DEFAULT_LOCALE = "en-us"
DEFAULT_LOCALE_FALLBACK = {
    "meta": {"name": "US English", "acceptLanguage": "en-US"},
    "ui": {},
}

_LOCALES: dict | None = None


def _load_locales():
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
    data = _available_locales()
    merged = {}
    for loc in reversed(_locale_chain(locale)):
        ui = data.get(loc, {}).get("ui", {})
        for cat, children in ui.items():
            merged.setdefault(cat, {}).update(children)
    return merged


def _ui_lookup(locale, key):
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
    """Resolve a DB i18n JSON blob or a UI-string key for the current locale."""
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


_NOT_INITIALISED = (
    "<h1>Database not initialised</h1>"
    "<p>The SQLite database at <code>{}</code> could not be opened or has no tables.</p>"
    "<p>Run <code>python scifind_cli.py init</code> to create and seed it, "
    "then refresh this page.</p>"
)


def _database_is_initialised(db):
    return database_has_formula_table(db)


def _bootstrap_database():
    conn = open_database()
    try:
        if not _database_is_initialised(conn):
            init_database()
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
        g.unit_name_map = unit_name_map(get_db(), locale)
    return g.unit_name_map


def _get_unit_symbol_map():
    if 'unit_symbol_map' not in g:
        g.unit_symbol_map = unit_symbol_map(get_db())
    return g.unit_symbol_map


def _unit_name_link(unit_id):
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
        unit_quantity_map=unit_quantity_map(get_db()),
    )


def _render_unit_symbol(default_unit):
    symbols = _get_unit_symbol_map()
    return format_default_unit_symbol(
        default_unit,
        unit_symbol=lambda uid: render_symbol(symbols.get(uid, uid)),
    )


def _render_default_unit(default_unit, locale):
    if not default_unit:
        return Markup(""), ""
    return (
        Markup(_render_unit_html(default_unit, locale)),
        _render_unit_symbol(default_unit),
    )


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
    compressed = compress_selection(tree, fs.ids)

    all_quantities_for_filter = []
    dimension_caches = {"var": {}, "unit": {}, "dim": {}}
    if db is not None:
        try:
            all_quantities_for_filter = [
                {"id": q["id"], "name": localise(q["name"], locale), "symbol": q["symbol"] or ""}
                for q in fetch_all_quantities(db)
                if not is_hidden_quantity(q)
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
    sort_context = _sort_context_for(request.path, request.args.get("sort"))

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
        dimension_symbol_list=dimension_symbols() if db else [],
        available_locales=locale_list,
        locale_ui=locale_ui,
        sort=sort_context["sort"],
        available_sorts=sort_context["available_sorts"],
        default_sort=sort_context["default_sort"],
    )


def _sort_context_for(path, raw_value):
    if path.startswith("/search"):
        return {
            "available_sorts": SEARCH_SORT_KEYS,
            "default_sort": DEFAULT_SEARCH_SORT,
            "sort": _resolve_sort(raw_value, SEARCH_SORT_KEYS, DEFAULT_SEARCH_SORT),
        }
    if path.startswith("/quantities"):
        return {
            "available_sorts": QUANTITY_SORT_KEYS,
            "default_sort": DEFAULT_QUANTITY_SORT,
            "sort": _resolve_sort(raw_value, QUANTITY_SORT_KEYS, DEFAULT_QUANTITY_SORT),
        }
    return {
        "available_sorts": FORMULA_SORT_KEYS,
        "default_sort": DEFAULT_FORMULA_SORT,
        "sort": _resolve_sort(raw_value, FORMULA_SORT_KEYS, DEFAULT_FORMULA_SORT),
    }


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
    """Build detail-items-shaped dicts from in-memory RPN tokens + overrides."""
    qids = {tok["quantity_id"] for tok in tokens
            if tok.get("token_kind") == "quantity"}
    if not qids:
        return []
    placeholder, qparams = _in_clause(qids)
    qrows = {
        r["id"]: r for r in db.execute(
            f"SELECT id, name, symbol, default_unit FROM quantity "
            f"WHERE id IN ({placeholder})", qparams
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
    """Build the formula detail table data from formula_id or in-memory tokens."""
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
        unit_html, unit_sym = _render_default_unit(item.get("default_unit"), locale)

        result.append({
            "symbol_latex": symbol_latex,
            "name_html": Markup(name_html) if name_html else "",
            "paren_html": Markup(paren_html) if paren_html else "",
            "default_unit_html": unit_html,
            "default_unit_symbol_latex": unit_sym,
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

    links = []
    if row.get("links"):
        try:
            links = json.loads(row["links"])
            if not isinstance(links, list):
                links = []
        except (ValueError, TypeError):
            links = []

    dim_caches = _get_dimension_caches()
    dimensions = compute_formula_dimensions(db, formula_id)
    dim_latex = format_dimensions_latex(
        *dimensions,
        variable_symbols=dim_caches["var"],
        unit_symbols=dim_caches["unit"],
        dim_symbols=dim_caches["dim"],
        mode=g.get("dim_mode", "dim"),
    )
    return render_template(
        "formula.html",
        formula=row, latex=latex,
        relations=related, detail_items=detail_items,
        dim_latex=dim_latex, links=links,
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

    default_unit_html, default_unit_symbol_latex = _render_default_unit(q["default_unit"], locale)

    units = []
    du_ids = set()
    if q.get("default_unit"):
        try:
            du = json.loads(q["default_unit"])
        except (json.JSONDecodeError, TypeError):
            du = []
        if du:
            du_ids = {e["unit"] for e in du}
            placeholders, duparams = _in_clause(tuple(e["unit"] for e in du))
            unit_system_row = db.execute(
                f"SELECT unit_system FROM unit WHERE id IN ({placeholders}) "
                f"AND unit_system != 'SI' LIMIT 1",
                duparams,
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
        dim_symbols=dim_caches["dim"],
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
    qty = fetch_quantity(db, unit["quantity_id"])
    unit["quantity_name_localized"] = localise(qty["name"], locale) if qty else unit.get("quantity_id", "")
    _attach_breadcrumbs(unit, locale)
    si_unit_symbol = fetch_si_unit_symbol(db, unit["quantity_id"])
    return render_template("unit.html", unit=unit, si_unit_symbol=si_unit_symbol)


@app.route("/search")
def search_page():
    query = request.args.get("q", "").strip()[:SEARCH_QUERY_MAX_LENGTH]
    db = get_db()
    locale = g.locale
    sort_key = _resolve_sort(request.args.get("sort"), SEARCH_SORT_KEYS, DEFAULT_SEARCH_SORT)
    results = search_headings(db, query) if query else []
    results = sort_search_rows(db, results, sort_key, locale)
    return render_template(
        "search.html",
        query=query,
        results=results,
        sort=sort_key,
        available_sorts=SEARCH_SORT_KEYS,
    )


@app.route("/api/search-suggestions")
def search_suggestions():
    query = request.args.get("q", "").strip()[:SUGGEST_QUERY_MAX_LENGTH]
    suggestions = suggest_headings(get_db(), query) if query else []
    return {"suggestions": [
        {"id": s[1], "kind": s[2], "heading": s[3]} for s in suggestions
    ]}


def _parse_override_form_keys():
    """Walk request.form and collect per-quantity override entries."""
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
    """Form-POST version of /api/preview that also returns detail_items HTML."""
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


def _operator_latex(item):
    """Generate LaTeX for an operator in the token sidebar."""
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
        path = topic_path(tree, selected_id) or [selected_id]
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
    walk_tree(tree, visit)
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
    """Return available locales plus the GitHub repo slug for new-issue links."""
    items = [
        {"code": code, "name": data.get("meta", {}).get("name", code)}
        for code, data in sorted(_available_locales().items())
    ]
    repo = os.environ.get("SCIFIND_GITHUB_REPO", "Creeperman3000/Scifind")
    return {"current": getattr(g, "locale", DEFAULT_LOCALE), "locales": items, "repo": repo}


def _parse_translation_block(prefix):
    """Parse a `<prefix>[<locale>][<field>]` FormData block; blanks omitted."""
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


def _build_create_sql_payload(db, form):
    """Parse the /create form fields and return (formula_sql, token_sql)."""
    def scalar(name):
        return (form.get(name) or "").strip()

    name_en = scalar("name_en")
    topic = scalar("topic")
    difficulty = scalar("difficulty") or "2"
    equation = form.get("equation") or ""
    description = scalar("description") or None
    links_raw = scalar("links")
    links = None
    if links_raw:
        url_lines = [p.strip() for p in links_raw.splitlines() if p.strip()]
        if url_lines:
            links = url_lines

    overrides = _parse_override_form_keys()

    tr_top = _parse_translation_block("tr")
    tr_ov = _parse_translation_block("tr_overrides")
    translations = {}
    for loc in set(tr_top) | set(tr_ov):
        entry = {}
        top = tr_top.get(loc, {})
        if "name" in top:
            entry["name"] = top["name"]
        if "description" in top:
            entry["description"] = top["description"]
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
    """Form-POST equivalent of /api/build-sql returning rendered modal HTML."""
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
    sort_key = _resolve_sort(request.args.get("sort"), QUANTITY_SORT_KEYS, DEFAULT_QUANTITY_SORT)
    tree = load_tree()
    compressed = compress_selection(tree, fs.ids)
    if compressed == _all_tree_root_ids(tree):
        return redirect("/quantities")

    if fs.exclude_all or (fs.ids_provided and not fs.ids):
        return render_template(
            "quantities.html",
            quantities=[],
            heading=_("detail.quantities_no_results"),
            sort=sort_key,
            available_sorts=QUANTITY_SORT_KEYS,
        )

    raw_quantities = [q for q in fetch_all_quantities(db) if not is_hidden_quantity(q)]
    topic_filter = _filtered_ids_for_query(tree, fs.ids)
    dim_qty_ids = set(dimension_quantity_ids().values()) if fs.base_quantity_only else None
    filtered = []
    for q in raw_quantities:
        q = dict(q)
        _attach_breadcrumbs(q, locale)

        if topic_filter and q.get("topic_id") not in topic_filter:
            continue
        q_difficulty = q.get("difficulty")
        if q_difficulty is not None and not (fs.diff_min <= q_difficulty <= fs.diff_max):
            continue
        if fs.has_dimension_filter and not dimension_matches(q, fs.dimension_filter, fs.dim_mode):
            continue
        if fs.quantity_ids and q["id"] not in fs.quantity_ids:
            continue
        if dim_qty_ids is not None and q["id"] not in dim_qty_ids:
            continue

        q["default_unit_html"], q["default_unit_symbol_latex"] = _render_default_unit(q["default_unit"], locale)
        filtered.append(q)

    filtered = sort_quantities(filtered, sort_key, locale)

    heading = _render_list_heading(
        _("detail.quantities"), tree, compressed, fs, db, locale,
    )
    if fs.base_quantity_only:
        heading = _("detail.base_quantities")
    return render_template(
        "quantities.html",
        quantities=filtered,
        heading=heading,
        sort=sort_key,
        available_sorts=QUANTITY_SORT_KEYS,
    )


@app.route("/formulas")
def all_formulas():
    db = get_db()
    locale = g.locale
    fs = parse_filter_state(request.args, request.path)
    tree = load_tree()
    compressed = compress_selection(tree, fs.ids)
    if compressed == _all_tree_root_ids(tree):
        return redirect("/formulas")

    sort_key = _resolve_sort(request.args.get("sort"), FORMULA_SORT_KEYS, DEFAULT_FORMULA_SORT)

    if fs.exclude_all or (fs.ids_provided and not fs.ids):
        return render_template(
            "formulas.html",
            formulas=[],
            heading=_("detail.formulas_no_results"),
            sort=sort_key,
            available_sorts=FORMULA_SORT_KEYS,
        )

    formulas = [dict(f) for f in fetch_all_formulas(db)]
    topic_filter = _filtered_ids_for_query(tree, fs.ids)
    if topic_filter:
        formulas = [f for f in formulas if f["topic_id"] in topic_filter]
    formulas = [
        f for f in formulas
        if f.get("difficulty") is None
        or fs.diff_min <= f["difficulty"] <= fs.diff_max
    ]

    if fs.has_dimension_filter:
        formula_ids = {f["id"] for f in formulas}
        dim_map = compute_all_formula_dimensions(db, formula_ids)
        formulas = [
            f for f in formulas
            if dimension_matches(dim_map.get(f["id"], {}), fs.dimension_filter, fs.dim_mode)
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

    formulas = sort_formulas(db, formulas, sort_key, locale)

    for f in formulas:
        _attach_breadcrumbs(f, locale)
        f["latex"] = render_formula(db, f["id"], locale=locale)

    heading = _render_list_heading(
        _("nav.formulas"), tree, compressed, fs, db, locale,
    )
    return render_template(
        "formulas.html",
        formulas=formulas,
        heading=heading,
        sort=sort_key,
        available_sorts=FORMULA_SORT_KEYS,
    )


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

    if fmt == "sql":
        return _respond(export_to_sql(db).encode("utf-8"),
                        "application/sql", "scifind.sql")

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
