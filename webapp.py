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
    fetch_formulas_with_quantities,
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
)
from scifind_lib.units import (
    compound_unit_by_slug,
    parse_compound_unit,
    select_base_unit_with_fallback,
    unit_by_id,
)
from scifind_lib.operators import operand_info, render_template as render_op_template

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
    tree = load_tree(get_db())
    name_map = topic_name_map(tree, locale)
    topic = row.get("topic_id")
    topic_path_ids = topic_path(tree, topic)
    if topic_path_ids:
        row["breadcrumbs"] = [{"id": n, "name": name_map.get(n, n)} for n in topic_path_ids]
    else:
        row["breadcrumbs"] = []
    return row


def _passes_topic_difficulty(item, topic_filter, fs):
    """Shared topic + difficulty gate for the quantities/formulas list pages."""
    if topic_filter and item.get("topic_id") not in topic_filter:
        return False
    diff = item.get("difficulty")
    return diff is None or fs.diff_min <= diff <= fs.diff_max


def _list_base(request_args, allowed_sorts, default_sort):
    """Shared setup for /formulas and /quantities: db, filter state, tree, sort."""
    conn = get_db()
    fs = parse_filter_state(request_args, conn)
    tree = load_tree(conn)
    compressed = compress_selection(tree, fs.ids)
    raw_sort = request_args.get("sort")
    sort_key = raw_sort if raw_sort in allowed_sorts else default_sort
    topic_filter = expand_selection(tree, [i for i in fs.ids if i in all_tree_ids(tree)])
    return conn, fs, tree, compressed, sort_key, topic_filter


_LATEX_TEXTCMD_RE = re.compile(r"\\(?:mathrm|text)\{([^}]*)\}")


def _strip_textcmd(latex):
    return _LATEX_TEXTCMD_RE.sub(r"\1", latex)


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
    gen_map = {}
    def visit(node):
        genitive = (node.get("translations") or {}).get("cs-cz-gen")
        if genitive:
            gen_map[node["id"]] = genitive
    walk_tree(tree, visit)
    return gen_map


def _render_list_heading(view_label, tree, compressed, fs, conn, locale):
    names_by_id = fetch_quantities_by_ids(conn, fs.quantity_ids) if fs.quantity_ids else {}
    return _heading_from_compressed(
        view_label, compressed, tree, locale, fs, conn,
        active_quantity_names=[localise(names_by_id[qid], locale)
                               for qid in fs.quantity_ids if qid in names_by_id],
    )


def _op_symbols(conn):
    """{operator_id: symbol} for dimension filter ops, from the operator table."""
    return {r["id"]: (r["symbol"] or r["id"])
            for r in conn.execute("SELECT id, symbol FROM operator").fetchall()}


def _heading_from_compressed(view_label, compressed, tree, locale, fs, conn,
                             active_quantity_names=None):
    def _ui(key): return _ui_lookup(locale, key)
    parts = [view_label]
    name_map = topic_name_map(tree, locale)

    if compressed:
        order = topic_tree_order(conn)
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
        diff = str(fs.diff_min) if fs.diff_min == fs.diff_max else f"{fs.diff_min}\u2013{fs.diff_max}"
        clauses.append(f"{where} {diff}")

    caches = _get_dimension_caches()
    dim_mode = g.get("dim_mode", "dim")
    x_map = caches.get("var" if dim_mode == "unit" else dim_mode, {})
    y_map = caches.get("unit", {})
    op_symbols = _op_symbols(conn)
    dim_parts = []
    for symbol in dimension_symbols(conn):
        d = fs.dimension_filter.get(symbol, {})
        if d.get("val") is None:
            continue
        op = op_symbols.get(d.get("op", "eq"), d.get("op", "eq"))
        dv = str(d["val"]).translate(SUPERSCRIPT_DIGITS)
        dim_parts.append(f"{_strip_textcmd(x_map.get(symbol, symbol))} {op} {_strip_textcmd(y_map.get(symbol, symbol))}{dv}")
    if dim_parts:
        d_conj = "heading.or" if fs.dim_mode == "or" else "heading.and"
        clauses.append(f"{_ui('heading.where_dimensions_are')} {_join_names(dim_parts, locale, d_conj)}")

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
    if request.method in ("POST", "PUT", "PATCH", "DELETE") \
            and request.endpoint not in (None, "static"):
        sent = request.headers.get(_CSRF_HEADER) or request.form.get(_CSRF_FORM_FIELD) or ""
        expected = session.get(_CSRF_SESSION_KEY) or ""
        if not expected or not sent or not secrets.compare_digest(sent, expected):
            return ("CSRF token missing or invalid", 400)
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
    locales = _available_locales()
    locale = request.args.get("locale") or request.cookies.get("sf_locale")
    if locale in locales:
        session["locale"] = locale
    g.locale = session["locale"] if session.get("locale") in locales \
        else _resolve_locale(request.headers.get("Accept-Language", ""))

    for arg_key, cookie_key, allowed, default in (
        ("dim_mode", "sf_dim_mode", ("dim", "var", "unit"), "dim"),
        ("unit_system", "sf_unit_system", ("SI", "CGS", "Imperial"), "SI"),
    ):
        value = request.args.get(arg_key) or request.cookies.get(cookie_key)
        if value in allowed:
            session[arg_key] = value
        setattr(g, arg_key, session.get(arg_key, default))

    meta = load_locale_config(g.locale)
    fallback = load_locale_config(DEFAULT_LOCALE)
    g.locale_seo_description = meta.get("seoDescription") or fallback.get("seoDescription", "")
    g.locale_seo_keywords = meta.get("seoKeywords") or fallback.get("seoKeywords", "")


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
        has_table = database_has_formula_table(get_db())
    except sqlite3.DatabaseError as exc:
        logger.warning("Database open failed: %s", exc)
        has_table = False
    if not has_table:
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
    try:
        conn = get_db()
    except sqlite3.OperationalError as exc:
        logger.warning("Database unavailable: %s", exc)
        conn = None
    tree = load_tree(conn) if conn is not None else []
    if conn is not None:
        from scifind_lib.conversion import UnitGraphError, validate_graph
        try:
            validate_graph(conn)
        except UnitGraphError as exc:
            logger.error("Unit graph integrity violated: %s", exc)
            raise RuntimeError(f"Unit reference graph broken: {exc}. Fix seed.sql before serving traffic.") from exc
    fs = parse_filter_state(request.args, conn)
    name_map = topic_name_map(tree, locale)
    compressed = compress_selection(tree, fs.ids)

    quantities_for_filter, dim_qty_names = [], {}
    caches = {"var": {}, "unit": {}, "dim": {}}
    if conn is not None:
        try:
            quantities_for_filter = [
                {"id": q["id"], "name": localise(q["name"], locale), "symbol": q["symbol"] or ""}
                for q in fetch_all_quantities(conn)
            ]
        except sqlite3.OperationalError as exc:
            logger.warning("Quantity table unavailable: %s", exc)
        caches = _get_dimension_caches()
        try:
            qty_ids = dimension_quantity_ids(conn)
            placeholders = ",".join("?" * len(qty_ids))
            qid_to_name = {q["id"]: localise(q["name"], locale) for q in conn.execute(
                f"SELECT id, name FROM quantity WHERE id IN ({placeholders})",
                tuple(qty_ids.values())).fetchall()}
            dim_qty_names = {sym: qid_to_name.get(qid, "") for sym, qid in qty_ids.items()}
        except sqlite3.OperationalError as exc:
            logger.warning("Base dimension names unavailable: %s", exc)

    dim_mode = g.get("dim_mode", "dim")
    sort_context = _sort_context_for(request.path, request.args.get("sort"))

    return dict(
        tree_json=_topic_tree_data(tree, name_map, compressed, fs.exclude_all, ids_provided=fs.ids_provided),
        diff_min=fs.diff_min,
        diff_max=fs.diff_max,
        current_view="quantities" if request.path == "/quantities"
            or request.path.startswith(("/quantity/", "/unit/")) else "formulas",
        dim_filter=fs.dimension_filter,
        dim_mode=fs.dim_mode,
        qty_mode=fs.quantity_mode,
        all_quantities_for_filter=quantities_for_filter,
        dim_symbols=caches.get(dim_mode, caches.get("dim", {})),
        dim_qty_names=dim_qty_names,
        dimension_symbol_list=dimension_symbols(conn) if conn else [],
        available_locales=[{"code": code, "name": data.get("meta", {}).get("name", code)}
                           for code, data in _available_locales().items()],
        locale_ui=_build_ui_with_fallback(locale),
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
        "sort": raw_value if raw_value in allowed else default,
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
    base = _resolve_base_unit(conn, constant.get("unit_id"),
                              constant.get("compound_unit_id"),
                              fallback_qid=rq_id)
    default_unit_html, default_unit_symbol = (
        render_compound_unit(base, locale) if base else (Markup(""), "")
    )

    graph = UnitGraph(conn, rq_id)
    if base and base["kind"] == "compound_unit":
        base_unit_ids = {uid for uid, _ in parse_compound_unit(base["unit"])}
    elif base:
        base_unit_ids = {base["id"]}
    else:
        base_unit_ids = set()

    units_rows = []
    if base:
        units_rows.append({
            "symbol_latex": default_unit_symbol,
            "name_html": default_unit_html,
            "system": base["system"],
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


def _detail_row(symbol_latex, name_html, paren_html, base, locale):
    unit_html, unit_sym = render_compound_unit(base, locale)
    return {
        "symbol_latex": symbol_latex,
        "name_html": Markup(name_html) if name_html else "",
        "paren_html": Markup(paren_html) if paren_html else "",
        "default_unit_html": unit_html,
        "default_unit_symbol_latex": unit_sym,
    }


def _constant_detail_item(conn, item, locale):
    cid = item.get("constant_id")
    if not cid:
        return None
    name = item.get("constant_name") or cid.replace("_", " ").title()
    name_html = build_entity_link("constant", cid, name)
    rq_id = item.get("related_quantity_id")
    rq_name = item.get("related_quantity_name")
    rq_symbol = (item.get("related_quantity_symbol") or "").strip()
    paren_html = ""
    if rq_name:
        sym = f"${rq_symbol}$ " if rq_symbol else ""
        paren_html = f"({sym}{build_entity_link('quantity', rq_id, rq_name)})"

    base = _resolve_base_unit(conn, item.get("constant_unit_id"),
                              item.get("constant_compound_unit_id"),
                              fallback_qid=rq_id)
    return _detail_row(item.get("constant_symbol") or "", name_html,
                       paren_html, base, locale)


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
            marker_ids = {
                m.group(1).strip().split("|", 1)[0].strip().lower().replace(" ", "_")
                for m in re.finditer(r"\[\s*([^\]]+)\]", no_raw)
            }
            marker_ids = {mid for mid in marker_ids if is_slug(mid)}
            if qid in marker_ids:
                name_html = expand_quantity_markers(no_raw)
            else:
                name_html = html_module.escape(no_raw)
                if has_overwrite and orig_symbol:
                    paren_parts.append(qlink)
        else:
            name_html = qlink

        paren_html = f"({' '.join(paren_parts)})" if paren_parts else ""
        result.append(_detail_row(
            render_variable_symbol(item, locale), name_html, paren_html,
            select_base_unit_with_fallback(conn, qid, g.unit_system), locale,
        ))

    return result


def _detail_or_404(fetch_fn, entity_id, label):
    """Fetch one row as a dict or return a (body, 404) tuple."""
    row = fetch_fn(get_db(), entity_id)
    if not row:
        return None, (f"{label} not found", 404)
    row = dict(row)
    _attach_breadcrumbs(row, g.locale)
    return row, None


def _parse_links(raw):
    try:
        links = json.loads(raw) if raw else []
    except (ValueError, TypeError):
        return []
    return links if isinstance(links, list) else []


def _dim_latex(conn, dimensions):
    caches = _get_dimension_caches()
    return format_dimensions_latex(
        *dimensions,
        symbols=dimension_symbols(conn),
        variable_symbols=caches["var"],
        unit_symbols=caches["unit"],
        dim_symbols=caches["dim"],
        mode=g.get("dim_mode", "dim"),
    )


def _with_latex(conn, rows, locale, id_key="id"):
    """Attach rendered formula latex to each row dict (in place)."""
    out = []
    for r in rows:
        r = dict(r)
        r["latex"] = render_formula_latex(conn, r[id_key], locale=locale) or ""
        out.append(r)
    return out


def _resolve_base_unit(conn, unit_id=None, compound_id=None, fallback_qid=None):
    base = None
    if unit_id:
        base = unit_by_id(conn, unit_id)
    elif compound_id:
        base = compound_unit_by_slug(conn, compound_id)
    if base is None and fallback_qid:
        base = select_base_unit_with_fallback(conn, fallback_qid, g.unit_system)
    return base


def _units_ctx(conn, quantity_id, ref_unit_id=None):
    t = quantity_units_table(conn, quantity_id, g.unit_system,
                             ref_unit_id=ref_unit_id, tr=_)
    return {"units": t["units"], "table_data": t["payload"],
            "si_prefixes": t["si_prefixes"],
            "si_prefix_sections": t["si_prefix_sections"]}


@app.route("/formula/<formula_id>")
def formula_detail(formula_id):
    conn = get_db()
    locale = g.locale
    row, err = _detail_or_404(fetch_formula, formula_id, "Formula")
    if err:
        return err
    formula_sql, token_sql = build_formula_insert_sql(conn, formula_id)
    return render_template(
        "formula.html",
        formula=row, latex=render_formula_latex(conn, formula_id, locale=locale),
        relations=_with_latex(conn, fetch_formula_relations(conn, formula_id),
                              locale, id_key="related_id"),
        detail_items=_build_formula_detail_items(conn, formula_id, locale),
        dim_latex=_dim_latex(conn, compute_formula_dimensions(conn, formula_id)),
        links=_parse_links(row.get("links")),
        formula_sql=formula_sql, token_sql=token_sql,
    )


@app.route("/quantity/<quantity_id>")
def quantity_detail(quantity_id):
    conn = get_db()
    locale = g.locale
    quantity, err = _detail_or_404(fetch_quantity, quantity_id, "Quantity")
    if err:
        return err
    primary, non_primary = fetch_quantity_formulas_by_side(conn, quantity_id)
    constants = []
    for const in fetch_quantity_constants(conn, quantity_id):
        const = dict(const)
        const["value_latex"] = _format_constant_value(const["value"])
        base = _resolve_base_unit(conn, const.get("unit_id"),
                                  const.get("compound_unit_id"))
        _html, const["unit_symbol_latex"] = render_compound_unit(base, g.locale) if base else (Markup(""), "")
        constants.append(const)
    return render_template(
        "quantity.html",
        q=quantity,
        primary_formulas=_with_latex(conn, primary, locale),
        nonprimary_formulas=_with_latex(conn, non_primary, locale),
        related_formulas=_with_latex(conn, fetch_quantity_related_formulas(conn, quantity_id), locale),
        constants=constants,
        dim_latex=_dim_latex(conn, dimensions_from_row(quantity, conn)),
        **_units_ctx(conn, quantity_id),
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

    base = _resolve_base_unit(conn, constant.get("unit_id"),
                              constant.get("compound_unit_id"))
    compound_unit_json = (base["unit"]
                          if base and base["kind"] == "compound_unit" else None)
    display = _constant_value_display(constant["value"]) if constant.get("value") is not None else None
    _, unit_symbol_latex = render_compound_unit(base, g.locale)

    return render_template(
        "constant.html",
        constant=constant,
        links=_parse_links(constant.get("links")),
        formulas=_with_latex(conn, fetch_constant_formulas(conn, constant_id), locale),
        dim_latex=_dim_latex(conn, compute_compound_unit_dimensions(conn, compound_unit_json)),
        display=display,
        value_latex=_constant_value_latex(display) if display else "",
        unit_symbol_latex=unit_symbol_latex,
        units=_constant_units_table(conn, constant, g.unit_system),
    )


@app.route("/unit/<unit_id>")
def unit_detail(unit_id):
    conn = get_db()
    unit, err = _detail_or_404(fetch_unit, unit_id, "Unit")
    if err:
        return err
    locale = g.locale
    qty = fetch_quantity(conn, unit["quantity_id"])
    unit["quantity_name_localized"] = localise(qty["name"], locale) if qty else unit.get("quantity_id", "")
    ctx = _units_ctx(conn, unit["quantity_id"], ref_unit_id=unit_id) if qty \
        else {"units": None, "table_data": None, "si_prefixes": None, "si_prefix_sections": None}
    return render_template("unit.html", unit=unit, fixed_ref=True, **ctx)



@app.route("/")
def index():
    return redirect("/formulas")


@app.route("/base-units")
def base_units_page():
    return redirect("/quantities?is_dim=1")


def _empty_list_response(template, items_key, empty_key, sort_key, sorts):
    return render_template(template, **{items_key: [], "heading": _(empty_key),
                                        "sort": sort_key, "available_sorts": sorts})


@app.route("/search")
def search_page():
    query = request.args.get("q", "").strip()[:SEARCH_QUERY_MAX_LENGTH]
    conn = get_db()
    locale = g.locale
    raw_sort = request.args.get("sort")
    sort_key = raw_sort if raw_sort in SEARCH_SORT_KEYS else DEFAULT_SEARCH_SORT
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
    meta = {kind: meta_by_kind.get(kind, {}) for kind in ("formula", "quantity", "unit", "constant")}
    detail_keys = {"formula": "detail.formula", "quantity": "detail.quantity",
                   "unit": "detail.unit", "constant": "detail.constant"}

    enriched = []
    for kind, ent_id, display_name in hits:
        if kind not in meta:
            continue
        item_meta = meta[kind].get(ent_id, {})
        item = {"kind": kind, "id": ent_id, "href": f"/{kind}/{ent_id}",
                "relation": _(detail_keys[kind])}
        if kind == "formula":
            item["latex"] = render_formula_latex(conn, ent_id, locale)
            item["name"] = display_name or item_meta.get("name_en") or ent_id
        else:
            item["symbol"] = item_meta.get("symbol") or ""
            if kind == "unit" and not display_name and item_meta.get("name"):
                item["name"] = localise(item_meta["name"], locale)
            else:
                item["name"] = display_name or ent_id
        enriched.append(item)
    return enriched


@app.route("/api/search-suggestions")
def search_suggestions():
    query = request.args.get("q", "").strip()[:SUGGEST_QUERY_MAX_LENGTH]
    locale = getattr(g, "locale", DEFAULT_LOCALE)
    suggestions = search_entities(get_db(), query, limit=8, locale=locale)
    return {"suggestions": [
        {"id": s[1], "kind": s[0], "heading": s[2] or s[1]} for s in suggestions
    ]}




@app.route("/quantities")
def all_quantities():
    conn, fs, tree, compressed, sort_key, topic_filter = _list_base(
        request.args, QUANTITY_SORT_KEYS, DEFAULT_QUANTITY_SORT)
    fs.quantity_mode = "or"
    locale = g.locale
    if compressed == {r["id"] for r in tree}:
        return redirect("/quantities")

    if fs.exclude_all or (fs.ids_provided and not fs.ids):
        return _empty_list_response("quantities.html", "quantities",
                                    "detail.quantities_no_results", sort_key, QUANTITY_SORT_KEYS)

    dim_qty_ids = set(dimension_quantity_ids(conn).values()) if fs.base_quantity_only else None
    system = g.unit_system
    filtered = []
    for row in fetch_all_quantities(conn):
        quantity = dict(row)
        _attach_breadcrumbs(quantity, locale)

        if not _passes_topic_difficulty(quantity, topic_filter, fs):
            continue
        if fs.has_dimension_filter and not dimension_matches(quantity, fs.dimension_filter, fs.dim_mode, conn):
            continue
        if fs.quantity_ids and quantity["id"] not in fs.quantity_ids:
            continue
        if dim_qty_ids is not None and quantity["id"] not in dim_qty_ids:
            continue

        cu = select_base_unit_with_fallback(conn, quantity["id"], system)
        quantity["default_unit_html"], quantity["default_unit_symbol_latex"] = render_compound_unit(cu, locale)
        filtered.append(quantity)

    filtered = sort_quantities(conn, filtered, sort_key, locale)

    heading = _("detail.base_quantities") if fs.base_quantity_only else _render_list_heading(
        _("detail.quantities"), tree, compressed, fs, conn, locale,
    )
    return render_template(
        "quantities.html",
        quantities=filtered,
        heading=heading,
        sort=sort_key,
        available_sorts=QUANTITY_SORT_KEYS,
    )


@app.route("/formulas")
def all_formulas():
    conn, fs, tree, compressed, sort_key, topic_filter = _list_base(
        request.args, FORMULA_SORT_KEYS, DEFAULT_FORMULA_SORT)
    locale = g.locale
    if compressed == {r["id"] for r in tree}:
        return redirect("/formulas")

    if fs.exclude_all or (fs.ids_provided and not fs.ids):
        return _empty_list_response("formulas.html", "formulas",
                                    "detail.formulas_no_results", sort_key, FORMULA_SORT_KEYS)

    formulas = [dict(formula) for formula in fetch_all_formulas(conn)]
    formulas = [formula for formula in formulas if _passes_topic_difficulty(formula, topic_filter, fs)]

    if fs.has_dimension_filter:
        formula_ids = {formula["id"] for formula in formulas}
        dim_map = compute_all_formula_dimensions(conn, formula_ids)
        formulas = [
            formula for formula in formulas
            if dimension_matches(dim_map.get(formula["id"], {}), fs.dimension_filter, fs.dim_mode, conn)
        ]

    if fs.quantity_ids:
        matching_ids = fetch_formulas_with_quantities(conn, fs.quantity_ids, fs.quantity_mode)
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

    if fmt == "sql":
        data, mimetype, filename = (export_to_sql(conn).encode("utf-8"),
                                    "application/sql", "scifind.sql")
    elif fmt in ("xlsx", "ods"):
        export_fn, mimetype, filename = {
            "xlsx": (export_to_xlsx,
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     "scifind.xlsx"),
            "ods": (export_to_ods,
                    "application/vnd.oasis.opendocument.spreadsheet",
                    "scifind.ods"),
        }[fmt]
        buffer = io.BytesIO()
        export_fn(conn, buffer)
        data = buffer.getvalue()
    else:
        data, mimetype, filename = (export_to_csv_zip(conn),
                                    "application/zip", "scifind_csv.zip")

    resp = Response(data, mimetype=mimetype,
                    headers={"Content-Disposition": f"attachment; filename={filename}"})
    resp.set_cookie("sf_export_format", fmt, max_age=365 * 24 * 3600, path="/")
    return resp



@app.route("/create")
def create_formula():
    return render_template("create.html")




def _parse_bracket(prefix, nparts, fields=None):
    """Parse `prefix[a][b]...` form keys; blanks omitted, last non-blank wins."""
    out, pre = {}, prefix + "["
    for key, values in request.form.lists():
        if not key.startswith(pre) or not key.endswith("]"):
            continue
        parts = key[len(pre):-1].split("][")
        if len(parts) != nparts or (fields and parts[-1] not in fields):
            continue
        value = next((v for v in reversed(values) if v and v.strip()), "")
        if not value:
            continue
        node = out
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value.strip()
    return out


def _check_equation():
    """Return (equation, error) enforcing CREATE_EQUATION_MAX_LENGTH."""
    equation = request.form.get("equation") or ""
    if len(equation) > CREATE_EQUATION_MAX_LENGTH:
        return None, f"equation exceeds {CREATE_EQUATION_MAX_LENGTH} characters"
    return equation, None


@app.route("/create/preview-render", methods=["POST"])
def create_preview_render():
    """Form-POST version of /api/preview that also returns detail_items HTML."""
    equation, error = _check_equation()
    if error:
        return {"error": error}, 400
    conn = get_db()
    result = parse_and_preview_equation(
        conn, equation.strip(), locale=g.locale, dim_caches=_get_dimension_caches(),
        overrides=_parse_bracket("override", 2, ("symbol", "name")),
        dim_mode=g.get("dim_mode", "dim"))
    if result.get("error") or not result.get("latex"):
        return result
    result["detail_items"] = _build_formula_detail_items(
        conn, None, g.locale, tokens=result["tokens"])
    return result


def _operator_latex(item):
    """LaTeX for an operator in the token sidebar via its own template."""
    try:
        arity = int(item.get("arity") or 2)
    except (TypeError, ValueError):
        arity = 2
    operands = ["x", "y", "z", "w"][:max(arity, 1)]
    try:
        return render_op_template(
            item.get("latex_template") or "[[0]] [[1]]", operands,
            [operand_info("operator")] * len(operands), item.get("id"))
    except ValueError:
        return item.get("symbol") or item["id"]


def _render_token_item(item, kind, locale):
    """One <div class="qty-result"> for the token sidebar."""
    esc = html_module.escape
    item = dict(item)
    if kind == "op":
        sym_text, name = _operator_latex(item), item["id"]
        insert = item.get("symbol") or item["id"]
        search = f'{item["id"]} {item.get("symbol") or ""}'
    else:
        sym_text = item.get("symbol") or ""
        name = localise(item.get("name") or "", locale, default="en-us") or item["id"]
        insert = item["id"]
        search = f'{item["id"]} {item.get("symbol") or ""} {item.get("name") or ""}'
    sym_html = f'<span class="qty-result-sym">${esc(sym_text)}$</span>' if sym_text else '<span class="qty-result-sym"></span>'
    return (f'<div class="qty-result" data-kind="{kind}" data-insert="{esc(insert)}"'
            f' data-search="{esc(search.lower())}">{sym_html}'
            f'<span class="qty-result-name">{esc(name)}</span></div>')


def _render_token_section(label, target_id, items, kind, locale, no_match_label):
    """One labelled <section> of token items with a collapse toggle."""
    esc = html_module.escape
    body = "".join(_render_token_item(it, kind, locale) for it in items)
    return (f'<div class="section-label-row"><div class="section-label">{esc(label)}</div>'
            f'<div class="filter-buttons"><button class="filter-btn" data-action="toggle-token-section"'
            f' data-target="{target_id}" type="button"><span class="token-section-icon">'
            f'<i data-lucide="chevron-up" width="16" height="16"></i></span></button></div></div>'
            f'<div class="token-list" id="{target_id}">{body}</div>'
            f'<div class="token-empty">{esc(no_match_label)}</div>')


@app.route("/create/token-sidebar")
def create_token_sidebar():
    """Server-rendered Q/C/O token sidebar for the /create page."""
    conn, locale = get_db(), g.locale
    no_results = _("create.no_results")
    sections = "".join(_render_token_section(label, tid, fetch(conn), kind, locale, no_results)
                       for label, tid, fetch, kind in (
                           (_("detail.quantities"), "token-qty", fetch_all_quantities, "qty"),
                           (_("nav.constants"), "token-const", fetch_all_constants, "const"),
                           (_("nav.operators"), "token-op", fetch_all_operators, "op")))
    return Markup(
        '<div class="filter-qty-search-wrap">'
        f'<input type="text" class="text-field" id="token-search" placeholder="{html_module.escape(_("create.search_placeholder"))}" autocomplete="off">'
        '</div>'
        f'<div class="token-sidebar">{sections}</div>'
    )


def _render_breadcrumb(selected_id, tree, name_map):
    """Server-rendered topic breadcrumb (root > ... > selected > child trigger)."""
    esc = html_module.escape
    node = _find_node(tree, selected_id) if selected_id else None
    kids, path = (node.get("children") or [], topic_path(tree, selected_id) or [selected_id]) \
        if node is not None else (tree, None)
    parts = [' &gt; '.join(
        f'<span class="topic-current" data-id="{esc(tid)}">{esc(name_map.get(tid, tid))}</span>'
        for tid in path)] if path else []
    if kids:
        if parts:
            parts.append(' &gt; ')
        label = _("create.topic")
        menu = "".join(_render_menu_item(kid, name_map) for kid in kids)
        parts.append(
            f'<span class="topic-current has-menu" data-text="{esc(label)}">'
            f'<button class="topic-dropdown-trigger" type="button">{esc(label)}</button>'
            f'<div class="topic-children-menu">{menu}</div></span>')
    return Markup("".join(parts))


def _find_node(tree, node_id):
    stack = list(tree)
    while stack:
        node = stack.pop()
        if node["id"] == node_id:
            return node
        stack.extend(node.get("children") or [])
    return None


def _render_menu_item(node, name_map):
    """One entry of the topic dropdown; `node` is a topic-tree node dict."""
    esc = html_module.escape
    node_id, name = node["id"], name_map.get(node["id"], node["id"])
    if kids := node.get("children"):
        sub = "".join(_render_menu_item(c, name_map) for c in kids)
        return (f'<div class="topic-menu-item" data-id="{esc(node_id)}">'
                f'<span>{esc(name)}</span><span class="caret"></span>'
                f'<div class="topic-submenu">{sub}</div></div>')
    return (f'<button type="button" class="topic-menu-item" data-id="{esc(node_id)}">'
            f'<span>{esc(name)}</span></button>')


@app.route("/create/breadcrumb")
def create_breadcrumb():
    topic = (request.args.get("topic") or "").strip() or None
    tree = load_tree(get_db())
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


def _build_create_sql_payload(conn, form):
    """Parse the /create form fields and return (formula_sql, token_sql)."""
    get = lambda n: (form.get(n) or "").strip()
    links = [line.strip() for line in get("links").splitlines() if line.strip()] or None
    tr_top = _parse_bracket("tr", 2)
    tr_ov = _parse_bracket("tr_overrides", 3, ("symbol", "name"))
    translations = {}
    for loc in set(tr_top) | set(tr_ov):
        entry = {k: tr_top[loc][k] for k in ("name", "description") if k in tr_top.get(loc, {})}
        if loc in tr_ov:
            entry["overrides"] = tr_ov[loc]
        if entry:
            translations[loc] = entry
    return build_create_sql(
        conn, name_en=get("name_en"), topic=get("topic"),
        difficulty=get("difficulty") or "2", equation=form.get("equation") or "",
        overrides=_parse_bracket("override", 2, ("symbol", "name")),
        description=get("description") or None, links=links,
        translations=translations, formula_id=get("formula_id"))


def _sql_block(pre_id, sql, action):
    esc = html_module.escape
    return (f'<div class="sql-block"><button class="formula-copy-btn" type="button"'
            f' data-action="{action}" title="Copy"><i data-lucide="copy" width="16" height="16"></i></button>'
            f'<pre id="{pre_id}">{esc(sql)}</pre></div>')


def _render_sql_modal_html(formula_sql, token_sql):
    return Markup(
        _sql_block("formula-sql", formula_sql, "copy-formula-sql")
        + f'<h3>{html_module.escape(_("create.token_inserts"))}</h3>'
        + _sql_block("token-sql", token_sql, "copy-token-sql"))


def _sql_error(message, code=None):
    esc, err = html_module.escape(str(message)), html_module.escape(code or str(message))
    return Markup(f'<p class="detail-desc" data-error="{err}">{esc}</p>'), 400


@app.route("/create/build-sql", methods=["POST"])
def create_build_sql():
    """Form-POST equivalent of /api/build-sql returning rendered modal HTML."""
    _, error = _check_equation()
    if error:
        return _sql_error(error, "equation-too-long")
    try:
        formula_sql, token_sql = _build_create_sql_payload(get_db(), request.form)
    except ValueError as e:
        return _sql_error(e)
    return _render_sql_modal_html(formula_sql, token_sql)




if __name__ == "__main__":
    host = os.environ.get("SCIFIND_HOST", "127.0.0.1")
    port = int(os.environ.get("SCIFIND_PORT", "5000"))
    debug = os.environ.get("SCIFIND_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
