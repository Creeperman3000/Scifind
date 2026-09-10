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
import time
from pathlib import Path

from flask import Flask, render_template, request, g, Response, redirect, session, url_for
from markupsafe import Markup

_PROJECT_DIR = Path(__file__).resolve().parent
_LOCALE_DIR = _PROJECT_DIR / "locales"
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from scifind_lib.db import (
    database_has_formula_table,
    database_path,
    initialize_database,
    open_database,
)
from scifind_lib.formula import (
    build_dimension_symbol_triplet,
    format_dimensions_latex,
)
from scifind_lib.i18n import load_locale_config, localise, locale_sibilants, wrap_symbol_in_latex
from scifind_lib.fetch import (
    DEFAULT_FORMULA_SORT,
    DEFAULT_QUANTITY_SORT,
    DEFAULT_SEARCH_SORT,
    FORMULA_SORT_KEYS,
    MAX_DIFFICULTY,
    MIN_DIFFICULTY,
    QUANTITY_SORT_KEYS,
    SEARCH_SORT_KEYS,
    fetch_all_quantities,
    fetch_quantities_by_ids,
    parse_filter_state,
)
from scifind_lib.tree import (
    all_tree_ids,
    compress_selection,
    expand_selection,
    load_tree,
    topic_name_map,
    topic_path,
    topic_tree_order,
    walk_tree,
)
from scifind_lib.constants import SUPERSCRIPT_DIGITS, is_slug
from scifind_lib.formula import dimension_symbols, dimension_quantity_ids

from scifind_lib.conversion import UnitGraph, convert_value
from scifind_lib.formula import (
    compute_all_formula_dimensions,
    compute_compound_unit_dimensions,
    compute_formula_dimensions,
    dimension_matches,
    dimensions_from_row,
    parse_and_preview_equation,
    render_formula_latex,
)
from scifind_lib.display import (
    build_entity_link,
    expand_quantity_markers,
    quantity_units_table,
    render_compound_unit,
    render_variable_symbol,
    unit_name_link,
)
from scifind_lib.export import (
    build_create_sql,
    build_formula_insert_sql,
    export_to_csv_zip,
    export_to_ods,
    export_to_sql,
    export_to_xlsx,
)
from scifind_lib.fetch import (
    fetch_all_constants,
    fetch_all_formulas,
    fetch_all_operators,
    fetch_constant,
    fetch_constant_formulas,
    fetch_formula,
    fetch_formula_relations,
    fetch_formula_token_quantities,
    fetch_formulas_with_all_quantities,
    fetch_formulas_with_any_quantity,
    fetch_keyed_rows,
    fetch_quantity,
    fetch_quantity_constants,
    fetch_quantity_formulas_by_side,
    fetch_quantity_related_formulas,
    fetch_quantity_units,
    fetch_search_meta,
    fetch_unit,
    search_entities,
    sort_formulas,
    sort_quantities,
    sort_search_rows,
    suggest_entities,
)
from scifind_lib.units import (
    compound_unit_by_slug,
    parse_compound_unit,
    select_base_unit_with_fallback,
    unit_by_id,
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


def _passes_topic_difficulty(item, topic_filter, fs):
    """Shared topic + difficulty gate for the quantities/formulas list pages."""
    if topic_filter and item.get("topic_id") not in topic_filter:
        return False
    diff = item.get("difficulty")
    return diff is None or fs.diff_min <= diff <= fs.diff_max


def _all_tree_root_ids(tree):
    return {r["id"] for r in tree}


def _localised_quantity_names(conn, quantity_ids, locale):
    if not quantity_ids:
        return []
    names_by_id = fetch_quantities_by_ids(conn, quantity_ids)
    return [localise(names_by_id[qid], locale) for qid in quantity_ids
            if qid in names_by_id]


_LATEX_TEXTCMD_RE = re.compile(r"\\(?:mathrm|text)\{([^}]*)\}")


def _strip_textcmd(latex):
    return _LATEX_TEXTCMD_RE.sub(r"\1", latex)


def _join_names(names, locale="en-us", conj_key="heading.and"):
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    locales = _available_locales()
    cat, _, child = conj_key.partition(".")
    conj = None
    for loc in _locale_chain(locale):
        conj = locales.get(loc, {}).get("ui", {}).get(cat, {}).get(child)
        if conj is not None:
            break
    if not isinstance(conj, str):
        conj = locales.get(DEFAULT_LOCALE, {}).get("ui", {}).get(cat, {}).get(child)
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
    gen_map = {}
    def visit(node):
        genitive = (node.get("translations") or {}).get("cs-cz-gen")
        if genitive:
            gen_map[node["id"]] = genitive
    walk_tree(tree, visit)
    return gen_map


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
def _(blob_or_key):
    """Resolve a DB i18n JSON blob or a UI-string key for the current locale."""
    loc = getattr(g, "locale", DEFAULT_LOCALE)
    if blob_or_key and blob_or_key.strip().startswith("{"):
        result = localise(blob_or_key, loc)
        if result:
            return result
    return _ui_lookup(loc, blob_or_key)


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


_SORT_CONTEXT_BY_PATH = (
    ("/search", SEARCH_SORT_KEYS, DEFAULT_SEARCH_SORT),
    ("/quantities", QUANTITY_SORT_KEYS, DEFAULT_QUANTITY_SORT),
)


def _sort_context_for(path, raw_value):
    allowed, default = next(
        ((a, d) for prefix, a, d in _SORT_CONTEXT_BY_PATH if path.startswith(prefix)),
        (FORMULA_SORT_KEYS, DEFAULT_FORMULA_SORT),
    )
    return {
        "available_sorts": allowed,
        "default_sort": default,
        "sort": _resolve_sort(raw_value, allowed, default),
    }

def _items_from_tokens(conn, tokens):
    """Build detail-items-shaped dicts from in-memory RPN tokens + overrides."""
    qids = {tok["quantity_id"] for tok in tokens
            if tok.get("token_kind") == "quantity"}
    cids = {tok["constant_id"] for tok in tokens
            if tok.get("token_kind") == "constant"}
    qrows = fetch_keyed_rows(
        conn, "SELECT id, name, symbol FROM quantity WHERE id IN ({})", qids,
    )
    crows = fetch_keyed_rows(
        conn,
        "SELECT c.id, c.name, c.symbol,"
        " c.unit_id, c.compound_unit_id,"
        " rq.id AS related_quantity_id,"
        " rq.name AS related_quantity_name,"
        " rq.symbol AS related_quantity_symbol"
        " FROM constant c"
        " LEFT JOIN quantity rq ON rq.id = c.quantity_id"
        " WHERE c.id IN ({})",
        cids,
    )
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
    display_parts = _constant_value_display(value)
    digits = f"{display_parts['int']}.{display_parts['dec']}" if display_parts["dec"] else display_parts["int"]
    if display_parts["exp"] is None:
        return f"{display_parts['sign']}{digits}"
    return f"{display_parts['sign']}{digits} \\times 10^{{{display_parts['exp']}}}"


def _constant_value_display(value):
    """Split a value into {sign, int, dec, exp}; large/small magnitudes use a mantissa in [1, 10)."""
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
    """LaTeX for the big display box; wrappers let the client measure the mantissa."""
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


def _constant_units_table(conn, constant, system):
    """Per-unit value rows for a constant, converting via the unit graph; preferred unit first."""
    si_value = constant.get("value")
    rq_id = constant.get("quantity_id")
    if si_value is None or not rq_id:
        return []

    locale = g.locale
    base = None
    if constant.get("unit_id"):
        base = unit_by_id(conn, constant["unit_id"])
    elif constant.get("compound_unit_id"):
        base = compound_unit_by_slug(conn, constant["compound_unit_id"])
    if base is None:
        base = select_base_unit_with_fallback(conn, rq_id, system)
    default_unit_html, default_unit_symbol = (
        render_compound_unit(base, locale) if base else (Markup(""), "")
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
            "name_html": unit_name_link(eu["id"]),
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
        base = compound_unit_by_slug(conn, item["constant_compound_unit_id"])
    if base is None and item.get("related_quantity_id"):
        base = select_base_unit_with_fallback(conn, item["related_quantity_id"], g.unit_system)
    unit_html, unit_sym = render_compound_unit(base, locale)
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
                if is_slug(qid_from_marker):
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
        unit_html, unit_sym = render_compound_unit(base, locale)

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
    quantity = fetch_quantity(conn, quantity_id)
    if not quantity:
        return "Quantity not found", 404
    quantity = dict(quantity)
    _attach_breadcrumbs(quantity, locale)
    primary_formulas, non_primary_formulas = fetch_quantity_formulas_by_side(conn, quantity_id)
    primary_formulas = [dict(formula) for formula in primary_formulas]
    non_primary_formulas = [dict(formula) for formula in non_primary_formulas]
    for formulas in (primary_formulas, non_primary_formulas):
        for formula in formulas:
            formula["latex"] = render_formula_latex(conn, formula["id"], locale=locale) or ""
    related_formulas = []
    for r in fetch_quantity_related_formulas(conn, quantity_id):
        r = dict(r)
        r["latex"] = render_formula_latex(conn, r["id"], locale=locale)
        related_formulas.append(r)

    units_table = quantity_units_table(conn, quantity_id, g.unit_system, tr=_)
    units = units_table["units"]

    dim_caches = _get_dimension_caches()
    dim_latex = format_dimensions_latex(
        *dimensions_from_row(quantity),
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
            base = compound_unit_by_slug(conn, const["compound_unit_id"])
        else:
            base = None
        _html, const["unit_symbol_latex"] = render_compound_unit(base, g.locale) if base else (Markup(""), "")
        constants.append(const)
    return render_template(
        "quantity.html",
        q=quantity,
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
    constant = fetch_constant(conn, constant_id)
    if not constant:
        return "Constant not found", 404
    constant = dict(constant)
    if constant["related_quantity_id"]:
        _attach_breadcrumbs(constant, locale)
        constant["quantity_name_localized"] = (
            localise(constant["related_quantity_name"], locale)
            or localise(constant["related_quantity_name"], "en-us")
        )

    links = []
    if constant.get("links"):
        try:
            links = json.loads(constant["links"])
            if not isinstance(links, list):
                links = []
        except (ValueError, TypeError):
            links = []

    formulas = []
    for formula in fetch_constant_formulas(conn, constant_id):
        formula = dict(formula)
        formula["latex"] = render_formula_latex(conn, formula["id"], locale=locale) or ""
        formulas.append(formula)

    dim_caches = _get_dimension_caches()
    if constant.get("unit_id"):
        base = unit_by_id(conn, constant["unit_id"])
    elif constant.get("compound_unit_id"):
        base = compound_unit_by_slug(conn, constant["compound_unit_id"])
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

    display = _constant_value_display(constant["value"]) if constant.get("value") is not None else None
    _, unit_symbol_latex = render_compound_unit(base, g.locale)
    units = _constant_units_table(conn, constant, g.unit_system)

    return render_template(
        "constant.html",
        constant=constant,
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
        units_table = quantity_units_table(
            conn, unit["quantity_id"], g.unit_system, ref_unit_id=unit_id, tr=_,
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



SEARCH_QUERY_MAX_LENGTH = 200
SUGGEST_QUERY_MAX_LENGTH = 50

@app.route("/")
def index():
    return redirect("/formulas")


@app.route("/base-units")
def base_units_page():
    return redirect("/quantities?is_dim=1")




@app.route("/search")
def search_page():
    query = request.args.get("q", "").strip()[:SEARCH_QUERY_MAX_LENGTH]
    conn = get_db()
    locale = g.locale
    sort_key = _resolve_sort(request.args.get("sort"), SEARCH_SORT_KEYS, DEFAULT_SEARCH_SORT)
    hits = search_entities(conn, query, locale=locale)
    meta_by_kind = fetch_search_meta(conn, hits)
    hits = sort_search_rows(conn, hits, sort_key, locale, meta_by_kind)
    results = _enrich_search_hits(conn, hits, locale, meta_by_kind)
    return render_template(
        "search.html",
        query=query,
        results=results,
        sort=sort_key,
        available_sorts=SEARCH_SORT_KEYS,
    )


def _enrich_search_hits(conn, hits, locale, meta_by_kind=None):
    """Attach latex / symbol data to each search hit for card-style rendering."""
    if meta_by_kind is None:
        meta_by_kind = fetch_search_meta(conn, hits)
    formula_meta = meta_by_kind.get("formula", {})
    quantity_meta = meta_by_kind.get("quantity", {})
    unit_meta = meta_by_kind.get("unit", {})
    constant_meta = meta_by_kind.get("constant", {})

    enriched = []
    for kind, ent_id, display_name in hits:
        if kind == "formula":
            meta = formula_meta.get(ent_id, {})
            enriched.append({
                "kind": kind, "id": ent_id,
                "href": f"/formula/{ent_id}",
                "latex": render_formula_latex(conn, ent_id, locale),
                "name": display_name or meta.get("name_en") or ent_id,
                "relation": _("detail.formula"),
            })
        elif kind == "quantity":
            meta = quantity_meta.get(ent_id, {})
            enriched.append({
                "kind": kind, "id": ent_id,
                "href": f"/quantity/{ent_id}",
                "symbol": meta.get("symbol") or "",
                "name": display_name or ent_id,
                "relation": _("detail.quantity"),
            })
        elif kind == "unit":
            meta = unit_meta.get(ent_id, {})
            enriched.append({
                "kind": kind, "id": ent_id,
                "href": f"/unit/{ent_id}",
                "symbol": meta.get("symbol") or "",
                "name": display_name or (localise(meta["name"], locale) if meta.get("name") else ent_id),
                "relation": _("detail.unit"),
            })
        elif kind == "constant":
            meta = constant_meta.get(ent_id, {})
            enriched.append({
                "kind": kind, "id": ent_id,
                "href": f"/constant/{ent_id}",
                "symbol": meta.get("symbol") or "",
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
        {"id": s[1], "kind": s[0], "heading": s[2] or s[1]} for s in suggestions
    ]}




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

    raw_quantities = [quantity for quantity in fetch_all_quantities(conn)]
    topic_filter = _filtered_ids_for_query(tree, fs.ids)
    dim_qty_ids = set(dimension_quantity_ids().values()) if fs.base_quantity_only else None
    system = g.unit_system
    filtered = []
    for quantity in raw_quantities:
        quantity = dict(quantity)
        _attach_breadcrumbs(quantity, locale)

        if not _passes_topic_difficulty(quantity, topic_filter, fs):
            continue
        if fs.has_dimension_filter and not dimension_matches(quantity, fs.dimension_filter, fs.dim_mode):
            continue
        if fs.quantity_ids and quantity["id"] not in fs.quantity_ids:
            continue
        if dim_qty_ids is not None and quantity["id"] not in dim_qty_ids:
            continue

        cu = select_base_unit_with_fallback(conn, quantity["id"], system)
        quantity["default_unit_html"], quantity["default_unit_symbol_latex"] = render_compound_unit(cu, locale)
        filtered.append(quantity)

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

    formulas = [dict(formula) for formula in fetch_all_formulas(conn)]
    topic_filter = _filtered_ids_for_query(tree, fs.ids)
    formulas = [formula for formula in formulas if _passes_topic_difficulty(formula, topic_filter, fs)]

    if fs.has_dimension_filter:
        formula_ids = {formula["id"] for formula in formulas}
        dim_map = compute_all_formula_dimensions(conn, formula_ids)
        formulas = [
            formula for formula in formulas
            if dimension_matches(dim_map.get(formula["id"], {}), fs.dimension_filter, fs.dim_mode)
        ]

    if fs.quantity_ids:
        quantity_match = (
            fetch_formulas_with_any_quantity
            if fs.quantity_mode == "or"
            else fetch_formulas_with_all_quantities
        )
        matching_ids = quantity_match(conn, fs.quantity_ids)
        if matching_ids is not None:
            formulas = [formula for formula in formulas if formula["id"] in matching_ids]

    formulas = sort_formulas(conn, formulas, sort_key, locale)

    for formula in formulas:
        _attach_breadcrumbs(formula, locale)
        formula["latex"] = render_formula_latex(conn, formula["id"], locale=locale)

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

    return _respond(export_to_csv_zip(conn), "application/zip", "scifind_csv.zip")



CREATE_EQUATION_MAX_LENGTH = 2000

@app.route("/create")
def create_formula():
    return render_template("create.html")




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




if __name__ == "__main__":
    host = os.environ.get("SCIFIND_HOST", "127.0.0.1")
    port = int(os.environ.get("SCIFIND_PORT", "5000"))
    debug = os.environ.get("SCIFIND_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
