#!/usr/bin/env python3
"""Scifind web app — Flask interface to the formula database."""

import gzip
import html as html_module
import json
import logging
import os
import re
import secrets
import sqlite3
import sys
import time

from collections import deque
from pathlib import Path
from urllib.parse import urlencode
from flask import Flask, render_template, request, g, Response, redirect, session, url_for
from markupsafe import Markup
from pylatexenc.latex2text import LatexNodes2Text

_PROJECT_DIR = Path(__file__).resolve().parent
_LOCALE_DIR = _PROJECT_DIR / "locales"
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from scifind_lib.db import (
    database_connection,
    database_has_formula_table,
    database_path,
    initialize_database,
    open_database,
)
from scifind_lib.formula import (
    build_dimension_symbol_triplet,
    dimension_quantity_ids,
    dimension_symbols,
    format_dimensions_latex,
    render_formulas_latex_batched,
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
    QuantityFilter,
    SEARCH_SORT_KEYS,
    fetch_all_quantities,
    fetch_formulas_filtered,
    fetch_quantities_by_ids,
    fetch_quantities_filtered,
    normalize_sort,
    parse_filter_state,
)
from scifind_lib.tree import (
    build_tree_indices,
    compress_selection,
    expand_selection,
    load_tree,
    topic_name_map,
    topic_path,
    topic_tree_order,
    walk_tree,
)
from scifind_lib.constants import SUPERSCRIPT_DIGITS
from scifind_lib.conversion import UnitGraph, convert_value, validate_graph
from scifind_lib.formula import (
    compute_all_formula_dimensions,
    compute_formula_dimensions,
    constant_dimensions,
    dimension_columns,
    dimension_matches,
    dimensions_from_row,
    parse_and_preview_equation,
    render_formula_latex,
)
from scifind_lib.display import (
    expand_quantity_markers,
    marker_ids_in,
    quantity_units_table,
    render_compound_unit,
    render_variable_symbol,
    unit_name_link,
    units_column,
)
from scifind_lib.util import entity_link, format_sci_parts, parse_int_or, render_sci_latex, request_cached, safe_json_list
from scifind_lib.export import (
    build_create_sql,
    build_formula_insert_sql,
    export_payload,
)
from scifind_lib.fetch import (
    fetch_all_constants,
    fetch_all_formulas,
    fetch_all_operators,
    fetch_constant,
    fetch_constant_formulas,
    fetch_detail_items,
    fetch_formula,
    fetch_formula_relations,
    fetch_formula_token_quantities,
    fetch_formulas_with_quantities,
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
    parse_compound_unit,
    resolve_base_unit,
    resolve_constant_base,
    select_base_units_batched,
)
from scifind_lib.operators import operand_info, render_template as render_op_template
from scifind_lib.parser import check_equation_length, parse_bracket_keys

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
        return Response(_err("error.not_found"), status=404)


def _secret_key():
    if env_key := os.environ.get("SCIFIND_SECRET_KEY"):
        return env_key
    key_file = Path(app.instance_path) / "secret_key"
    for _ in range(2):
        try:
            if stored := key_file.read_text(encoding="utf-8").strip():
                return stored
        except FileNotFoundError:
            pass
        except OSError:
            break
        try:
            key_file.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError:
            continue  # FileExistsError → re-read; other errors → retry then fallback
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
        try:
            return key_file.read_text(encoding="utf-8").strip()
        except OSError:
            break
    return secrets.token_hex(24)


app.secret_key = _secret_key()
app.config.update(
    MAX_CONTENT_LENGTH=max(1, parse_int_or(os.environ.get("SCIFIND_MAX_UPLOAD_MB", "1"), 1)) * 1024 * 1024,
    SEND_FILE_MAX_AGE_DEFAULT=365 * 86400,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SCIFIND_COOKIE_SECURE", "").lower() in ("1", "true", "yes"),
)


_GZIP_TYPES = ('text/', 'application/json', 'application/javascript')


def _accepts_gzip(header_value):
    for part in header_value.split(","):
        token, _, params = part.partition(";")
        if token.strip().lower() != "gzip":
            continue
        q = params.strip().lower()
        if not q.startswith("q="):
            return True
        try:
            return float(q[2:]) > 0
        except ValueError:
            return True
    return False


@app.after_request
def gzip_response(response):
    response.vary.add("Accept-Encoding")
    if not _accepts_gzip(request.headers.get("Accept-Encoding", "")):
        return response
    if not (response.content_type or "").startswith(_GZIP_TYPES):
        return response
    if response.direct_passthrough or response.is_streamed:
        return response
    original = response.get_data()
    if len(original) < 200:
        return response
    compressed = gzip.compress(original)
    response.set_data(compressed)
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = len(compressed)
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


def _attach_breadcrumbs_batched(rows, locale, tree, name_map=None, parent_map=None):
    """Attach breadcrumbs to many rows with one tree + name-map load (no N+1)."""
    name_map = name_map if name_map is not None else topic_name_map(tree, locale)
    parent_map = parent_map if parent_map is not None else build_tree_indices(tree)["parent"]
    for row in rows:
        ids = topic_path(tree, row.get("topic_id"), _parent_map=parent_map)
        row["breadcrumbs"] = [{"id": n, "name": name_map.get(n, n)} for n in ids] if ids else []
    return rows


def _passes_topic_difficulty(item, topic_filter, fs):
    """Shared topic + difficulty gate for the quantities/formulas list pages."""
    if topic_filter and item.get("topic_id") not in topic_filter:
        return False
    diff = item.get("difficulty")
    return diff is None or fs.diff_min <= diff <= fs.diff_max


def _cached(key, build): return request_cached(key, build)
def _cached_tree(conn): return _cached("_tree", lambda: load_tree(conn))
def _cached_indices(tree): return _cached("_tree_indices", lambda: build_tree_indices(tree))
def _cached_name_map(tree, locale):
    return _cached("_topic_name_map_" + str(locale), lambda: topic_name_map(tree, locale))


def _list_base(request_args, allowed_sorts, default_sort):
    """Shared setup for /formulas and /quantities: db, filter state, tree, sort."""
    conn = get_db()
    fs = parse_filter_state(request_args, conn)
    tree = _cached_tree(conn)
    # Single index build shared by compress + expand + breadcrumbs.
    indices = _cached_indices(tree)
    compressed = compress_selection(tree, fs.ids, _indices=indices)
    valid = set(indices["id_to_node"])
    sort_key = normalize_sort(request_args.get("sort"), allowed_sorts, default_sort)
    topic_filter = expand_selection(tree, [tid for tid in fs.ids if tid in valid], _indices=indices)
    return conn, fs, tree, compressed, sort_key, topic_filter


_LATEX_TEXTCMD_RE = re.compile(r"\\(?:mathrm|text)\{([^}]*)\}")


def _strip_textcmd(latex):
    return _LATEX_TEXTCMD_RE.sub(r"\1", latex)


def _latex_to_unicode(latex):
    """Unicode approximation of a LaTeX fragment for copy-to-clipboard."""
    if not isinstance(latex, str) or not latex.strip():
        return ""
    try:
        # Scifind stores raw math fragments; $...$ enables math rendering.
        return LatexNodes2Text().latex_to_text(f"${latex.strip()}$")
    except Exception as exc:
        logger.warning("latex_to_unicode failed for %r: %s", latex, exc)
        return latex


def _join_names(names, locale="en-us", conj_key="heading.and"):
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    conj = _ui_lookup(locale, conj_key)
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


def _operator_display_symbols(conn):
    """{operator_id: first alias} — first aliases entry is the display (unicode) symbol."""
    if getattr(g, "_operator_display_symbols", None) is not None:
        return g._operator_display_symbols
    try:
        rows = conn.execute("SELECT id, aliases FROM operator").fetchall()
    except sqlite3.OperationalError:
        return {}
    out = {}
    for r in rows:
        try:
            aliases = safe_json_list(r["aliases"])
        except (KeyError, TypeError, IndexError):
            aliases = []
        first = next((a for a in aliases if isinstance(a, str) and a), None)
        out[r["id"]] = first or r["id"]
    g._operator_display_symbols = out
    return out


def _heading_from_compressed(view_label, compressed, tree, locale, fs, conn):
    def _ui(key): return _ui_lookup(locale, key)
    parts = [view_label]
    name_map = _cached_name_map(tree, locale)

    if compressed:
        order = topic_tree_order(conn)
        gen_map = {}
        if locale == "cs-cz":
            walk_tree(tree, lambda n: gen_map.update(
                {n["id"]: g} if (g := (n.get("translations") or {}).get("cs-cz-gen")) else {}))
        seen, topic_names = set(), []
        for nid in sorted(compressed, key=lambda x: order.get(x, float("inf"))):
            display_name = gen_map.get(nid) or name_map.get(nid, nid)
            if display_name not in seen:
                topic_names.append(display_name)
                seen.add(display_name)
        if topic_names:
            joined = _join_names(topic_names, locale)
            parts.append(f"{_sibilant_prep(joined, _ui('heading.from'), locale)} {joined}")

    if fs.quantity_ids:
        names_by_id = fetch_quantities_by_ids(conn, fs.quantity_ids)
        active = [localise(names_by_id[qid], locale) for qid in fs.quantity_ids if qid in names_by_id]
        if active:
            q_label = _ui("heading.quantity" if len(active) == 1 else "heading.quantities")
            q_conj = "heading.or" if fs.quantity_mode == "or" else "heading.and"
            joined = _join_names(active, locale, q_conj)
            parts.append(f"{_sibilant_prep(joined, _ui('heading.with'), locale)} {q_label} {joined}")

    clauses = []
    if fs.diff_min > MIN_DIFFICULTY or fs.diff_max < MAX_DIFFICULTY:
        diff = str(fs.diff_min) if fs.diff_min == fs.diff_max else f"{fs.diff_min}\u2013{fs.diff_max}"
        clauses.append(f"{_ui('heading.where_difficulty_is')} {diff}")

    caches = _get_dimension_caches()
    dim_mode = g.get("dim_mode", "dim")
    x_map = caches.get("var" if dim_mode == "unit" else dim_mode, {})
    y_map = caches.get("unit", {})
    op_symbols = _operator_display_symbols(conn)
    dim_parts = []
    for symbol in dimension_symbols(conn):
        dim_entry = fs.dimension_filter.get(symbol, {})
        if dim_entry.get("val") is None:
            continue
        op = op_symbols.get(dim_entry.get("op", "eq"), dim_entry.get("op", "eq"))
        dv = str(dim_entry["val"]).translate(SUPERSCRIPT_DIGITS)
        dim_parts.append(f"{_strip_textcmd(x_map.get(symbol, symbol))} {op} {_strip_textcmd(y_map.get(symbol, symbol))}{dv}")
    if dim_parts:
        d_conj = "heading.or" if fs.dim_mode == "or" else "heading.and"
        clauses.append(f"{_ui('heading.where_dimensions_are')} {_join_names(dim_parts, locale, d_conj)}")

    if clauses:
        parts.append(f" {_ui('heading.and')} ".join(clauses))

    heading = " ".join(parts)
    return heading[0].upper() + heading[1:] if heading else f"{_ui('heading.all')} {view_label}"


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
    locales_data, lang_map = {}, {}
    if _LOCALE_DIR.is_dir():
        for path in sorted(_LOCALE_DIR.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    locale_data = json.load(f)
            except (OSError, ValueError):
                continue
            locales_data[path.stem] = locale_data
            lang_map[locale_data.get("meta", {}).get("acceptLanguage", path.stem)] = path.stem
    locales_data.setdefault(DEFAULT_LOCALE, DEFAULT_LOCALE_FALLBACK)
    lang_map.setdefault("en-US", DEFAULT_LOCALE)
    lang_map.setdefault("en", DEFAULT_LOCALE)
    _LOCALES = (locales_data, lang_map)
    for code, locale_data in locales_data.items():
        if code != DEFAULT_LOCALE and (empty := sorted(c for c, v in locale_data.get("ui", {}).items() if not v)):
            logger.warning("l10n: locale %r has empty ui categories: %s", code, empty)
    return _LOCALES


def _available_locales():
    return _load_locales()[0]


def _lang_to_locale():
    return _load_locales()[1]


_CSRF_KEY = "_csrf_token"
_CSRF_HEADER = "X-CSRF-Token"


def _ensure_csrf_token():
    if _CSRF_KEY not in session:
        session[_CSRF_KEY] = secrets.token_urlsafe(32)
    return session[_CSRF_KEY]


@app.before_request
def _csrf_protect():
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.endpoint not in (None, "static"):
        sent = request.headers.get(_CSRF_HEADER) or request.form.get(_CSRF_KEY) or ""
        expected = session.get(_CSRF_KEY) or ""
        if not (sent and expected and secrets.compare_digest(sent, expected)):
            return (_err("error.csrf"), 400)
    _ensure_csrf_token()


@app.context_processor
def _inject_csrf_token():
    return {"csrf_token": _ensure_csrf_token}


_RATE_LIMIT_BUCKETS: dict = {}
_RATE_LIMIT_MAX_BUCKETS = 10000


def _rate_limit(bucket, max_per_minute):
    """Sliding-window limiter."""
    try:
        max_n = int(max_per_minute)
    except (TypeError, ValueError):
        return None
    if max_n <= 0:
        return None
    now = time.monotonic()
    window = _RATE_LIMIT_BUCKETS.setdefault(bucket, deque())
    if len(_RATE_LIMIT_BUCKETS) > _RATE_LIMIT_MAX_BUCKETS:
        _RATE_LIMIT_BUCKETS.pop(next(iter(_RATE_LIMIT_BUCKETS)))
    while window and window[0] < now - 60.0:
        window.popleft()
    if len(window) >= max_n:
        return (f"{_err('error.rate_limit')}: {bucket}", 429)
    window.append(now)
    return None


def _locale_chain(start):
    locales = _available_locales()
    chain, seen = [], set()
    while start and start not in seen:
        seen.add(start)
        chain.append(start)
        start = locales.get(start, {}).get("meta", {}).get("fallback")
    return chain


def _resolve_locale(header):
    lang_map = _lang_to_locale()
    for part in (header or "").split(","):
        code = part.split(";")[0].strip()[:5]
        if hit := lang_map.get(code) or lang_map.get(code[:2]):
            return hit
    return DEFAULT_LOCALE


def _build_ui_with_fallback(locale):
    locales = _available_locales()
    merged = {}
    for code in reversed(_locale_chain(locale)):
        for cat, children in locales.get(code, {}).get("ui", {}).items():
            merged.setdefault(cat, {}).update(children)
    return merged


def _ui_lookup(locale, key):
    locales = _available_locales()
    cat, sep, child = key.partition(".")
    if not sep:
        return key
    chain = _locale_chain(locale)
    for code in chain:
        if (val := locales.get(code, {}).get("ui", {}).get(cat, {}).get(child)) is not None:
            return val
    intended = child in locales.get(DEFAULT_LOCALE, {}).get("ui", {}).get(cat, {})
    logger.warning(
        "l10n: %s %r (locale %s) — chain %s",
        "key fell back to en-us — translation missing in" if intended else "unknown key — not present in any locale file",
        key, locale, chain,
    )
    return key


@app.template_global()
def _(blob_or_key):
    """Resolve a DB i18n JSON blob or a UI-string key for the current locale."""
    locale = getattr(g, "locale", DEFAULT_LOCALE)
    if blob_or_key and blob_or_key.strip().startswith("{") and (result := localise(blob_or_key, locale)):
        return result
    return _ui_lookup(locale, blob_or_key)


app.template_global()(wrap_symbol_in_latex)


@app.template_global()
def static_v(filename):
    """Static URL with an mtime/size version for cache busting."""
    try:
        st = (Path(app.static_folder) / filename).stat()
        v = f"{int(st.st_mtime):x}{st.st_size:x}"
    except OSError:
        v = ""
    url = url_for("static", filename=filename)
    return f"{url}?v={v}" if v else url


@app.template_global()
def page_url(page):
    """Current path with all query args preserved and ``page`` overridden (no-JS fallback)."""
    args = request.args.to_dict() | {"page": page}
    return f"{request.path}?{qs}" if (qs := urlencode(args)) else request.path


@app.before_request
def detect_locale():
    locales = _available_locales()
    if (locale := request.args.get("locale") or request.cookies.get("sf_locale")) in locales:
        session["locale"] = locale
    g.locale = session["locale"] if session.get("locale") in locales else _resolve_locale(request.headers.get("Accept-Language", ""))

    for arg_key, cookie_key, allowed, default in (
        ("dim_mode", "sf_dim_mode", ("dim", "var", "unit"), "dim"),
        ("unit_system", "sf_unit_system", ("SI", "CGS", "Imperial"), "SI"),
    ):
        if (value := request.args.get(arg_key) or request.cookies.get(cookie_key)) in allowed:
            session[arg_key] = value
        setattr(g, arg_key, session.get(arg_key, default))

    for code in _locale_chain(g.locale):
        meta = load_locale_config(code)
        if meta.get("seoDescription") or meta.get("seoKeywords"):
            break
    g.locale_seo_description = meta.get("seoDescription", "")
    g.locale_seo_keywords = meta.get("seoKeywords", "")


def _err(key):
    try:
        locale = g.locale
    except Exception:
        locale = DEFAULT_LOCALE
    return _ui_lookup(locale, key)


def _not_initialised_html(path):
    return (f"<h1>{_err('error.not_initialised_title')}</h1>"
            f"<p>{_err('error.not_initialised_body')}</p>"
            f"<p><code>{html_module.escape(str(path))}</code></p>"
            f"<p>{_err('error.not_initialised_hint')}</p>")


def _validate_graph_once():
    """Validate the unit graph at startup."""
    with database_connection() as conn:
        validate_graph(conn)


def _bootstrap_database():
    with database_connection() as conn:
        if not database_has_formula_table(conn):
            initialize_database()
            logger.info("Database initialised at %s", database_path())
    # Fail fast so a broken seed never serves traffic.
    try:
        _validate_graph_once()
    except Exception as exc:
        raise RuntimeError(f"Unit reference graph broken: {exc}. Fix seed.sql before serving traffic.") from exc


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
        return (_not_initialised_html(os.environ.get("SCIFIND_DB", "scifind.db")), 503)


def _get_dimension_caches():
    if "dim_caches" in g:
        return g.dim_caches
    try:
        var_map, unit_map, dim_map = build_dimension_symbol_triplet(get_db())
        g.dim_caches = {"var": var_map, "unit": unit_map, "dim": dim_map}
    except sqlite3.OperationalError as exc:
        logger.warning("Dimension symbol lookup failed: %s", exc)
        g.dim_caches = {"var": {}, "unit": {}, "dim": {}}
    return g.dim_caches


_SKIP_GLOBALS_PREFIXES = ("/api/", "/export", "/create/token-sidebar", "/create/breadcrumb")


@app.context_processor
def inject_globals():
    locale = g.get("locale", "en-us")
    path = request.path or ""
    sort_context = _sort_context_for(path, request.args.get("sort"))
    # Skip heavy globals for API/export/partial endpoints (no base.html render).
    if path.startswith(_SKIP_GLOBALS_PREFIXES):
        return dict(
            tree_json=[], diff_min=1, diff_max=10,
            current_view="formulas", dim_filter={}, dim_mode="dim",
            qty_mode="and", dim_symbols={}, dim_qty_names={},
            dimension_symbol_list=[], available_locales=[], locale_ui={},
            filter_op_symbols={},
            **sort_context,
        )
    try:
        conn = get_db()
    except sqlite3.OperationalError as exc:
        logger.warning("Database unavailable: %s", exc)
        conn = None
    tree = _cached_tree(conn) if conn is not None else []
    if conn is not None:
        fs = parse_filter_state(request.args, conn)
        indices = _cached_indices(tree)
        compressed = compress_selection(tree, fs.ids, _indices=indices)
    else:
        fs = QuantityFilter()
        compressed = set()
    name_map = _cached_name_map(tree, locale)

    # Filter quantity chips are loaded lazily via /api/quantities-filter.
    dim_qty_names = {}
    caches = {"var": {}, "unit": {}, "dim": {}}
    if conn is not None:
        caches = _get_dimension_caches()
        try:
            if qty_ids := dimension_quantity_ids(conn):
                qid_to_name = {qid: localise(name, locale) for qid, name in
                               fetch_quantities_by_ids(conn, qty_ids.values()).items()}
                dim_qty_names = {sym: qid_to_name.get(qid, "") for sym, qid in qty_ids.items()}
        except sqlite3.OperationalError as exc:
            logger.warning("Base dimension names unavailable: %s", exc)

    dim_mode = g.get("dim_mode", "dim")

    return dict(
        tree_json=_topic_tree_data(tree, name_map, compressed, fs.exclude_all, ids_provided=fs.ids_provided),
        diff_min=fs.diff_min,
        diff_max=fs.diff_max,
        current_view="quantities" if path == "/quantities"
            or path.startswith(("/quantity/", "/unit/")) else "formulas",
        dim_filter=fs.dimension_filter,
        dim_mode=fs.dim_mode,
        qty_mode=fs.quantity_mode,
        dim_symbols=caches.get(dim_mode, caches.get("dim", {})),
        dim_qty_names=dim_qty_names,
        dimension_symbol_list=dimension_symbols(conn) if conn else [],
        filter_op_symbols=_operator_display_symbols(conn) if conn is not None else {},
        available_locales=[{"code": code, "name": loc.get("meta", {}).get("name", code)}
                           for code, loc in _available_locales().items()],
        locale_ui=_build_ui_with_fallback(locale),
        **sort_context,
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
        "sort": normalize_sort(raw_value, allowed, default),
    }


def _list_guard(tree, compressed, target, fs, template, items_key, empty_key,
                sort_key, sorts):
    """Shared redirect-if-all-selected + empty-filter response for list pages."""
    if tree and compressed == {r["id"] for r in tree}:
        return redirect(target)
    if fs.exclude_all or (fs.ids_provided and not fs.ids):
        return render_template(template, **{items_key: [], "heading": _(empty_key),
                                            "sort": sort_key, "available_sorts": sorts,
                                            "pagination": {"page": 1, "per_page": 0, "total": 0,
                                                           "total_pages": 1, "show_all": False}})
    return None

def _format_constant_value(value):
    if value is None:
        return ""
    display_parts = format_sci_parts(value)
    digits = f"{display_parts['int']}.{display_parts['dec']}" if display_parts["dec"] else display_parts["int"]
    if display_parts["exp"] is None:
        return f"{display_parts['sign']}{digits}"
    return render_sci_latex(display_parts["sign"], digits, display_parts["exp"])


def _constant_value_latex(display):
    """LaTeX for the big display box; wrappers let the client measure the mantissa."""
    parts = ["\\htmlClass{cv-int}{" + display["sign"] + (display["int"] or "0") + "}"]
    if display["dec"]:
        parts.append("\\htmlClass{cv-dot}{.}")
        parts.extend(f"\\htmlClass{{cv-dec}}{{{d}}}" for d in display["dec"])
    if display["exp"] is not None:
        parts.append("\\htmlClass{cv-times}{\\times}10^{" + str(display["exp"]) + "}")
    return "".join(parts)


def _constant_units_table(conn, constant, system):
    """Per-unit value rows for a constant, converting via the unit graph; preferred unit first."""
    si_value = constant.get("value")
    rq_id = constant.get("quantity_id") or constant.get("related_quantity_id")
    if si_value is None or (not rq_id and not constant.get("unit")):
        return []

    locale = g.locale
    base = resolve_constant_base(conn, constant, system=system)
    _, default_unit_html, default_unit_symbol = _render_base(base, locale)

    units_rows = []
    if base:
        units_rows.append({
            "symbol_latex": default_unit_symbol,
            "name_html": default_unit_html,
            "system": base.get("system") or None,
            "value_latex": _format_constant_value(si_value),
        })

    seen_values = {units_rows[0]["value_latex"]} if units_rows else set()
    if base is None or not rq_id:
        return units_rows
    base_unit_ids = ({uid for uid, _ in parse_compound_unit(base["unit"])} if base["kind"] == "compound_unit"
                     else {base["id"]})
    graph = UnitGraph(conn, rq_id, locale)
    for unit_row in fetch_quantity_units(conn, rq_id):
        unit = dict(unit_row)
        if unit["id"] in base_unit_ids:
            continue
        converted = convert_value(si_value, base["id"], unit["id"], graph)
        if converted is None:
            continue
        value_latex = _format_constant_value(converted)
        if value_latex in seen_values:
            continue
        seen_values.add(value_latex)
        units_rows.append({
            "symbol_latex": Markup(wrap_symbol_in_latex(unit["symbol"])),
            "name_html": unit_name_link(unit["id"]),
            "system": unit.get("system") or None,
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
    name = localise(item.get("constant_name") or "", locale) or cid
    name_html = entity_link("constant", cid, name)
    rq_id = item.get("related_quantity_id")
    rq_name = localise(item.get("related_quantity_name") or "", locale) or rq_id or ""
    rq_symbol = (item.get("related_quantity_symbol") or "").strip()
    paren_html = ""
    if rq_name:
        sym = f"${html_module.escape(rq_symbol)}$ " if rq_symbol else ""
        paren_html = f"({sym}{entity_link('quantity', rq_id, rq_name)})"

    base = resolve_constant_base(conn, {
        "unit": item.get("constant_unit"),
        "quantity_id": rq_id,
    }, system=g.unit_system)
    return _detail_row(item.get("constant_symbol") or "", name_html,
                       paren_html, base, locale)


def _build_formula_detail_items(conn, formula_id, locale, tokens=None):
    """Build the formula detail table data from formula_id or in-memory tokens."""
    if tokens is None:
        items = [dict(r) for r in fetch_formula_token_quantities(conn, formula_id)]
    else:
        items = fetch_detail_items(conn, tokens)

    detail_items = []
    for item in items:
        qid = item.get("quantity_id")
        if not qid:
            const_item = _constant_detail_item(conn, item, locale)
            if const_item:
                detail_items.append(const_item)
            continue

        qty_name = localise(item.get("quantity_name") or "", locale) or qid
        orig_symbol = (item.get("quantity_symbol") or "").strip()
        overwrite = localise(item.get("symbol_overwrite") or "", locale)
        has_overwrite = bool(overwrite and orig_symbol and overwrite != orig_symbol)
        name_override = localise(item.get("name_overwrite") or "", locale)
        quantity_link = entity_link("quantity", qid, qty_name)

        paren_parts = [f"${orig_symbol}$"] if has_overwrite and orig_symbol else []

        if name_override:
            if qid in marker_ids_in(name_override):
                name_html = expand_quantity_markers(name_override)
            else:
                name_html = html_module.escape(name_override)
                if has_overwrite and orig_symbol:
                    paren_parts.append(quantity_link)
        else:
            name_html = quantity_link

        paren_html = f"({' '.join(paren_parts)})" if paren_parts else ""
        base = resolve_base_unit(conn, None, None, qid, system=g.unit_system)
        detail_items.append(_detail_row(
            render_variable_symbol(item, locale), name_html, paren_html, base, locale))

    return detail_items


def _detail_or_404(fetch_fn, entity_id, label_key):
    conn = get_db()
    row = fetch_fn(conn, entity_id)
    if not row:
        return None, (f"{_ui_lookup(g.locale, label_key)} {_err('error.not_found_detail')}", 404)
    row = dict(row)
    _attach_breadcrumbs_batched([row], g.locale, _cached_tree(conn))
    return row, None


def _dim_latex(conn, dimensions):
    try:
        if dimensions is None:
            return _err("error.render_error")
        caches = _get_dimension_caches()
        return format_dimensions_latex(
            *dimensions, symbols=dimension_symbols(conn), variable_symbols=caches["var"],
            unit_symbols=caches["unit"], dim_symbols=caches["dim"], mode=g.get("dim_mode", "dim"))
    except Exception:
        return _err("error.render_error")


def _safe_dims(conn, fn, *args):
    try:
        return fn(conn, *args)
    except Exception:
        cols = dimension_columns(conn)
        return [None] * len(cols)


def _with_latex(conn, rows, locale, id_key="id"):
    """Attach rendered formula latex to each row dict (batched, 3 queries)."""
    annotated = [dict(r) for r in rows]
    ids = [r.get(id_key) for r in annotated if r.get(id_key)]
    latex_map = render_formulas_latex_batched(conn, ids, locale=locale) if ids else {}
    for r in annotated:
        r["latex"] = latex_map.get(r.get(id_key), "") or ""
    return annotated


def _render_base(base, locale=None):
    """Render an already-resolved base row as (base, html, latex)."""
    if base is None:
        return None, Markup(""), ""
    name_html, symbol_latex = render_compound_unit(base, locale or g.locale)
    return base, name_html, symbol_latex


def _units_ctx(conn, quantity_id, ref_unit_id=None):
    units_table = quantity_units_table(conn, quantity_id, g.unit_system, ref_unit_id=ref_unit_id, tr=_)
    return {"units": units_table["units"], "table_data": units_table["payload"],
            "si_prefixes": units_table["si_prefixes"], "si_prefix_sections": units_table["si_prefix_sections"]}


@app.route("/formula/<formula_id>")
def formula_detail(formula_id):
    conn = get_db()
    locale = g.locale
    row, err = _detail_or_404(fetch_formula, formula_id, "detail.formula")
    if err:
        return err
    formula_sql, token_sql = build_formula_insert_sql(conn, formula_id)
    latex = render_formula_latex(conn, formula_id, locale=locale)
    return render_template(
        "formula.html",
        formula=row, latex=latex, latex_unicode=_latex_to_unicode(latex),
        relations=_with_latex(conn, fetch_formula_relations(conn, formula_id),
                              locale, id_key="related_id"),
        detail_items=_build_formula_detail_items(conn, formula_id, locale),
        dim_latex=_dim_latex(conn, _safe_dims(conn, compute_formula_dimensions, formula_id)),
        links=safe_json_list(row.get("links")),
        formula_sql=formula_sql, token_sql=token_sql,
    )


@app.route("/quantity/<quantity_id>")
def quantity_detail(quantity_id):
    conn = get_db()
    locale = g.locale
    quantity, err = _detail_or_404(fetch_quantity, quantity_id, "detail.quantity")
    if err:
        return err
    primary, non_primary = fetch_quantity_formulas_by_side(conn, quantity_id)
    constants = []
    for const in fetch_quantity_constants(conn, quantity_id):
        const = dict(const)
        const["value_latex"] = _format_constant_value(const["value"])
        _, _html, _latex = _render_base(
            resolve_constant_base(conn, const, system=g.unit_system), locale)
        const["unit_symbol_latex"] = _latex
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
    constant, err = _detail_or_404(fetch_constant, constant_id, "detail.constant")
    if err:
        return err
    if constant.get("related_quantity_id"):
        constant["quantity_name_localized"] = (
            localise(constant.get("related_quantity_name"), locale)
            or constant.get("related_quantity_id")
        )

    base, _, unit_symbol_latex = _render_base(
        resolve_constant_base(conn, constant, system=g.unit_system), locale)
    dimensions = _safe_dims(conn, constant_dimensions,
        constant.get("quantity_id") or constant.get("related_quantity_id"),
        constant.get("unit"))
    display = format_sci_parts(constant["value"]) if constant.get("value") is not None else None

    return render_template(
        "constant.html",
        constant=constant,
        links=safe_json_list(constant.get("links")),
        formulas=_with_latex(conn, fetch_constant_formulas(conn, constant_id), locale),
        dim_latex=_dim_latex(conn, dimensions),
        display=display,
        value_latex=_constant_value_latex(display) if display else "",
        unit_symbol_latex=unit_symbol_latex,
        units=_constant_units_table(conn, constant, g.unit_system),
    )


@app.route("/unit/<unit_id>")
def unit_detail(unit_id):
    conn = get_db()
    unit, err = _detail_or_404(fetch_unit, unit_id, "detail.unit")
    if err:
        return err
    locale = g.locale
    qty = fetch_quantity(conn, unit["quantity_id"])
    unit["quantity_name_localized"] = localise(qty["name"], locale) if qty else unit.get("quantity_id", "")
    ctx = _units_ctx(conn, unit["quantity_id"], ref_unit_id=unit_id) if qty \
        else {"units": None, "table_data": None, "si_prefixes": None, "si_prefix_sections": None}
    dim_latex = _dim_latex(conn, dimensions_from_row(qty, conn)) if qty else ""
    difficulty = qty["difficulty"] if qty else None
    return render_template("unit.html", unit=unit, fixed_ref=True,
                           dim_latex=dim_latex, difficulty=difficulty, **ctx)



@app.route("/")
def index():
    return redirect("/formulas")


@app.route("/base-units")
def base_units_page():
    return redirect("/quantities?is_dim=1")


@app.route("/search")
def search_page():
    limited = _rate_limit(f"search:{request.remote_addr or 'anon'}", 30)
    if limited is not None:
        return limited
    query = request.args.get("q", "").strip()[:SEARCH_QUERY_MAX_LENGTH]
    conn = get_db()
    locale = g.locale
    sort_key = normalize_sort(request.args.get("sort"), SEARCH_SORT_KEYS, DEFAULT_SEARCH_SORT)
    hits = search_entities(conn, query, locale=locale)
    meta_by_kind = fetch_search_meta(conn, hits)
    hits = sort_search_rows(conn, hits, sort_key, locale, meta_by_kind)
    results = _enrich_search_hits(conn, hits, locale, meta_by_kind)
    page, per_page, show_all = _pagination_params(request.args)
    page_results, pagination = _paginate_list(results, page, per_page, show_all)
    return render_template(
        "search.html",
        query=query,
        results=page_results,
        sort=sort_key,
        available_sorts=SEARCH_SORT_KEYS,
        pagination=pagination,
    )


def _enrich_search_hits(conn, hits, locale, meta_by_kind=None):
    """Attach latex / symbol data to each search hit for card-style rendering."""
    meta_by_kind = meta_by_kind if meta_by_kind is not None else fetch_search_meta(conn, hits)
    meta = {k: meta_by_kind.get(k, {}) for k in ("formula", "quantity", "unit", "constant")}
    detail_keys = {"formula": "detail.formula", "quantity": "detail.quantity",
                   "unit": "detail.unit", "constant": "detail.constant"}
    ids = [ent_id for kind, ent_id, _ in hits if kind == "formula"]
    latex_map = render_formulas_latex_batched(conn, ids, locale=locale) if ids else {}
    enriched = []
    for kind, ent_id, display_name in hits:
        if kind not in meta:
            continue
        item_meta = meta[kind].get(ent_id, {})
        item = {"kind": kind, "id": ent_id, "href": f"/{kind}/{ent_id}",
                "relation": _(detail_keys[kind])}
        if kind == "formula":
            item["latex"] = latex_map.get(ent_id, "") or ""
            item["name"] = display_name or item_meta.get("name_en") or ""
        else:
            item["symbol"] = item_meta.get("symbol") or ""
            if kind == "unit" and not display_name and item_meta.get("name"):
                item["name"] = localise(item_meta["name"], locale)
            else:
                item["name"] = display_name or ""
        enriched.append(item)
    return enriched


def _json_cached(payload, max_age):
    resp = app.response_class(response=json.dumps(payload), mimetype="application/json")
    resp.headers["Cache-Control"] = f"private, max-age={max_age}"
    return resp


@app.route("/api/search-suggestions")
def search_suggestions():
    query = request.args.get("q", "").strip()[:SUGGEST_QUERY_MAX_LENGTH]
    locale = getattr(g, "locale", DEFAULT_LOCALE)
    suggestions = search_entities(get_db(), query, limit=8, locale=locale)
    return _json_cached({"suggestions": [
        {"id": hit[1], "kind": hit[0], "heading": hit[2] or hit[1]} for hit in suggestions]}, 60)


@app.route("/api/quantities-filter")
def quantities_filter_data():
    """Lazy filter data for the quantity chips."""
    locale = getattr(g, "locale", DEFAULT_LOCALE)
    try:
        rows = fetch_all_quantities(get_db())
    except sqlite3.OperationalError:
        rows = []
    return _json_cached({"quantities": [
        {"id": q["id"], "name": localise(q["name"], locale), "symbol": q["symbol"] or ""} for q in rows]}, 3600)


LATEX_UNICODE_MAX_LENGTH = 4000


@app.route("/api/latex2unicode")
def latex2unicode():
    """Unicode approximation of a LaTeX fragment (live-preview pages)."""
    limited = _rate_limit(f"latex:{request.remote_addr or 'anon'}", 30)
    if limited is not None:
        return limited
    tex = request.args.get("tex", "")[:LATEX_UNICODE_MAX_LENGTH]
    return _json_cached({"unicode": _latex_to_unicode(tex)}, 86400)


@app.route("/api/units-column")
def units_column_data():
    """One conversion column for a quantity's unit tables (lazy ref-switch)."""
    limited = _rate_limit(f"unitscol:{request.remote_addr or 'anon'}", 30)
    if limited is not None:
        return limited
    qid = (request.args.get("quantity") or "").strip()[:100]
    ref = (request.args.get("ref") or "").strip()[:200]
    ids = [i for i in request.args.getlist("id")
           if re.fullmatch(r"[A-Za-z0-9_-]+", i or "")][:300]
    if not qid or not re.fullmatch(r"[A-Za-z0-9_-]+", qid) or not ref or not ids:
        return {"error": _err("error.params_required")}, 400
    column = units_column(get_db(), qid, ref, ids, getattr(g, "locale", DEFAULT_LOCALE))
    return _json_cached({"ref": ref, "column": column}, 3600)



DEFAULT_PER_PAGE = 100
MAX_PER_PAGE = 500


def _pagination_params(args):
    per_page = max(1, min(parse_int_or(args.get("per_page"), DEFAULT_PER_PAGE), MAX_PER_PAGE))
    return max(parse_int_or(args.get("page"), 1), 1), per_page, False


def _paginate_list(items, page, per_page, show_all=False):
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    return items[start:start + per_page], {"page": page, "per_page": per_page,
                                           "total": total, "total_pages": total_pages, "show_all": False}


def _prefiltered(conn, fetch_fn, fetch_all_fn, fs, topic_filter, extra_blocked=False):
    """SQL topic/difficulty pre-filter when no Python post-filter needs full rows."""
    if not extra_blocked and not fs.has_dimension_filter and not fs.quantity_ids \
            and (topic_filter or fs.diff_min > MIN_DIFFICULTY or fs.diff_max < MAX_DIFFICULTY):
        return [dict(r) for r in fetch_fn(conn, topic_ids=topic_filter or None,
                                          diff_min=fs.diff_min, diff_max=fs.diff_max)]
    return [dict(r) for r in fetch_all_fn(conn)]


def _page_batch(rows, locale, tree):
    page, per_page, show_all = _pagination_params(request.args)
    page_items, pagination = _paginate_list(rows, page, per_page, show_all)
    _attach_breadcrumbs_batched(page_items, locale, tree,
                                name_map=_cached_name_map(tree, locale),
                                parent_map=_cached_indices(tree)["parent"])
    return page_items, pagination


@app.route("/quantities")
def all_quantities():
    conn, fs, tree, compressed, sort_key, topic_filter = _list_base(
        request.args, QUANTITY_SORT_KEYS, DEFAULT_QUANTITY_SORT)
    fs.quantity_mode = "or"
    locale = g.locale
    guard = _list_guard(tree, compressed, "/quantities", fs, "quantities.html",
                        "quantities", "detail.quantities_no_results",
                        sort_key, QUANTITY_SORT_KEYS)
    if guard is not None:
        return guard

    dim_qty_ids = set(dimension_quantity_ids(conn).values()) if fs.base_quantity_only else None
    system = g.unit_system
    all_rows = _prefiltered(conn, fetch_quantities_filtered, fetch_all_quantities,
                            fs, topic_filter, extra_blocked=dim_qty_ids is not None)
    filtered = [q for q in all_rows if _passes_topic_difficulty(q, topic_filter, fs)
           and (not fs.has_dimension_filter or dimension_matches(q, fs.dimension_filter, fs.dim_mode, conn))
           and (not fs.quantity_ids or q["id"] in fs.quantity_ids)
           and (dim_qty_ids is None or q["id"] in dim_qty_ids)]
    page_items, pagination = _page_batch(sort_quantities(conn, filtered, sort_key, locale), locale, tree)
    base_map = select_base_units_batched(conn, [q["id"] for q in page_items], system)
    for quantity in page_items:
        quantity["default_unit_html"], quantity["default_unit_symbol_latex"] = render_compound_unit(
            base_map.get(quantity["id"]), locale)

    heading = _("detail.base_quantities") if fs.base_quantity_only else _heading_from_compressed(
        _("detail.quantities"), compressed, tree, locale, fs, conn)
    return render_template(
        "quantities.html",
        quantities=page_items,
        heading=heading,
        sort=sort_key,
        available_sorts=QUANTITY_SORT_KEYS,
        pagination=pagination,
    )


@app.route("/formulas")
def all_formulas():
    conn, fs, tree, compressed, sort_key, topic_filter = _list_base(
        request.args, FORMULA_SORT_KEYS, DEFAULT_FORMULA_SORT)
    locale = g.locale
    guard = _list_guard(tree, compressed, "/formulas", fs, "formulas.html",
                        "formulas", "detail.formulas_no_results",
                        sort_key, FORMULA_SORT_KEYS)
    if guard is not None:
        return guard

    formulas = _prefiltered(conn, fetch_formulas_filtered, fetch_all_formulas, fs, topic_filter)
    formulas = [f for f in formulas if _passes_topic_difficulty(f, topic_filter, fs)]

    if fs.has_dimension_filter:
        dim_map = compute_all_formula_dimensions(conn, {f["id"] for f in formulas})
        formulas = [f for f in formulas
                    if dimension_matches(dim_map.get(f["id"], {}), fs.dimension_filter, fs.dim_mode, conn)]

    if fs.quantity_ids:
        matching_ids = fetch_formulas_with_quantities(conn, fs.quantity_ids, fs.quantity_mode)
        if matching_ids is not None:
            formulas = [f for f in formulas if f["id"] in matching_ids]

    page_items, pagination = _page_batch(sort_formulas(conn, formulas, sort_key, locale), locale, tree)
    page_items = _with_latex(conn, page_items, locale)

    heading = _heading_from_compressed(_("nav.formulas"), compressed, tree, locale, fs, conn)
    return render_template(
        "formulas.html",
        formulas=page_items,
        heading=heading,
        sort=sort_key,
        available_sorts=FORMULA_SORT_KEYS,
        pagination=pagination,
    )




@app.route("/export")
def export():
    limited = _rate_limit(f"export:{request.remote_addr or 'anon'}|{request.endpoint or '?'}", 6)
    if limited is not None:
        return limited
    fmt = request.args.get("format") or request.cookies.get("sf_export_format", "csv")
    if fmt not in ("csv", "zip", "xlsx", "ods", "sql"):
        return {"error": _err("error.unknown_format")}, 400
    # Web serves zip for csv (multi-table); map plain csv -> zip.
    payload, mimetype, filename = export_payload(get_db(), "zip" if fmt == "csv" else fmt)

    resp = Response(payload, mimetype=mimetype,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    resp.set_cookie("sf_export_format", fmt, max_age=365 * 24 * 3600, path="/",
                    httponly=True, samesite="Lax", secure=app.config.get("SESSION_COOKIE_SECURE", False))
    return resp



@app.route("/create")
def create_formula():
    return render_template("create.html")




def _bracket(prefix, nparts, fields=None):
    return parse_bracket_keys(request.form.lists(), prefix, nparts, fields)


def _equation_error():
    return check_equation_length(request.form.get("equation") or "",
                                 CREATE_EQUATION_MAX_LENGTH)[1]


@app.route("/create/preview-render", methods=["POST"])
def create_preview_render():
    """Form-POST version of /api/preview that also returns detail_items HTML."""
    limited = _rate_limit(f"preview:{request.remote_addr or 'anon'}", 20)
    if limited is not None:
        return limited
    if error := _equation_error():
        return {"error": error}, 400
    conn = get_db()
    result = parse_and_preview_equation(
        conn, (request.form.get("equation") or "").strip(), locale=g.locale,
        dim_caches=_get_dimension_caches(),
        overrides=_bracket("override", 2, ("symbol", "name")),
        dim_mode=g.get("dim_mode", "dim"))
    if result.get("error") or not result.get("latex"):
        return result
    result["detail_items"] = _build_formula_detail_items(
        conn, None, g.locale, tokens=result["tokens"])
    return result


def _operator_latex(item):
    """LaTeX for an operator in the token sidebar via its own template."""
    try:
        arity = max(min(int(item.get("arity") or 2), 4), 1)
    except (TypeError, ValueError):
        arity = 2
    operands = ["x", "y", "z", "w"][:arity]
    try:
        return render_op_template(
            item.get("latex_template") or "[[0]] [[1]]", operands,
            [operand_info("operator")] * arity, item.get("id"))
    except (ValueError, KeyError, TypeError):
        return item.get("symbol") or item.get("id") or ""


def _render_token_item(item, kind, locale, selected=False):
    """One unified <div class="qty-result"> for sidebar + filter rows."""
    esc = html_module.escape
    item = dict(item)
    if kind == "op":
        sym_text, name = _operator_latex(item), item["id"]
        insert, search, chip = item.get("symbol") or item["id"], \
            f'{item["id"]} {item.get("symbol") or ""}', ""
    else:
        sym_text = item.get("symbol") or ""
        name = localise(item.get("name") or "", locale)
        insert = item["id"]
        search = f'{item["id"]} {item.get("symbol") or ""} {item.get("name") or ""}'
        chip = f' data-action="add-qty-chip" data-qty="{esc(item["id"])}" tabindex="0"'
    sym = f'<span class="qty-result-sym">${esc(sym_text)}$</span>' if sym_text else '<span class="qty-result-sym"></span>'
    return (f'<div class="qty-result{" selected" if selected else ""}" role="option" data-kind="{kind}"'
            f' data-insert="{esc(insert)}" data-search="{esc(search.lower())}"{chip}>{sym}'
            f'<span class="qty-result-name">{esc(name)}</span></div>')


def _render_token_section(label, target_id, items, kind, locale, no_match_label):
    """One labelled <section> of token items with a collapse toggle."""
    esc = html_module.escape
    tid = esc(target_id)
    body = "".join(_render_token_item(it, kind, locale) for it in items)
    return (f'<div class="section-label-row"><div class="section-label">{esc(label)}</div>'
            f'<div class="filter-buttons"><button class="filter-btn" data-action="toggle-token-section"'
            f' data-target="{tid}" type="button"><span class="token-section-icon">'
            f'<i data-lucide="chevron-up" width="16" height="16"></i></span></button></div></div>'
            f'<div class="token-list" id="{tid}">{body}</div>'
            f'<div class="token-empty">{esc(no_match_label)}</div>')


@app.route("/create/token-sidebar")
def create_token_sidebar():
    """Server-rendered Q/C/O token sidebar for the /create page."""
    conn, locale = get_db(), g.locale
    no_results = _("create.no_results")
    sections = "".join(_render_token_section(_(key), tid, fn(conn), kind, locale, no_results)
                       for key, tid, fn, kind in (
                           ("detail.quantities", "token-qty", fetch_all_quantities, "qty"),
                           ("nav.constants", "token-const", fetch_all_constants, "const"),
                           ("nav.operators", "token-op", fetch_all_operators, "op")))
    return Markup(
        '<div class="filter-qty-search-wrap">'
        f'<input type="text" class="text-field" id="token-search" placeholder="{html_module.escape(_("create.search_placeholder"))}" autocomplete="off">'
        '</div>'
        f'<div class="token-sidebar">{sections}</div>'
    )


def _render_breadcrumb(selected_id, tree, name_map):
    """Server-rendered topic breadcrumb (root > ... > selected > child trigger)."""
    esc = html_module.escape
    node = build_tree_indices(tree)["id_to_node"].get(selected_id) if selected_id else None
    kids = node.get("children") or [] if node else tree
    path = (topic_path(tree, selected_id) or [selected_id]) if node else None
    parts = [' &gt; '.join(
        f'<span class="topic-current" data-id="{esc(t)}">{esc(name_map.get(t, t))}</span>'
        for t in path)] if path else []
    if kids:
        label = _("create.topic")
        menu = "".join(_render_menu_item(k, name_map) for k in kids)
        if parts:
            parts.append(" &gt; ")
        parts.append(
            f'<span class="topic-current has-menu" data-text="{esc(label)}">'
            f'<button class="topic-dropdown-trigger" type="button">{esc(label)}</button>'
            f'<div class="topic-children-menu">{menu}</div></span>')
    return Markup("".join(parts))


def _render_menu_item(node, name_map):
    """One entry of the topic dropdown."""
    esc = html_module.escape
    nid, name = node["id"], name_map.get(node["id"], node["id"])
    if kids := node.get("children"):
        sub = "".join(_render_menu_item(c, name_map) for c in kids)
        return (f'<div class="topic-menu-item" data-id="{esc(nid)}">'
                f'<span>{esc(name)}</span><span class="caret"></span>'
                f'<div class="topic-submenu">{sub}</div></div>')
    return (f'<button type="button" class="topic-menu-item" data-id="{esc(nid)}">'
            f'<span>{esc(name)}</span></button>')


@app.route("/create/breadcrumb")
def create_breadcrumb():
    topic = (request.args.get("topic") or "").strip()[:200] or None
    tree = load_tree(get_db())
    name_map = topic_name_map(tree, g.locale)
    return _render_breadcrumb(topic, tree, name_map)


@app.route("/create/languages")
def create_languages():
    """Available locales plus the GitHub repo slug for new-issue links."""
    items = [{"code": code, "name": loc.get("meta", {}).get("name", code)}
             for code, loc in sorted(_available_locales().items())]
    return {"current": getattr(g, "locale", DEFAULT_LOCALE), "locales": items,
            "repo": os.environ.get("SCIFIND_GITHUB_REPO", "Creeperman3000/Scifind")}


def _build_create_sql_payload(conn, form):
    """Parse the /create form fields and return (formula_sql, token_sql)."""
    field = lambda f: (form.get(f) or "").strip()
    links = [ln.strip() for ln in field("links").splitlines() if ln.strip()] or None
    tr_top, tr_ov = _bracket("tr", 2), _bracket("tr_overrides", 3, ("symbol", "name"))
    translations = {loc: ({k: tr_top[loc][k] for k in ("name", "description") if k in tr_top.get(loc, {})}
                          | ({"overrides": tr_ov[loc]} if loc in tr_ov else {}))
                    for loc in set(tr_top) | set(tr_ov)}
    translations = {loc: e for loc, e in translations.items() if e}
    return build_create_sql(
        conn, name_en=field("name_en"), topic=field("topic"),
        difficulty=field("difficulty") or "2", equation=form.get("equation") or "",
        overrides=_bracket("override", 2, ("symbol", "name")),
        description=field("description") or None, links=links,
        translations=translations, formula_id=field("formula_id"))


def _render_sql_modal_html(formula_sql, token_sql):
    esc = html_module.escape
    copy_title = esc(_("tooltip.copy"))
    block = lambda pid, sql, act: (
        f'<div class="sql-block"><button class="formula-copy-btn" type="button"'
        f' data-action="{act}" title="{copy_title}"><i data-lucide="copy" width="16" height="16"></i></button>'
        f'<pre id="{pid}">{esc(sql)}</pre></div>')
    return Markup(
        f'<h3>{esc(_("create.formula_insert"))}</h3>'
        + block("formula-sql", formula_sql, "copy-formula-sql-export")
        + f'<h3>{esc(_("create.token_inserts"))}</h3>'
        + block("token-sql", token_sql, "copy-token-sql-export"))


def _sql_error(message, code=None):
    msg, err_code = str(message)[:200], code or "error"
    # JSON error contract (client prefers JSON, falls back to HTML data-error).
    if "application/json" in (request.headers.get("Accept") or ""):
        return {"error": msg, "code": err_code}, 400
    esc = html_module.escape
    return Markup(f'<p class="detail-desc" data-error="{esc(err_code)}">{esc(msg)}</p>'), 400


@app.route("/create/build-sql", methods=["POST"])
def create_build_sql():
    """Form-POST equivalent of /api/build-sql returning rendered modal HTML."""
    limited = _rate_limit(f"buildsql:{request.remote_addr or 'anon'}", 20)
    if limited is not None:
        return limited
    if error := _equation_error():
        return _sql_error(error, "equation-too-long")
    try:
        formula_sql, token_sql = _build_create_sql_payload(get_db(), request.form)
    except ValueError as e:
        return _sql_error(e)
    return _render_sql_modal_html(formula_sql, token_sql)




if __name__ == "__main__":
    host = os.environ.get("SCIFIND_HOST", "127.0.0.1")
    port = parse_int_or(os.environ.get("SCIFIND_PORT", "5000"), 5000)
    app.run(host=host, port=port)
