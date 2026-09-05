#!/usr/bin/env python3
"""Scifind web app — Flask interface to the formula database."""

import gzip
import html as html_module
import io
import json
import logging
import math
import os
import re
import secrets
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from flask import Flask, render_template, request, g, Response, redirect, session, url_for
from markupsafe import Markup

_PROJECT_DIR = Path(__file__).resolve().parent
_LOCALE_DIR = _PROJECT_DIR / "locales"
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from scifind_lib import (
    open_database,
    database_path,
    database_has_formula_table,
    initialize_database,
    render_formula_latex,
    format_dimensions_latex,
    format_compound_unit_html,
    format_compound_unit_symbol,
    localise,
    load_locale_config,
    fetch_formula,
    fetch_formula_relations,
    fetch_formula_token_quantities,
    render_variable_symbol,
    expand_quantity_markers,
    build_entity_link,
    fetch_quantity,
    fetch_quantity_units,
    fetch_si_prefixes,
    fetch_quantity_formulas_by_side,
    fetch_quantity_related_formulas,
    fetch_quantities_by_ids,
    fetch_constant,
    fetch_constant_formulas,
    fetch_quantity_constants,
    compute_formula_dimensions,
    compute_all_formula_dimensions,
    compute_compound_unit_dimensions,
    fetch_formulas_with_all_quantities,
    fetch_formulas_with_any_quantity,
    fetch_unit,
    build_dimension_symbol_triplet,
    fetch_all_quantities,
    fetch_all_constants,
    fetch_all_operators,
    fetch_all_formulas,
    compound_unit_by_id,
    select_base_unit_with_fallback,
    unit_by_id,
    search_entities,
    suggest_entities,
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
    build_formula_insert_sql,
    parse_and_preview_equation,
    build_create_sql,
    unit_name_map,
    unit_symbol_map,
    unit_quantity_map,
    wrap_symbol_in_latex,
    dimension_matches,
    dimension_symbols,
    dimension_quantity_ids,
    dimensions_from_row,
    locale_sibilants,
    load_tree,
    topic_name_map,
    all_tree_ids,
    compress_selection,
    expand_selection,
    topic_path,
    topic_tree_order,
    walk_tree,
    in_clause,
)
from scifind_lib.constants import SUPERSCRIPT_DIGITS
from scifind_lib.filter import MIN_DIFFICULTY, MAX_DIFFICULTY, parse_filter_state
from scifind_lib.units import parse_compound_unit, parse_compound_unit_parts
from scifind_lib.conversion import (
    UnitGraph, precompute_latex_map, convert_value,
)

app = Flask(
    __name__,
    static_folder="web",
    template_folder="web",
)


@app.before_request
def _hide_templates_from_static():
    if request.path.startswith(f"{app.static_url_path}/") and request.path.endswith(
        ".html"
    ):
        return Response("Not Found", status=404)


def _secret_key():
    env_key = os.environ.get("SCIFIND_SECRET_KEY")
    if env_key:
        return env_key
    key_file = Path(app.instance_path) / "secret_key"
    fallback = secrets.token_hex(24)
    for _ in range(2):
        try:
            stored = key_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            stored = None
        except OSError:
            return fallback
        if stored:
            return stored
        try:
            key_file.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        except OSError:
            return fallback
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
        return key_file.read_text(encoding="utf-8").strip()
    return fallback


app.secret_key = _secret_key()
app.config["MAX_CONTENT_LENGTH"] = (
    int(os.environ.get("SCIFIND_MAX_UPLOAD_MB", "1")) * 1024 * 1024
)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 365 * 86400
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(
    os.environ.get("SCIFIND_COOKIE_SECURE", "").lower() in ("1", "true", "yes")
)


_GZIP_TYPES = ('text/', 'application/json', 'application/javascript')


def _accepts_gzip(header_value):
    for part in header_value.split(","):
        token, _, params = part.partition(";")
        if token.strip().lower() != "gzip":
            continue
        q = params.strip().lower()
        if q.startswith("q="):
            try:
                return float(q[2:]) > 0
            except ValueError:
                return True
        return True
    return False


@app.after_request
def gzip_response(response):
    response.vary.add("Accept-Encoding")
    if not _accepts_gzip(request.headers.get("Accept-Encoding", "")):
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
CREATE_EQUATION_MAX_LENGTH = 2000

logger = logging.getLogger("scifind")


def _resolve_sort(value, allowed, default):
    if value and value in allowed:
        return value
    return default


def _topic_tree_data(tree, name_map, compressed, exclude_all=False, ids_provided=False):
    if not compressed and not exclude_all and not ids_provided:
        compressed = {r["id"] for r in tree} if tree else set()
    def conv(node):
        return {
            "id": node["id"],
            "name": name_map.get(node["id"], node["id"]),
            "state": {"checked": node["id"] in compressed},
            "children": [conv(c) for c in (node.get("children") or [])],
        }
    return [conv(r) for r in tree] if tree else []


def _attach_breadcrumbs(row, locale):
    tree = load_tree()
    name_map = topic_name_map(tree, locale)
    topic = row.get("topic_id")
    topic_path_ids = topic_path(tree, topic)
    if topic_path_ids:
        row["breadcrumbs"] = [{"id": n, "name": name_map.get(n, n)} for n in topic_path_ids]
    else:
        row["breadcrumbs"] = []
    return row


def _filtered_ids_for_query(tree, ids):
    valid = [i for i in ids if i in all_tree_ids(tree)]
    return expand_selection(tree, valid)


def _all_tree_root_ids(tree):
    return {r["id"] for r in tree}


def _localised_quantity_names(conn, quantity_ids, locale):
    if not quantity_ids:
        return []
    names_by_id = fetch_quantities_by_ids(conn, quantity_ids)
    return [localise(names_by_id[qid], locale) for qid in quantity_ids
            if qid in names_by_id]


_LATEX_TEXTCMD_RE = re.compile(r"\\(?:mathrm|text)\{([^}]*)\}")


def _strip_textcmd(text):
    return _LATEX_TEXTCMD_RE.sub(r"\1", text)


def _join_names(names, locale="en-us", conj_key="heading.and"):
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    data = _available_locales()
    cat, _, child = conj_key.partition(".")
    conj = None
    for loc in _locale_chain(locale):
        conj = data.get(loc, {}).get("ui", {}).get(cat, {}).get(child)
        if conj is not None:
            break
    if not isinstance(conj, str):
        conj = data.get(DEFAULT_LOCALE, {}).get("ui", {}).get(cat, {}).get(child)
    if not isinstance(conj, str):
        if conj_key not in _WARNED_KEYS:
            _WARNED_KEYS.add(conj_key)
            logger.warning("l10n: _join_names key %r not found in any locale, falling back to 'and'", conj_key)
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


def _render_list_heading(view_label, tree, compressed, fs, conn, locale):
    return _heading_from_compressed(
        view_label, compressed, topic_name_map(tree, locale), locale, fs,
        dim_mode=g.get("dim_mode", "dim"), dimension_caches=_get_dimension_caches(),
        active_quantity_names=_localised_quantity_names(conn, fs.quantity_ids, locale),
    )


_OP_SYMBOLS = {"eq": "=", "geq": "\u2265", "leq": "\u2264"}


def _heading_from_compressed(view_label, compressed, name_map, locale, fs,
                             dim_mode="dim", dimension_caches=None,
                             active_quantity_names=None):
    def _ui(key): return _ui_lookup(locale, key)
    parts = [view_label]

    if compressed:
        tree = load_tree()
        order = topic_tree_order()
        gen_map = _tree_gen_map(tree) if locale == "cs-cz" else {}
        seen, topic_names = set(), []
        for nid in sorted(compressed, key=lambda x: order.get(x, float("inf"))):
            n = gen_map.get(nid) or name_map.get(nid, nid)
            if n not in seen:
                topic_names.append(n)
                seen.add(n)
        if topic_names:
            joined = _join_names(topic_names, locale)
            parts.append(f"{_sibilant_prep(joined, _ui('heading.from'), locale)} {joined}")

    if active_quantity_names:
        q_label = _ui("heading.quantity" if len(active_quantity_names) == 1
                      else "heading.quantities")
        q_conj = "heading.or" if fs.quantity_mode == "or" else "heading.and"
        joined = _join_names(active_quantity_names, locale, q_conj)
        parts.append(f"{_sibilant_prep(joined, _ui('heading.with'), locale)} {q_label} {joined}")

    clauses = []
    if fs.diff_min > MIN_DIFFICULTY or fs.diff_max < MAX_DIFFICULTY:
        where = _ui("heading.where_difficulty_is")
        if fs.diff_min == fs.diff_max:
            clauses.append(f"{where} {fs.diff_min}")
        else:
            clauses.append(f"{where} {fs.diff_min}\u2013{fs.diff_max}")

    if dimension_caches is None:
        dimension_caches = {}
    x_map = dimension_caches.get("var" if dim_mode == "unit" else dim_mode, {})
    y_map = dimension_caches.get("unit", {})
    dim_parts = []
    for symbol in dimension_symbols():
        d = fs.dimension_filter.get(symbol, {})
        if d.get("val") is None:
            continue
        x_sym = _strip_textcmd(x_map.get(symbol, symbol))
        y_sym = _strip_textcmd(y_map.get(symbol, symbol))
        dv = str(d["val"]).translate(SUPERSCRIPT_DIGITS)
        dim_parts.append(f"{x_sym} {_OP_SYMBOLS[d.get('op', 'eq')]} {y_sym}{dv}")
    if dim_parts:
        d_conj = "heading.or" if fs.dim_mode == "or" else "heading.and"
        joined = _join_names(dim_parts, locale, d_conj)
        clauses.append(f"{_ui('heading.where_dimensions_are')} {joined}")

    if clauses:
        parts.append(f" {_ui('heading.and')} ".join(clauses))

    text = " ".join(parts)
    return text[0].upper() + text[1:] if text else f"{_ui('heading.all')} {view_label}"


DEFAULT_LOCALE = "en-us"
DEFAULT_LOCALE_FALLBACK = {
    "meta": {"name": "US English", "acceptLanguage": "en-US"},
    "ui": {},
}

_LOCALES: dict | None = None
_WARNED_KEYS: set = set()


def _load_locales():
    global _LOCALES
    if _LOCALES is not None:
        return _LOCALES
    locales_data, lang_map = {}, {}
    if _LOCALE_DIR.is_dir():
        for path in sorted(_LOCALE_DIR.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    locale_data = json.load(f)
            except (OSError, ValueError):
                continue
            locale = path.stem
            locales_data[locale] = locale_data
            lang_map[locale_data.get("meta", {}).get("acceptLanguage", locale)] = locale
    if DEFAULT_LOCALE not in locales_data:
        locales_data[DEFAULT_LOCALE] = DEFAULT_LOCALE_FALLBACK
    lang_map.setdefault("en-US", DEFAULT_LOCALE)
    lang_map.setdefault("en", DEFAULT_LOCALE)
    _LOCALES = (locales_data, lang_map)
    for loc, locale_data in locales_data.items():
        if loc == DEFAULT_LOCALE:
            continue
        empty_cats = sorted(c for c, children in locale_data.get("ui", {}).items() if not children)
        if empty_cats:
            logger.warning("l10n: locale %r has empty ui categories: %s", loc, empty_cats)
    return _LOCALES


def _available_locales():
    return _load_locales()[0]


def _lang_to_locale():
    return _load_locales()[1]


_CSRF_SESSION_KEY = "_csrf_token"
_CSRF_HEADER = "X-CSRF-Token"
_CSRF_FORM_FIELD = "_csrf_token"


def _ensure_csrf_token():
    token = session.get(_CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[_CSRF_SESSION_KEY] = token
    return token


@app.before_request
def _csrf_protect():
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    if request.endpoint in (None, "static"):
        return
    sent = (
        request.headers.get(_CSRF_HEADER)
        or request.form.get(_CSRF_FORM_FIELD)
        or ""
    )
    expected = session.get(_CSRF_SESSION_KEY) or ""
    if not expected or not sent or not secrets.compare_digest(sent, expected):
        return ("CSRF token missing or invalid", 400)


@app.before_request
def _seed_csrf_token():
    _ensure_csrf_token()


@app.context_processor
def _inject_csrf_token():
    return {"csrf_token": _ensure_csrf_token}


_RATE_LIMIT_BUCKETS = {}


def _rate_limit(bucket, max_per_minute):
    try:
        max_n = int(max_per_minute)
    except (TypeError, ValueError):
        return None
    if max_n <= 0:
        return None
    now = time.monotonic()
    cutoff = now - 60.0
    window = _RATE_LIMIT_BUCKETS.get(bucket)
    if window is None:
        window = []
        _RATE_LIMIT_BUCKETS[bucket] = window
    while window and window[0] < cutoff:
        window.pop(0)
    if len(window) >= max_n:
        return (f"Rate limit exceeded for {bucket}", 429)
    window.append(now)
    return None


def _client_key():
    return (request.remote_addr or "anon") + "|" + (request.endpoint or "?")


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
    if key in _WARNED_KEYS:
        return key
    _WARNED_KEYS.add(key)
    intended = key in data.get(DEFAULT_LOCALE, {}).get("ui", {}).get(cat, {})
    if intended:
        logger.warning(
            "l10n: key %r (locale %s) fell back to en-us — translation missing in chain %s",
            key, locale, list(_locale_chain(locale)),
        )
    else:
        logger.warning(
            "l10n: unknown key %r (locale %s) — not present in any locale file",
            key, locale,
        )
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


app.template_global()(wrap_symbol_in_latex)


_STATIC_VERSION_CACHE: dict = {}


def _static_version(filename):
    if filename not in _STATIC_VERSION_CACHE:
        try:
            st = (Path(app.static_folder) / filename).stat()
            _STATIC_VERSION_CACHE[filename] = f"{int(st.st_mtime):x}{st.st_size:x}"
        except OSError:
            _STATIC_VERSION_CACHE[filename] = ""
    return _STATIC_VERSION_CACHE[filename]


@app.template_global()
def static_v(filename):
    """Static URL with an mtime/size version for cache busting."""
    url = url_for("static", filename=filename)
    v = _static_version(filename)
    return f"{url}?v={v}" if v else url


@app.before_request
def detect_locale():
    def _resolve_setting(arg_key, cookie_key, allowed, default):
        value = request.args.get(arg_key) or request.cookies.get(cookie_key)
        if value in allowed:
            session[arg_key] = value
        g.__setattr__(arg_key, session.get(arg_key, default))

    locale = request.args.get("locale") or request.cookies.get("sf_locale")
    if locale in _available_locales():
        session["locale"] = locale
    g.locale = (
        session["locale"]
        if session.get("locale") in _available_locales()
        else _resolve_locale(request.headers.get("Accept-Language", ""))
    )

    _resolve_setting("dim_mode", "sf_dim_mode", ("dim", "var", "unit"), "dim")
    _resolve_setting("unit_system", "sf_unit_system", ("SI", "CGS", "Imperial"), "SI")

    meta = load_locale_config(g.locale)
    g.locale_seo_description = meta.get("seoDescription") or load_locale_config(DEFAULT_LOCALE).get("seoDescription", "")
    g.locale_seo_keywords = meta.get("seoKeywords") or load_locale_config(DEFAULT_LOCALE).get("seoKeywords", "")


_NOT_INITIALISED = (
    "<h1>Database not initialised</h1>"
    "<p>The SQLite database at <code>{}</code> could not be opened or has no tables.</p>"
    "<p>Run <code>python scifind_cli.py init</code> to create and seed it, "
    "then refresh this page.</p>"
)


def _bootstrap_database():
    conn = open_database()
    try:
        if not database_has_formula_table(conn):
            initialize_database()
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
    if not database_has_formula_table(db):
        return _uninitialised_response()


def _uninitialised_response():
    return (_NOT_INITIALISED.format(os.environ.get("SCIFIND_DB", "scifind.db")), 503)


def _get_dimension_caches():
    if 'dim_caches' not in g:
        try:
            var_map, unit_map, dim_map = build_dimension_symbol_triplet(get_db())
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


def _get_prefix_name_map(locale=None):
    if 'prefix_name_map' not in g:
        loc = locale or g.get("locale", "en-us")
        g.prefix_name_map = {
            int(p["id"]): localise(p["name"], loc)
            for p in fetch_si_prefixes(get_db())
        }
    return g.prefix_name_map


def _get_prefix_symbol_map(locale=None):
    if 'prefix_symbol_map' not in g:
        loc = locale or g.get("locale", "en-us")
        g.prefix_symbol_map = {
            int(p["id"]): localise(p["symbol"], loc)
            for p in fetch_si_prefixes(get_db())
        }
    return g.prefix_symbol_map


def _unit_name_link(unit_id):
    names = _get_unit_name_map()
    if unit_id in names:
        return Markup(build_entity_link("unit", unit_id, names[unit_id]))
    return Markup(html_module.escape(unit_id.replace("_", " ").title()))


def _unit_name_callback(locale):
    names = _get_unit_name_map()
    first = [True]

    def unit_name(uid):
        name = names.get(uid, uid.replace("_", " ")).lower()
        if first[0]:
            first[0] = False
            return name[0].upper() + name[1:]
        return name

    return unit_name


def _prefix_name_callback(locale):
    pmap = _get_prefix_name_map(locale)
    return lambda exp: pmap.get(exp, "")


def _prefix_symbol_callback(locale):
    smap = _get_prefix_symbol_map(locale)
    return lambda exp: smap.get(exp, "")


def _render_unit_html(unit_json, locale):
    names = _get_unit_name_map()
    return format_compound_unit_html(
        unit_json,
        unit_url=lambda uid: f"/unit/{uid}" if uid in names else None,
        unit_name=_unit_name_callback(locale),
        locale=locale,
        unit_quantity_map=unit_quantity_map(get_db()),
        prefix_name=_prefix_name_callback(locale),
    )


def _render_unit_symbol(unit_json, locale=None):
    symbols = _get_unit_symbol_map()
    loc = locale or g.get("locale", "en-us")
    # `format_compound_unit_symbol` wraps each part in \\mathrm{} itself,
    # so pass raw symbols here to avoid double-wrapping.
    return format_compound_unit_symbol(
        unit_json,
        unit_symbol=lambda uid: symbols.get(uid, uid),
        prefix_symbol=lambda exp: _get_prefix_symbol_map(loc).get(exp, ""),
    )


def _render_compound_unit(cu_row, locale):
    """Render a base row (unit or compound_unit) as (html, latex_symbol)."""
    if not cu_row:
        return Markup(""), ""
    if cu_row["kind"] == "unit":
        return Markup(_unit_name_link(cu_row["id"])), wrap_symbol_in_latex(cu_row["symbol"])
    unit = cu_row["unit"]
    sym_latex = (
        wrap_symbol_in_latex(cu_row["symbol_overwrite"]) if cu_row["symbol_overwrite"]
        else _render_unit_symbol(unit, locale)
    )
    name_html = (
        localise(cu_row["name_overwrite"], locale)
        if cu_row.get("name_overwrite")
        else _render_unit_html(unit, locale)
    )
    return Markup(name_html), sym_latex


def _format_system_label(system, is_base, locale):
    if not system:
        return _("unit.system_any")
    if is_base:
        return _("unit.system_base").format(system=_(f"unit.system_{system.lower()}"))
    return _(f"unit.system_{system.lower()}")


def _row_is_base(conn, row_id, system, kind):
    """True if `row_id` is the base row for its quantity.

    The `system` filter is intentionally not applied so a system base
    shows regardless of the display system.
    """
    if not row_id:
        return False
    if kind == "unit":
        row = conn.execute(
            "SELECT 1 FROM unit WHERE id = ? AND is_base = 1 LIMIT 1",
            (row_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM compound_unit WHERE id = ? AND is_base = 1 LIMIT 1",
            (row_id,),
        ).fetchone()
    return row is not None


def _quantity_units_table(conn, quantity_id, system, ref_unit_id=None):
    """Unit-table rows shared by /quantity/<id> and /unit/<id>.

    Conversion LaTeX to every reachable unit is precomputed server-side,
    so the client only looks up the cached string on reference change.
    """
    locale = g.locale
    base = select_base_unit_with_fallback(conn, quantity_id, system)
    default_unit_html, default_unit_symbol_latex = (
        _render_compound_unit(base, locale) if base else (Markup(""), "")
    )

    graph = UnitGraph(conn, quantity_id)
    _inject_si_prefix_nodes(graph, conn, quantity_id)
    latex_map = precompute_latex_map(graph)

    base_unit_ids = set()
    if base and base["kind"] == "compound_unit":
        base_unit_ids = {uid for uid, _ in parse_compound_unit(base["unit"])}
    elif base:
        base_unit_ids = {base["id"]}
    base_system = base["system"] if base else "SI"
    default_id = base["id"] if base else None

    entries = []
    si_prefixes, _ = _si_prefix_rows(conn, "SI", quantity_id)
    if si_prefixes:
        base_entry_id = base["id"] if base else None
        for section_key, section in si_prefixes.items():
            for r in section["rows"]:
                if base_entry_id and r["payload_id"] == base_entry_id:
                    continue
                entries.append({
                    "id": r["payload_id"],
                    "symbol_latex": Markup(r["symbol_latex"]),
                    "name_html": Markup(r["name"]),
                    "label": r["name"],
                    "system": _format_system_label(None, False, locale),
                })

    if base:
        label_json = (json.dumps([{"unit": base["id"], "exponent": 1}])
                      if base["kind"] == "unit" else base["unit"])
        base_is_base = _row_is_base(conn, base["id"], system, base["kind"])
        entries.append({
            "id": base["id"],
            "symbol_latex": default_unit_symbol_latex,
            "name_html": default_unit_html,
            "label": format_compound_unit_html(
                label_json, locale=locale,
                unit_name=_unit_name_callback(locale),
                prefix_name=_prefix_name_callback(locale)),
            "system": _format_system_label(base_system, base_is_base, locale),
        })

    for eu in (dict(u) for u in fetch_quantity_units(conn, quantity_id)):
        if base and base["kind"] == "unit" and eu["id"] == base["id"]:
            continue
        eu_system = eu.get("system") or None
        eu_is_base = _row_is_base(conn, eu["id"], system, "unit")
        entries.append({
            "id": eu["id"],
            "symbol_latex": Markup(wrap_symbol_in_latex(eu["symbol"])),
            "name_html": _unit_name_link(eu["id"]),
            "label": (localise(eu.get("name"), locale)
                      or localise(eu.get("name"), "en-us")
                      or eu["id"].replace("_", " ")),
            "system": _format_system_label(eu_system, eu_is_base, locale),
        })

    # Skip compound rows already shown as SI prefix entries (hectare = hm²,
    # etc.) — they only belong in the prefix table.
    si_prefix_entry_ids = set()
    if si_prefixes:
        for section in si_prefixes.values():
            for r in section["rows"]:
                si_prefix_entry_ids.add(r["id"])
    for cu in conn.execute(
        "SELECT * FROM compound_unit WHERE quantity_id = ?", (quantity_id,)
    ).fetchall():
        cu_row = dict(cu)
        if cu_row["id"] in si_prefix_entry_ids:
            continue
        cu_row["kind"] = "compound_unit"
        if base and base["kind"] == "compound_unit" and cu_row["id"] == base["id"]:
            continue
        unit_html, unit_sym = _render_compound_unit(cu_row, locale)
        cu_system = cu_row.get("system") or None
        cu_is_base = _row_is_base(conn, cu_row["id"], system, "compound_unit")
        # Show the parts-derived name in parens unless it duplicates the override.
        no_json = cu_row.get("name_overwrite")
        if no_json and localise(no_json, locale):
            parts_name = format_compound_unit_html(
                cu_row["unit"], locale=locale,
                unit_quantity_map=unit_quantity_map(conn),
                unit_name=_unit_name_callback(locale),
                prefix_name=_prefix_name_callback(locale))
            parts_text = re.sub(r"<[^>]+>", "", parts_name).strip()
            override_text = localise(no_json, locale)
            if parts_text and parts_text.lower() != override_text.lower():
                cu_name_html = Markup(f"{override_text} ({parts_text})")
                cu_label = f"{override_text} ({parts_text})"
            else:
                cu_name_html = Markup(override_text)
                cu_label = override_text
        else:
            cu_name_html = unit_html
            cu_label = format_compound_unit_html(
                cu_row["unit"], locale=locale,
                unit_name=_unit_name_callback(locale),
                prefix_name=_prefix_name_callback(locale))
        entries.append({
            "id": cu_row["id"],
            "symbol_latex": unit_sym,
            "name_html": cu_name_html,
            "label": cu_label,
            "system": _format_system_label(cu_system, cu_is_base, locale),
        })

    if ref_unit_id and any(e["id"] == ref_unit_id for e in entries):
        ref_id = ref_unit_id
    else:
        ref_id = default_id

    ref_label = next(
        (re.sub(r"<[^>]+>", "", str(e["label"])) for e in entries if e["id"] == ref_id),
        "",
    )

    si_payload_ids = set()
    if si_prefixes:
        for section in si_prefixes.values():
            for r in section["rows"]:
                si_payload_ids.add(r["payload_id"])
    units_rows = []
    for e in entries:
        if (e["id"] or "").startswith("si_"):
            continue
        # DB-overwritten SI prefix entries are already in the prefix table; skip.
        if e["id"] in si_payload_ids:
            continue
        plain_label = re.sub(r"<[^>]+>", "", e["label"]) if e.get("label") else (e["id"] or "").replace("_", " ")
        units_rows.append({
            "id": e["id"] or "",
            "symbol_latex": e["symbol_latex"],
            "name_html": e["name_html"],
            "label": plain_label,
            "system": e["system"],
            "is_ref": e["id"] == ref_id,
            "latex_by_ref": {rid: latex_map.get(e["id"], {}).get(rid)
                             for rid in latex_map},
        })

    si_prefix_sections = []
    if si_prefixes:
        for section_key, section in si_prefixes.items():
            section_payload = []
            for r in section["rows"]:
                pid = r["payload_id"]
                section_payload.append({
                    "id": pid,
                    "symbol_latex": Markup(r["symbol_latex"]),
                    "name": r["name"],
                    "system_key": r.get("system_key"),
                    "link_unit_id": r.get("link_unit_id"),
                    "value_latex": r.get("value_latex", ""),
                    "is_ref": pid == ref_id,
                    "collapsed": bool(r.get("collapsed")),
                    "latex_by_ref": {rid: latex_map.get(pid, {}).get(rid)
                                     for rid in latex_map},
                })
            si_prefix_sections.append({
                "component": section["component"],
                "label": section["label"],
                "payload": section_payload,
            })
    si_payload = [row for section in si_prefix_sections for row in section["payload"]]
    payload = {
        "ref": ref_id or "",
        "ref_label": ref_label,
        "entries": units_rows,
        "si_entries": si_payload,
    }
    return {
        "units": units_rows,
        "payload": payload,
        "si_prefixes": si_payload,
        "si_prefix_sections": si_prefix_sections,
    }


def _normalise_prefix_symbol(prefix_sym, next_token):
    """Add a separating space when a backslash-command prefix (e.g. `\\mu`)
    is followed by a letter token, so they don't parse as one undefined command.
    """
    if not prefix_sym or not next_token:
        return prefix_sym
    if not next_token[0].isalnum() and next_token[0] != "_":
        return prefix_sym
    if prefix_sym.endswith(" "):
        return prefix_sym
    stripped = prefix_sym.rstrip()
    if not stripped.endswith("\\") and "\\" in stripped:
        last_bs = stripped.rfind("\\")
        tail = stripped[last_bs + 1:]
        if tail and tail.isalpha():
            return prefix_sym + " "
    if stripped.endswith("\\") or stripped.endswith("}"):
        return prefix_sym + " "
    return prefix_sym


def _unit_symbol_for(conn, uid):
    row = fetch_unit(conn, uid)
    return row["symbol"] if row else uid


def _prefix_symbol_for(conn, exp):
    row = conn.execute(
        "SELECT symbol FROM si_prefix WHERE id = ?", (str(exp),)
    ).fetchone()
    if not row:
        return str(exp)
    sym_json = row["symbol"]
    localised = localise(sym_json, g.locale)
    if not localised:
        localised = localise(sym_json, "en-us")
    return localised or str(exp)


def _build_compound_sym_latex(conn, prefix_sym, primary_uid, parts):
    """Prefixed compound LaTeX: prefix prepended to the primary prefixable part,
    otherwise matching `format_compound_unit_symbol`'s shape.
    """
    def _wrap(sym):
        return wrap_symbol_in_latex(sym)

    primary_sym_raw = _unit_symbol_for(conn, primary_uid)
    out_parts = []
    for part_uid, part_exp in parts:
        if part_uid == primary_uid:
            normalized = _normalise_prefix_symbol(prefix_sym, primary_sym_raw)
            combined = normalized + primary_sym_raw
            sym_latex = _wrap(combined)
        else:
            sym_latex = _wrap(_unit_symbol_for(conn, part_uid))
        out_parts.append([part_uid, part_exp, sym_latex])
    numerators, denominators = [], []
    for part_uid, part_exp, sym_latex in out_parts:
        if part_exp >= 0:
            numerators.append((sym_latex, part_exp))
        else:
            denominators.append((sym_latex, -part_exp))

    def _render_group(group):
        out = []
        for sym_latex, exp in group:
            if exp == 1:
                out.append(sym_latex)
            else:
                out.append(f"{sym_latex}^{{{int(exp)}}}")
        return " \\cdot ".join(out)

    num_str = _render_group(numerators)
    den_str = _render_group(denominators)
    if not den_str:
        return num_str
    if not num_str:
        return f"1 / {den_str}" if len(denominators) == 1 else f"1 / ({den_str})"
    return (
        f"{num_str} / {den_str}"
        if len(denominators) == 1
        else f"{num_str} / ({den_str})"
    )


def _inject_si_prefix_nodes(graph, conn, quantity_id):
    """Inject synthetic SI-prefixed nodes (si_kilo -> base) so the renderer
    can emit "1 km = 1000 m" for the prefix table.

    For compound units with multiple prefixable components, inject separate
    nodes for each component so that multiple tables can be generated.
    """
    locale = g.locale
    base = select_base_unit_with_fallback(conn, quantity_id, g.get("unit_system", "SI"))
    if not base:
        return

    prefixable = _get_prefixable_base_units(conn)
    if base["kind"] == "unit":
        pref_base_id = prefixable.get(base["id"], base["id"])
        base_unit_row = fetch_unit(conn, pref_base_id)
        if base_unit_row is None:
            return
        base_symbol = base_unit_row["symbol"]
        base_symbol_latex = wrap_symbol_in_latex(base_symbol)
        for p in fetch_si_prefixes(conn):
            exp = int(p["id"])
            pid = f"si_{p['id']}"
            graph.edges[pid] = (pref_base_id, 10 ** exp, 0, None, "mul", 0.0)
            prefix_sym = _normalise_prefix_symbol(localise(p["symbol"], locale), base_symbol)
            graph.unit_rows[pid] = {
                "id": pid,
                "symbol": prefix_sym + base_symbol,
                "system": "SI",
                "quantity_id": quantity_id,
                "is_base": 0,
            }
    else:
        parts = parse_compound_unit(base["unit"])
        if not parts:
            return
        prefixable = _get_prefixable_base_units(conn)
        prefixable_parts = []
        for part_uid, part_exp in parts:
            pref_uid = prefixable.get(part_uid)
            if pref_uid:
                prefixable_parts.append((part_uid, part_exp, pref_uid))

        if not prefixable_parts:
            return

        for part_uid, part_exp, _pref_uid in prefixable_parts:
            part_symbol = _unit_symbol_for(conn, part_uid)
            for p in fetch_si_prefixes(conn):
                exp = int(p["id"])
                pid = f"si_{p['id']}_{part_uid}"
                factor = 10 ** (exp * part_exp)
                graph.edges[pid] = (base["id"], factor, 0, None, "mul", 0.0)
                prefixed_sym_latex = _build_compound_sym_latex(
                    conn, localise(p["symbol"], locale), part_uid, parts
                )
                graph.compound_rows[pid] = {
                    "id": pid,
                    "unit": base["unit"],
                    "symbol_overwrite": prefixed_sym_latex,
                    "system": "SI",
                    "quantity_id": quantity_id,
                    "is_base": 0,
                }


def _get_prefixable_base_units(conn):
    """SI base units to their prefixable base; kilogram maps to gram."""
    result = {}
    rows = conn.execute(
        "SELECT id FROM unit WHERE is_base = 1 AND system = 'SI'"
    ).fetchall()
    for r in rows:
        result[r["id"]] = r["id"]
    result["kilogram"] = "gram"
    result["gram"] = "gram"
    return result

# kilogram is the SI base of mass even though prefixes attach to gram.
SI_BASE_EXPONENT = {"gram": 3}

# Visible before expansion: base, kilo, milli. Deca/hecto are only shown
# by default when a DB entry (hectare, are) exists; synthetic rows collapse.
DEFAULT_VISIBLE_EXPONENTS = {0, 3, -3}


def _si_prefix_rows(conn, system, quantity_id):
    """Rows for every SI-prefixed form of a quantity's base unit, plus its
    unprefixed base at 10^0. Returns (rows, cgs_unit_id).
    """
    locale = g.locale
    base = select_base_unit_with_fallback(conn, quantity_id, system)
    if not base:
        base = conn.execute(
            "SELECT * FROM unit WHERE quantity_id = ? LIMIT 1",
            (quantity_id,),
        ).fetchone()
        if not base:
            return None, None
        base = {"kind": "unit", **dict(base)}

    cgs_unit = conn.execute(
        "SELECT id FROM unit WHERE quantity_id = ? AND system = 'CGS' LIMIT 1",
        (quantity_id,),
    ).fetchone()
    cgs_unit_id = cgs_unit["id"] if cgs_unit else None

    prefixable = _get_prefixable_base_units(conn)
    if base["kind"] == "unit":
        base_id = prefixable.get(base["id"], base["id"])
        base_unit_row = fetch_unit(conn, base_id)
        if base_unit_row is None:
            return None, None
        base_symbol = base_unit_row["symbol"]
        base_name = localise(base_unit_row["name"], locale) or localise(base_unit_row["name"], "en-us")
        base_id_for_link = base_id if fetch_unit(conn, base_id) else None

        def make_prefix_rows(base_id, base_name, base_symbol):
            base_symbol_latex = wrap_symbol_in_latex(base_symbol)
            def system_field(exp):
                if exp == SI_BASE_EXPONENT.get(base_id, 0):
                    return ("detail.si_base", base_id_for_link)
                return (None, None)
            prefixed = []

            prefixed.append({
                "id": base_id,
                "exp": 0,
                "symbol_latex": base_symbol_latex,
                "name": base_name,
                "system_key": system_field(0)[0],
                "link_unit_id": base_id_for_link,
                "value_latex": "10^{0}",
            })

            for p in fetch_si_prefixes(conn):
                exp = int(p["id"])
                combined = localise(p["name"], locale) + base_name.lower()
                sys_key, _ = system_field(exp)
                link_unit_id = base_id_for_link
                prefix_sym = localise(p["symbol"], locale)
                normalised_prefix = _normalise_prefix_symbol(prefix_sym, base_symbol)
                prefix_word = localise(p["name"], locale)
                name_html = (
                    html_module.escape(prefix_word)
                    + f'<a href="/unit/{link_unit_id}">'
                    + html_module.escape(base_name.lower())
                    + "</a>"
                )
                prefixed.append({
                    "id": f"si_{p['id']}",
                    "exp": exp,
                    "symbol_latex": wrap_symbol_in_latex(normalised_prefix) + base_symbol_latex,
                    "name": Markup(name_html),
                    "system_key": sys_key,
                    "link_unit_id": None,
                    "value_latex": f"10^{{{exp}}}",
                })
            for r in prefixed:
                r["collapsed"] = r["exp"] not in DEFAULT_VISIBLE_EXPONENTS
                r["payload_id"] = r["id"] or base_id or "si_base"
            prefixed.sort(key=lambda x: x["exp"], reverse=True)
            return prefixed

        rows = make_prefix_rows(base_id, base_name, base_symbol)
        sections = {base_id: {"component": base_id, "label": base_name, "rows": rows}}
        return sections, cgs_unit_id

    parts_with_prefix = parse_compound_unit_parts(base["unit"])
    parts = [(uid, exp) for uid, exp, _prefix in parts_with_prefix]
    if not parts:
        return None, None

    prefixable = _get_prefixable_base_units(conn)
    prefixable_parts = []
    for part_uid, part_exp in parts:
        pref_uid = prefixable.get(part_uid)
        if pref_uid:
            prefixable_parts.append((part_uid, part_exp, pref_uid))

    if not prefixable_parts:
        return None, None

    base_id = base.get("id")
    base_symbol_latex = base.get("symbol_overwrite")
    if not base_symbol_latex:
        from scifind_lib.units import format_compound_unit_symbol
        base_symbol_latex = format_compound_unit_symbol(
            base["unit"],
            unit_symbol=lambda uid: _unit_symbol_for(conn, uid),
            prefix_symbol=lambda exp: _prefix_symbol_for(conn, exp),
        )

    def make_component_section(part_uid, part_exp):
        from scifind_lib.units import format_compound_unit_html, format_compound_unit_symbol
        prefixed = []
        db_prefix_entries = {}
        for row in conn.execute(
            "SELECT id, unit, name_overwrite, symbol_overwrite FROM compound_unit WHERE quantity_id = ? AND is_base = 0",
            (quantity_id,),
        ).fetchall():
            try:
                units = json.loads(row["unit"])
                if isinstance(units, list):
                    for u in units:
                        if isinstance(u, dict) and "prefix" in u and u.get("unit") == part_uid:
                            pref_val = u["prefix"]
                            if pref_val is not None:
                                try:
                                    pref_exp = int(pref_val)
                                    db_prefix_entries[pref_exp] = row
                                except (ValueError, TypeError):
                                    pass
            except (json.JSONDecodeError, TypeError):
                pass

        base_row_exp = 0
        prefixed.append({
            "id": f"{base_id}_{part_uid}_base",
            "exp": base_row_exp,
            "symbol_latex": base_symbol_latex,
            "name": format_compound_unit_html(
                base["unit"], locale=locale,
                unit_name=_unit_name_callback(locale),
                unit_url=lambda uid: f"/unit/{uid}" if uid in _get_unit_name_map() else None,
            ),
            "system_key": "detail.si_base",
            "link_unit_id": None,
            "value_latex": f"10^{{{base_row_exp * part_exp}}}",
        })

        for p in fetch_si_prefixes(conn):
            exp = int(p["id"])
            if exp == base_row_exp:
                continue

            if exp in db_prefix_entries:
                db_entry = db_prefix_entries[exp]
                name_json = db_entry["name_overwrite"]
                if name_json:
                    db_entry_name = localise(name_json, locale)
                    if not db_entry_name:
                        db_entry_name = localise(name_json, "en-us")
                else:
                    db_entry_name = db_entry["id"].replace("_", " ").title()
                sym_overwrite = db_entry["symbol_overwrite"]
                if sym_overwrite:
                    db_sym_latex = sym_overwrite
                else:
                    db_parts = parse_compound_unit(db_entry["unit"])
                    if db_parts and part_uid:
                        prefix_sym = localise(p["symbol"], locale)
                        db_sym_latex = _build_compound_sym_latex(
                            conn, prefix_sym, part_uid, db_parts
                        )
                    else:
                        db_sym_latex = format_compound_unit_symbol(
                            db_entry["unit"],
                            unit_symbol=lambda uid: _unit_symbol_for(conn, uid),
                            prefix_symbol=lambda exp: _prefix_symbol_for(conn, exp),
                        )
                prefixed.append({
                    "id": db_entry["id"],
                    "exp": exp,
                    "symbol_latex": db_sym_latex,
                    "name": db_entry_name,
                    "system_key": None,
                    "link_unit_id": part_uid,
                    "value_latex": f"10^{{{exp * part_exp}}}",
                    "is_db_entry": True,
                })
                continue

            prefix_name_val = localise(p["name"], locale)
            prefix_sym = localise(p["symbol"], locale)
            prefixed_parts = [
                {"unit": uid, "exponent": exp_val, "prefix": exp}
                if uid == part_uid
                else {"unit": uid, "exponent": exp_val}
                for uid, exp_val in parts
            ]
            pref_name_html = format_compound_unit_html(
                json.dumps(prefixed_parts), locale=locale,
                unit_name=_unit_name_callback(locale),
                prefix_name=lambda _exp: prefix_name_val,
                unit_url=lambda uid: f"/unit/{uid}" if uid in _get_unit_name_map() else None,
            )
            pref_sym_latex = _build_compound_sym_latex(
                conn, prefix_sym, part_uid, parts
            )
            prefixed.append({
                "id": f"si_{p['id']}_{part_uid}",
                "exp": exp,
                "symbol_latex": pref_sym_latex,
                "name": pref_name_html,
                "system_key": None,
                "link_unit_id": None,
                "value_latex": f"10^{{{exp * part_exp}}}",
            })

        for r in prefixed:
            is_db_entry = r.get("is_db_entry", False)
            r["collapsed"] = (not is_db_entry) and (r["exp"] not in DEFAULT_VISIBLE_EXPONENTS)
            r["payload_id"] = r["id"] or f"{base_id}_{part_uid}" or "si_base"
        prefixed.sort(key=lambda x: x["exp"], reverse=True)
        return prefixed

    sections = {}
    for part_uid, part_exp, _pref_uid in prefixable_parts:
        part_unit_row = fetch_unit(conn, part_uid)
        if part_unit_row:
            part_name = localise(part_unit_row["name"], locale) or localise(part_unit_row["name"], "en-us")
        else:
            part_name = part_uid.replace("_", " ").title()
        sections[part_uid] = {
            "component": part_uid,
            "label": f"Prefixed on: {part_name}",
            "rows": make_component_section(part_uid, part_exp),
        }

    return sections, cgs_unit_id



@app.context_processor
def inject_globals():
    locale = g.get("locale", "en-us")
    tree = load_tree()
    conn = None
    try:
        conn = get_db()
    except sqlite3.OperationalError as exc:
        logger.warning("Database unavailable: %s", exc)
    # A unit with no path to a root (cycle or orphan) is a hard-stop error.
    if conn is not None:
        from scifind_lib.conversion import UnitGraphError, validate_graph
        try:
            validate_graph(conn)
        except UnitGraphError as exc:
            logger.error("Unit graph integrity violated: %s", exc)
            raise RuntimeError(
                f"Unit reference graph broken: {exc}. "
                f"Fix seed.sql before serving traffic."
            ) from exc
    fs = parse_filter_state(request.args)
    name_map = topic_name_map(tree, locale)
    compressed = compress_selection(tree, fs.ids)

    all_quantities_for_filter = []
    dimension_caches = {"var": {}, "unit": {}, "dim": {}}
    dim_qty_names = {}
    if conn is not None:
        try:
            all_quantities_for_filter = [
                {"id": q["id"], "name": localise(q["name"], locale), "symbol": q["symbol"] or ""}
                for q in fetch_all_quantities(conn)
            ]
        except sqlite3.OperationalError as exc:
            logger.warning("Quantity table unavailable: %s", exc)
        dimension_caches = _get_dimension_caches()
        try:
            qid_to_name = {
                q["id"]: localise(q["name"], locale)
                for q in conn.execute(
                    f"SELECT id, name FROM quantity WHERE id IN ({','.join('?' * len(dimension_quantity_ids()))})",
                    tuple(dimension_quantity_ids().values()),
                ).fetchall()
            }
            for sym, qid in dimension_quantity_ids().items():
                dim_qty_names[sym] = qid_to_name.get(qid, "")
        except sqlite3.OperationalError as exc:
            logger.warning("Base dimension names unavailable: %s", exc)

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
        tree_json=_topic_tree_data(tree, name_map, compressed, fs.exclude_all, ids_provided=fs.ids_provided),
        diff_min=fs.diff_min,
        diff_max=fs.diff_max,
        current_view="quantities" if is_qty_page else "formulas",
        dim_filter=fs.dimension_filter,
        dim_mode=fs.dim_mode,
        qty_mode=fs.quantity_mode,
        all_quantities_for_filter=all_quantities_for_filter,
        dim_symbols=dim_symbols,
        dim_qty_names=dim_qty_names,
        dimension_symbol_list=dimension_symbols() if conn else [],
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


def _items_from_tokens(conn, tokens):
    """Build detail-items-shaped dicts from in-memory RPN tokens + overrides."""
    qids = {tok["quantity_id"] for tok in tokens
            if tok.get("token_kind") == "quantity"}
    cids = {tok["constant_id"] for tok in tokens
            if tok.get("token_kind") == "constant"}
    qrows = {}
    if qids:
        placeholder, qparams = in_clause(qids)
        qrows = {
            r["id"]: r for r in conn.execute(
                f"SELECT id, name, symbol FROM quantity WHERE id IN ({placeholder})", qparams
            ).fetchall()
        }
    crows = {}
    if cids:
        placeholder, cparams = in_clause(cids)
        crows = {
            r["id"]: r for r in conn.execute(
                f"""
                SELECT c.id, c.name, c.symbol,
                       c.unit_id,
                       c.compound_unit_id,
                       rq.id AS related_quantity_id,
                       rq.name AS related_quantity_name,
                       rq.symbol AS related_quantity_symbol
                FROM constant c
                LEFT JOIN quantity rq ON rq.id = c.quantity_id
                WHERE c.id IN ({placeholder})
                """,
                cparams,
            ).fetchall()
        }
    items = []
    for tok in tokens:
        kind = tok.get("token_kind")
        if kind == "quantity":
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
                "name_overwrite": tok.get("name_overwrite") or "",
                "label": tok.get("label") or "",
            })
        elif kind == "constant":
            crow = crows.get(tok["constant_id"])
            if not crow:
                continue
            items.append({
                "constant_id": tok["constant_id"],
                "constant_symbol": crow["symbol"],
                "constant_name": localise(crow["name"], "en-us"),
                "related_quantity_id": crow["related_quantity_id"] or "",
                "related_quantity_name": localise(crow["related_quantity_name"] or "", "en-us") or None,
                "related_quantity_symbol": crow["related_quantity_symbol"] or "",
                "constant_unit_id": crow["unit_id"],
                "constant_compound_unit_id": crow["compound_unit_id"],
            })
    return items


def _format_constant_value(value):
    if value is None:
        return ""
    d = _constant_value_display(value)
    digits = f"{d['int']}.{d['dec']}" if d["dec"] else d["int"]
    if d["exp"] is None:
        return f"{d['sign']}{digits}"
    return f"{d['sign']}{digits} \\times 10^{{{d['exp']}}}"


def _constant_value_display(value):
    """Split a value into {sign, int, dec, exp} for the big display box.

    Large/small magnitudes are normalised to a mantissa in [1, 10) plus
    a 10^exp factor, so the integer digits stay readable.
    """
    v = float(value)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e4 or a < 1e-2:
        exponent = math.floor(math.log10(a)) if a else 0
        mantissa = a / 10 ** exponent
        text = f"{mantissa:.9f}"
        if float(text) >= 10:
            exponent += 1
            mantissa = a / 10 ** exponent
            text = f"{mantissa:.9f}"
        int_part, _, dec = text.rstrip("0").rstrip(".").partition(".")
        return {"sign": sign, "int": int_part, "dec": dec, "exp": exponent}
    int_part, _, dec = f"{a:.10g}".partition(".")
    return {"sign": sign, "int": int_part, "dec": dec, "exp": None}


def _constant_value_latex(display):
    """LaTeX for the big display box; `\\htmlClass` wrappers let the client
    measure the mantissa and fade trailing digits.
    """
    parts = [
        "\\htmlClass{cv-int}{" + display["sign"] + (display["int"] or "0") + "}"
    ]
    if display["dec"]:
        parts.append("\\htmlClass{cv-dot}{.}")
        parts.extend(
            f"\\htmlClass{{cv-dec}}{{{d}}}" for d in display["dec"]
        )
    if display["exp"] is not None:
        parts.append(
            "\\htmlClass{cv-times}{\\times}10^{" + str(display["exp"]) + "}"
        )
    return "".join(parts)


def _constant_units_table(conn, c, system):
    """Per-unit value rows for a constant, converting via the unit graph; preferred unit first."""
    si_value = c.get("value")
    rq_id = c.get("quantity_id")
    if si_value is None or not rq_id:
        return []

    locale = g.locale
    base = None
    if c.get("unit_id"):
        base = unit_by_id(conn, c["unit_id"])
    elif c.get("compound_unit_id"):
        base = compound_unit_by_id(conn, c["compound_unit_id"])
    if base is None:
        base = select_base_unit_with_fallback(conn, rq_id, system)
    default_unit_html, default_unit_symbol = (
        _render_compound_unit(base, locale) if base else (Markup(""), "")
    )

    graph = UnitGraph(conn, rq_id)
    base_unit_ids = set()
    if base and base["kind"] == "compound_unit":
        base_unit_ids = {uid for uid, _ in parse_compound_unit(base["unit"])}
    elif base:
        base_unit_ids = {base["id"]}
    base_system = base["system"] if base else "SI"

    units_rows = []
    if base:
        units_rows.append({
            "symbol_latex": default_unit_symbol,
            "name_html": default_unit_html,
            "system": base_system,
            "value_latex": _format_constant_value(si_value),
        })

    seen_values = {units_rows[0]["value_latex"]} if units_rows else set()
    for eu_row in fetch_quantity_units(conn, rq_id):
        eu = dict(eu_row)
        if eu["id"] in base_unit_ids:
            continue
        converted = convert_value(si_value, base["id"], eu["id"], graph)
        if converted is None:
            continue
        value_latex = _format_constant_value(converted)
        if value_latex in seen_values:
            continue
        seen_values.add(value_latex)
        units_rows.append({
            "symbol_latex": Markup(wrap_symbol_in_latex(eu["symbol"])),
            "name_html": _unit_name_link(eu["id"]),
            "system": eu.get("system") or "any",
            "value_latex": value_latex,
        })
    return units_rows


def _constant_detail_item(conn, item, locale):
    cid = item.get("constant_id")
    if not cid:
        return None
    name = item.get("constant_name") or cid.replace("_", " ").title()
    name_html = build_entity_link("constant", cid, name)
    rq_id = item.get("related_quantity_id")
    rq_name = item.get("related_quantity_name")
    rq_symbol = (item.get("related_quantity_symbol") or "").strip()
    paren_parts = []
    if rq_name:
        paren_parts.append(f"${rq_symbol}$" if rq_symbol else "")
        paren_parts.append(build_entity_link("quantity", rq_id, rq_name))
    paren_html = f"({' '.join(part for part in paren_parts if part)})" if rq_name else ""

    base = None
    if item.get("constant_unit_id"):
        base = unit_by_id(conn, item["constant_unit_id"])
    elif item.get("constant_compound_unit_id"):
        base = compound_unit_by_id(conn, item["constant_compound_unit_id"])
    if base is None and item.get("related_quantity_id"):
        base = select_base_unit_with_fallback(conn, item["related_quantity_id"], g.unit_system)
    unit_html, unit_sym = _render_compound_unit(base, locale)
    return {
        "symbol_latex": item.get("constant_symbol") or "",
        "name_html": Markup(name_html),
        "paren_html": Markup(paren_html) if paren_html else "",
        "default_unit_html": unit_html,
        "default_unit_symbol_latex": unit_sym,
    }


def _build_formula_detail_items(conn, formula_id, locale, tokens=None):
    """Build the formula detail table data from formula_id or in-memory tokens."""
    if tokens is None:
        items = [dict(r) for r in fetch_formula_token_quantities(conn, formula_id)]
    else:
        items = _items_from_tokens(conn, tokens)

    result = []
    for item in items:
        qid = item.get("quantity_id")
        if not qid:
            const_item = _constant_detail_item(conn, item, locale)
            if const_item:
                result.append(const_item)
            continue

        symbol_latex = render_variable_symbol(item, locale)
        qty_name = item.get("quantity_name") or qid.replace("_", " ").title()
        orig_symbol = (item.get("quantity_symbol") or "").strip()
        overwrite = localise(item.get("symbol_overwrite") or "", locale)
        has_overwrite = bool(overwrite and orig_symbol and overwrite != orig_symbol)
        no_raw = localise(item.get("name_overwrite") or "", locale)
        qlink = build_entity_link("quantity", qid, qty_name)

        paren_parts = []
        if has_overwrite and orig_symbol:
            paren_parts.append(f"${orig_symbol}$")

        if no_raw:
            marker_ids = set()
            for m in re.finditer(r"\[\s*([^\]]+)\]", no_raw):
                qid_from_marker = m.group(1).strip().split("|", 1)[0].strip().lower().replace(" ", "_")
                if re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", qid_from_marker):
                    marker_ids.add(qid_from_marker)
            if qid in marker_ids:
                name_html = expand_quantity_markers(no_raw)
            else:
                name_html = html_module.escape(no_raw)
                if has_overwrite and orig_symbol:
                    paren_parts.append(qlink)
        else:
            name_html = qlink

        paren_html = f"({' '.join(paren_parts)})" if paren_parts else ""
        base = select_base_unit_with_fallback(conn, qid, g.unit_system)
        unit_html, unit_sym = _render_compound_unit(base, locale)

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
    conn = get_db()
    locale = g.locale
    row = fetch_formula(conn, formula_id)
    if not row:
        return "Formula not found", 404
    row = dict(row)
    _attach_breadcrumbs(row, locale)
    latex = render_formula_latex(conn, formula_id, locale=locale)
    related = []
    for r in fetch_formula_relations(conn, formula_id):
        r["latex"] = render_formula_latex(conn, r["related_id"], locale=locale)
        related.append(r)
    detail_items = _build_formula_detail_items(conn, formula_id, locale)

    links = []
    if row.get("links"):
        try:
            links = json.loads(row["links"])
            if not isinstance(links, list):
                links = []
        except (ValueError, TypeError):
            links = []

    dim_caches = _get_dimension_caches()
    dimensions = compute_formula_dimensions(conn, formula_id)
    dim_latex = format_dimensions_latex(
        *dimensions,
        variable_symbols=dim_caches["var"],
        unit_symbols=dim_caches["unit"],
        dim_symbols=dim_caches["dim"],
        mode=g.get("dim_mode", "dim"),
    )
    formula_sql, token_sql = build_formula_insert_sql(conn, formula_id)
    return render_template(
        "formula.html",
        formula=row, latex=latex,
        relations=related, detail_items=detail_items,
        dim_latex=dim_latex, links=links,
        formula_sql=formula_sql, token_sql=token_sql,
    )


@app.route("/quantity/<quantity_id>")
def quantity_detail(quantity_id):
    conn = get_db()
    locale = g.locale
    q = fetch_quantity(conn, quantity_id)
    if not q:
        return "Quantity not found", 404
    q = dict(q)
    _attach_breadcrumbs(q, locale)
    primary_formulas, non_primary_formulas = fetch_quantity_formulas_by_side(conn, quantity_id)
    primary_formulas = [dict(f) for f in primary_formulas]
    non_primary_formulas = [dict(f) for f in non_primary_formulas]
    for formulas in (primary_formulas, non_primary_formulas):
        for f in formulas:
            f["latex"] = render_formula_latex(conn, f["id"], locale=locale) or ""
    related_formulas = []
    for r in fetch_quantity_related_formulas(conn, quantity_id):
        r = dict(r)
        r["latex"] = render_formula_latex(conn, r["id"], locale=locale)
        related_formulas.append(r)

    units_table = _quantity_units_table(conn, quantity_id, g.unit_system)
    units = units_table["units"]

    dim_caches = _get_dimension_caches()
    dim_latex = format_dimensions_latex(
        *dimensions_from_row(q),
        variable_symbols=dim_caches["var"],
        unit_symbols=dim_caches["unit"],
        dim_symbols=dim_caches["dim"],
        mode=g.get("dim_mode", "dim"),
    )
    constants = []
    for const in fetch_quantity_constants(conn, quantity_id):
        const = dict(const)
        const["value_latex"] = _format_constant_value(const["value"])
        if const.get("unit_id"):
            base = unit_by_id(conn, const["unit_id"])
        elif const.get("compound_unit_id"):
            base = compound_unit_by_id(conn, const["compound_unit_id"])
        else:
            base = None
        _, const["unit_symbol_latex"] = _render_compound_unit(base, g.locale) if base else (Markup(""), "")
        constants.append(const)
    return render_template(
        "quantity.html",
        q=q,
        units=units,
        primary_formulas=primary_formulas,
        nonprimary_formulas=non_primary_formulas,
        related_formulas=related_formulas,
        constants=constants,
        dim_latex=dim_latex,
        table_data=units_table["payload"],
        si_prefixes=units_table["si_prefixes"],
        si_prefix_sections=units_table["si_prefix_sections"],
    )


@app.route("/constant/<constant_id>")
def constant_detail(constant_id):
    conn = get_db()
    locale = g.locale
    c = fetch_constant(conn, constant_id)
    if not c:
        return "Constant not found", 404
    c = dict(c)
    if c["related_quantity_id"]:
        _attach_breadcrumbs(c, locale)
        c["quantity_name_localized"] = (
            localise(c["related_quantity_name"], locale)
            or localise(c["related_quantity_name"], "en-us")
        )

    links = []
    if c.get("links"):
        try:
            links = json.loads(c["links"])
            if not isinstance(links, list):
                links = []
        except (ValueError, TypeError):
            links = []

    formulas = []
    for f in fetch_constant_formulas(conn, constant_id):
        f = dict(f)
        f["latex"] = render_formula_latex(conn, f["id"], locale=locale) or ""
        formulas.append(f)

    dim_caches = _get_dimension_caches()
    if c.get("unit_id"):
        base = unit_by_id(conn, c["unit_id"])
    elif c.get("compound_unit_id"):
        base = compound_unit_by_id(conn, c["compound_unit_id"])
    else:
        base = None
    compound_unit_json = (base["unit"]
                          if base and base["kind"] == "compound_unit" else None)
    dim_latex = format_dimensions_latex(
        *compute_compound_unit_dimensions(conn, compound_unit_json),
        variable_symbols=dim_caches["var"],
        unit_symbols=dim_caches["unit"],
        dim_symbols=dim_caches["dim"],
        mode=g.get("dim_mode", "dim"),
    )

    display = _constant_value_display(c["value"]) if c.get("value") is not None else None
    _, unit_symbol_latex = _render_compound_unit(base, g.locale)
    units = _constant_units_table(conn, c, g.unit_system)

    return render_template(
        "constant.html",
        constant=c,
        links=links,
        formulas=formulas,
        dim_latex=dim_latex,
        display=display,
        value_latex=_constant_value_latex(display) if display else "",
        unit_symbol_latex=unit_symbol_latex,
        units=units,
    )


@app.route("/unit/<unit_id>")
def unit_detail(unit_id):
    conn = get_db()
    unit = fetch_unit(conn, unit_id)
    if not unit:
        return "Unit not found", 404
    unit = dict(unit)
    locale = g.locale
    qty = fetch_quantity(conn, unit["quantity_id"])
    unit["quantity_name_localized"] = localise(qty["name"], locale) if qty else unit.get("quantity_id", "")
    _attach_breadcrumbs(unit, locale)
    units = table_data = si_prefixes = si_prefix_sections = None
    if qty:
        # On a unit's own page the reference unit is that unit.
        units_table = _quantity_units_table(
            conn, unit["quantity_id"], g.unit_system, ref_unit_id=unit_id,
        )
        units = units_table["units"]
        table_data = units_table["payload"]
        si_prefixes = units_table["si_prefixes"]
        si_prefix_sections = units_table["si_prefix_sections"]
    return render_template(
        "unit.html",
        unit=unit,
        units=units,
        table_data=table_data,
        si_prefixes=si_prefixes,
        si_prefix_sections=si_prefix_sections,
        fixed_ref=True,
    )


@app.route("/search")
def search_page():
    query = request.args.get("q", "").strip()[:SEARCH_QUERY_MAX_LENGTH]
    conn = get_db()
    locale = g.locale
    sort_key = _resolve_sort(request.args.get("sort"), SEARCH_SORT_KEYS, DEFAULT_SEARCH_SORT)
    hits = search_entities(conn, query, locale=locale)
    hits = sort_search_rows(conn, hits, sort_key, locale)
    results = _enrich_search_hits(conn, hits, locale)
    return render_template(
        "search.html",
        query=query,
        results=results,
        sort=sort_key,
        available_sorts=SEARCH_SORT_KEYS,
    )


def _enrich_search_hits(conn, hits, locale):
    """Attach latex / symbol data to each search hit so the template can
    render formula-card style entries."""
    formula_ids, quantity_ids, unit_ids, constant_ids = (
        [h[1] for h in hits if h[0] == k] for k in ("formula", "quantity", "unit", "constant")
    )

    def _meta(sql, ids, row_to_meta):
        if not ids:
            return {}
        placeholder, params = in_clause(ids)
        return {r["id"]: row_to_meta(r) for r in conn.execute(
            f"{sql} WHERE id IN ({placeholder})", params,
        ).fetchall()}

    formula_meta = _meta(
        "SELECT id, json_extract(name, '$.en-us') AS name_en FROM formula",
        formula_ids,
        lambda r: {"name_en": r["name_en"] or r["id"]},
    )
    quantity_meta = _meta(
        "SELECT id, symbol FROM quantity",
        quantity_ids,
        lambda r: {"symbol": r["symbol"] or ""},
    )
    unit_meta = _meta(
        "SELECT u.id, u.symbol, u.name FROM unit u",
        unit_ids,
        lambda r: {"symbol": r["symbol"] or "",
                   "name": localise(r["name"], locale) if r["name"] else r["id"]},
    )
    constant_meta = _meta(
        "SELECT id, symbol FROM constant",
        constant_ids,
        lambda r: {"symbol": r["symbol"] or ""},
    )

    enriched = []
    for kind, ent_id, display_name in hits:
        if kind == "formula":
            meta = formula_meta.get(ent_id, {})
            enriched.append({
                "kind": kind, "id": ent_id,
                "href": f"/formula/{ent_id}",
                "latex": render_formula_latex(conn, ent_id, locale),
                "name": display_name or meta.get("name_en", ent_id),
                "relation": _("detail.formula"),
            })
        elif kind == "quantity":
            meta = quantity_meta.get(ent_id, {})
            enriched.append({
                "kind": kind, "id": ent_id,
                "href": f"/quantity/{ent_id}",
                "symbol": meta.get("symbol", ""),
                "name": display_name or ent_id,
                "relation": _("detail.quantity"),
            })
        elif kind == "unit":
            meta = unit_meta.get(ent_id, {})
            enriched.append({
                "kind": kind, "id": ent_id,
                "href": f"/unit/{ent_id}",
                "symbol": meta.get("symbol", ""),
                "name": display_name or meta.get("name", ent_id),
                "relation": _("detail.unit"),
            })
        elif kind == "constant":
            meta = constant_meta.get(ent_id, {})
            enriched.append({
                "kind": kind, "id": ent_id,
                "href": f"/constant/{ent_id}",
                "symbol": meta.get("symbol", ""),
                "name": display_name or ent_id,
                "relation": _("detail.constant"),
            })
    return enriched


@app.route("/api/search-suggestions")
def search_suggestions():
    query = request.args.get("q", "").strip()[:SUGGEST_QUERY_MAX_LENGTH]
    locale = getattr(g, "locale", DEFAULT_LOCALE)
    suggestions = suggest_entities(get_db(), query, locale=locale)
    return {"suggestions": [
        {"id": s[0], "kind": s[1], "heading": s[2] or s[0]} for s in suggestions
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
        if field not in ("symbol", "name"):
            continue
        value = next((v for v in reversed(values) if v.strip()), "")
        if not value:
            continue
        overrides.setdefault(ov_key, {})[field] = value
    return overrides


@app.route("/create/preview-render", methods=["POST"])
def create_preview_render():
    """Form-POST version of /api/preview that also returns detail_items HTML."""
    equation = (request.form.get("equation") or "").strip()
    if len(equation) > CREATE_EQUATION_MAX_LENGTH:
        return {"error": f"equation exceeds {CREATE_EQUATION_MAX_LENGTH} characters"}, 400
    conn = get_db()
    locale = g.locale
    overrides = _parse_override_form_keys()
    caches = _get_dimension_caches()
    result = parse_and_preview_equation(conn, equation, locale=locale, dim_caches=caches, overrides=overrides, dim_mode=g.get("dim_mode", "dim"))
    if result.get("error") or not result.get("latex"):
        return result
    items = _build_formula_detail_items(conn, None, locale, tokens=result["tokens"])
    result["detail_items"] = items
    return result


def _operator_latex(item):
    """Generate LaTeX for an operator in the token sidebar."""
    op_id = item["id"]
    symbol = item.get("symbol") or ""
    op_type = item["operator_type"]
    x, y = "x", "y"
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
    conn = get_db()
    locale = g.locale
    no_results = _("create.no_results")
    sections = [
        _render_token_section(
            _("detail.quantities"), "token-qty",
            fetch_all_quantities(conn), "qty", locale, no_results,
        ),
        _render_token_section(
            _("nav.constants"), "token-const",
            fetch_all_constants(conn), "const", locale, no_results,
        ),
        _render_token_section(
            _("nav.operators"), "token-op",
            fetch_all_operators(conn), "op", locale, no_results,
        ),
    ]

    return Markup(
        '<div class="filter-qty-search-wrap">'
        f'<input type="text" class="text-field" id="token-search" placeholder="{html_module.escape(_("create.search_placeholder"))}" autocomplete="off">'
        '</div>'
        f'<div class="token-sidebar">{"".join(sections)}</div>'
    )


def _render_breadcrumb(selected_id, tree, name_map):
    """Server-rendered topic breadcrumb (root > ... > selected > child trigger)."""
    selected_node = _find_node(tree, selected_id) if selected_id else None
    if selected_node is not None:
        kids = selected_node.get("children") or []
        path = topic_path(tree, selected_id) or [selected_id]
    else:
        kids = tree
        path = None

    parts = []
    if path:
        for i, tid in enumerate(path):
            if i > 0:
                parts.append(' &gt; ')
            parts.append(
                f'<span class="topic-current"'
                f' data-id="{html_module.escape(tid)}">'
                f'{html_module.escape(name_map.get(tid, tid))}</span>'
            )

    if kids:
        if parts:
            parts.append(' &gt; ')
        trigger_label = _("create.topic")
        menu_items = "".join(
            _render_menu_item(kid, name_map) for kid in kids
        )
        parts.append(
            f'<span class="topic-current has-menu" data-text="{html_module.escape(trigger_label)}">'
            f'<button class="topic-dropdown-trigger" type="button">'
            f'{html_module.escape(trigger_label)}</button>'
            f'<div class="topic-children-menu">{menu_items}</div>'
            f'</span>'
        )
    return Markup("".join(parts))


def _find_node(tree, node_id):
    found = []
    def visit(node):
        if node["id"] == node_id:
            found.append(node)
    walk_tree(tree, visit)
    return found[0] if found else None


def _render_menu_item(node, name_map):
    """One entry of the topic dropdown; `node` is a tree.json node dict."""
    node_id = node["id"]
    name = name_map.get(node_id, node_id)
    kids = node.get("children") or []
    if kids:
        sub = "".join(_render_menu_item(c, name_map) for c in kids)
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
    topic = (request.args.get("topic") or "").strip() or None
    tree = load_tree()
    name_map = topic_name_map(tree, g.locale)
    return _render_breadcrumb(topic, tree, name_map)


@app.route("/create/languages")
def create_languages():
    """Available locales plus the GitHub repo slug for new-issue links."""
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


def _build_create_sql_payload(conn, form):
    """Parse the /create form fields and return (formula_sql, token_sql)."""
    def scalar(name):
        return (form.get(name) or "").strip()

    name_en = scalar("name_en")
    formula_id = scalar("formula_id")
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
        top = tr_top.get(loc, {})
        entry = {k: top[k] for k in ("name", "description") if k in top}
        if loc in tr_ov:
            entry["overrides"] = tr_ov[loc]
        if entry:
            translations[loc] = entry

    return build_create_sql(
        conn,
        name_en=name_en,
        topic=topic,
        difficulty=difficulty,
        equation=equation,
        overrides=overrides,
        description=description,
        links=links,
        translations=translations,
        formula_id=formula_id,
    )


def _render_sql_modal_html(formula_sql, token_sql):
    return Markup(
        '<div class="sql-block">'
        f'<button class="formula-copy-btn" type="button" data-action="copy-formula-sql" title="Copy">'
        f'<i data-lucide="copy" width="16" height="16"></i>'
        f'</button>'
        f'<pre id="formula-sql">{html_module.escape(formula_sql)}</pre>'
        f'</div>'
        '<h3>' + html_module.escape(_("create.token_inserts")) + '</h3>'
        '<div class="sql-block">'
        f'<button class="formula-copy-btn" type="button" data-action="copy-token-sql" title="Copy">'
        f'<i data-lucide="copy" width="16" height="16"></i>'
        f'</button>'
        f'<pre id="token-sql">{html_module.escape(token_sql)}</pre>'
        f'</div>'
    )


@app.route("/create/build-sql", methods=["POST"])
def create_build_sql():
    """Form-POST equivalent of /api/build-sql returning rendered modal HTML."""
    equation = (request.form.get("equation") or "")
    if len(equation) > CREATE_EQUATION_MAX_LENGTH:
        body = (
            f'<p class="detail-desc" data-error="equation-too-long">'
            f'equation exceeds {CREATE_EQUATION_MAX_LENGTH} characters</p>'
        )
        return Markup(body), 400
    conn = get_db()
    try:
        formula_sql, token_sql = _build_create_sql_payload(conn, request.form)
    except ValueError as e:
        body = (
            f'<p class="detail-desc" data-error="{html_module.escape(str(e))}">'
            f'{html_module.escape(str(e))}</p>'
        )
        return Markup(body), 400
    return _render_sql_modal_html(formula_sql, token_sql)


@app.route("/quantities")
def all_quantities():
    conn = get_db()
    locale = g.locale
    fs = parse_filter_state(request.args)
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

    raw_quantities = [q for q in fetch_all_quantities(conn)]
    topic_filter = _filtered_ids_for_query(tree, fs.ids)
    dim_qty_ids = set(dimension_quantity_ids().values()) if fs.base_quantity_only else None
    system = g.unit_system
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

        cu = select_base_unit_with_fallback(conn, q["id"], system)
        q["default_unit_html"], q["default_unit_symbol_latex"] = _render_compound_unit(cu, locale)
        filtered.append(q)

    filtered = sort_quantities(filtered, sort_key, locale)

    heading = _render_list_heading(
        _("detail.quantities"), tree, compressed, fs, conn, locale,
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
    conn = get_db()
    locale = g.locale
    fs = parse_filter_state(request.args)
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

    formulas = [dict(f) for f in fetch_all_formulas(conn)]
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
        dim_map = compute_all_formula_dimensions(conn, formula_ids)
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
        matching_ids = quantity_match(conn, fs.quantity_ids)
        if matching_ids is not None:
            formulas = [f for f in formulas if f["id"] in matching_ids]

    formulas = sort_formulas(conn, formulas, sort_key, locale)

    for f in formulas:
        _attach_breadcrumbs(f, locale)
        f["latex"] = render_formula_latex(conn, f["id"], locale=locale)

    heading = _render_list_heading(
        _("nav.formulas"), tree, compressed, fs, conn, locale,
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
    limited = _rate_limit("export:" + _client_key(), 6)
    if limited is not None:
        return limited
    fmt = request.args.get("format") or request.cookies.get("sf_export_format", "csv")
    conn = get_db()

    def _respond(data, mimetype, filename):
        resp = Response(data, mimetype=mimetype, headers={"Content-Disposition": f"attachment; filename={filename}"})
        resp.set_cookie("sf_export_format", fmt, max_age=365*24*3600, path="/")
        return resp

    def _binary_export(export_fn, mimetype, filename):
        buffer = io.BytesIO()
        export_fn(conn, buffer)
        buffer.seek(0)
        return _respond(buffer.getvalue(), mimetype, filename)

    if fmt == "sql":
        return _respond(export_to_sql(conn).encode("utf-8"),
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
        with tempfile.TemporaryDirectory() as tmpdir:
            export_to_csv_directory(conn, tmpdir)
            for p in Path(tmpdir).iterdir():
                zf.write(p, p.name)
    buffer.seek(0)
    return _respond(buffer.getvalue(), "application/zip", "scifind_csv.zip")


if __name__ == "__main__":
    host = os.environ.get("SCIFIND_HOST", "127.0.0.1")
    port = int(os.environ.get("SCIFIND_PORT", "5000"))
    debug = os.environ.get("SCIFIND_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)