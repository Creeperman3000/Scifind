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
    fetch_si_prefixes,
    fetch_quantity_formulas_by_side,
    fetch_quantity_related_formulas,
    fetch_quantities_by_ids,
    fetch_constant,
    fetch_constant_formulas,
    fetch_quantity_constants,
    compute_formula_dimensions,
    compute_all_formula_dimensions,
    compute_default_unit_dimensions,
    fetch_formulas_with_all_quantities,
    fetch_formulas_with_any_quantity,
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
    build_formula_sql,
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
from scifind_lib.constants import SUPERSCRIPT_DIGITS
from scifind_lib.filter import MIN_DIFFICULTY, MAX_DIFFICULTY, parse_filter_state
from scifind_lib.units import parse_default_unit

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
    int(os.environ.get("SCIFIND_MAX_UPLOAD_MB", "32")) * 1024 * 1024
)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 365 * 86400


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


def _default_unit_system(db, du_ids):
    """Unit system of a quantity's default-unit parts ('SI' unless some
    part belongs to another system)."""
    if not du_ids:
        return "SI"
    placeholders, params = _in_clause(tuple(du_ids))
    row = db.execute(
        f"SELECT unit_system FROM unit WHERE id IN ({placeholders}) "
        f"AND unit_system != 'SI' LIMIT 1",
        params,
    ).fetchone()
    return row["unit_system"] if row else "SI"


def _quantity_units_table(db, quantity_id, default_unit, ref_unit_id=None):
    """Rows for the units table shared by /quantity/<id> and /unit/<id>:
    the quantity's default unit first, then its registered units.

    Factor/offset cells are filled client-side (web/app.js) so the
    reference unit can be switched without a page reload; the reference
    defaults to ref_unit_id when it is one of the quantity's units,
    otherwise to the quantity default. The raw per-unit conversion data
    is embedded as JSON for the client."""
    locale = g.locale
    default_unit_html, default_unit_symbol_latex = _render_default_unit(
        default_unit, locale
    )
    default_parts = parse_default_unit(default_unit)
    du_ids = {uid for uid, _ in default_parts}
    unit_system = _default_unit_system(db, du_ids)

    entries = []
    si_prefixes, si_cgs_id = _append_si_prefix_entries(
        db, quantity_id, default_unit, entries
    )

    default_entry = None
    if default_parts:
        default_entry = {
            "id": None,
            "symbol_latex": default_unit_symbol_latex,
            "name_html": default_unit_html,
            "label": format_default_unit_html(default_unit, locale=locale),
            "unit_system": unit_system,
            "factor": 1,
            "offset": 0,
        }
        entries.append(default_entry)

    for eu in (dict(u) for u in fetch_quantity_units(db, quantity_id)):
        if eu["id"] in du_ids:
            continue
        # A registered CGS unit that coincides with a prefix-family row
        # (centimetre, gram) is shown only in the family table.
        if eu["id"] == si_cgs_id:
            continue
        entries.append({
            "id": eu["id"],
            "symbol_latex": Markup(render_symbol(eu["symbol"])),
            "name_html": _unit_name_link(eu["id"]),
            "label": (localise(eu.get("name"), locale)
                      or localise(eu.get("name"), "en-us")
                      or eu["id"].replace("_", " ")),
            "unit_system": eu.get("unit_system") or "any",
            "factor": eu.get("factor", 1) or 1,
            "offset": eu.get("offset", 0) or 0,
        })

    ref = next(
        (e for e in entries if e["id"] and e["id"] == ref_unit_id),
        None,
    )
    if not ref and ref_unit_id and ref_unit_id == si_cgs_id and si_prefixes:
        # On /unit/<id> for a CGS unit that lives only in the family
        # table now (centimetre, gram), its prefixed-family twin takes
        # over as the initial reference.
        dup_row = next(
            (r for r in si_prefixes if r.get("system_key") == "detail.cgs_base"),
            None,
        )
        if dup_row:
            ref = next(
                (e for e in entries if e["id"] == dup_row["payload_id"]), None
            )
    # Without an explicit reference (/quantity/<id>) the default unit
    # starts as the reference.
    if ref is None:
        ref = default_entry

    units = [{
        "id": e["id"] or "",
        "symbol_latex": e["symbol_latex"],
        "name_html": e["name_html"],
        "unit_system": e["unit_system"],
        "is_ref": e is ref,
    } for e in entries if not (e["id"] or "").startswith("si_")]

    payload = {
        "ref": (ref["id"] or "") if ref else "",
        "ref_label": re.sub(r"<[^>]+>", "",
                            (ref["label"] if ref else "")),
        "entries": [{"id": e["id"] or "", "factor": e["factor"],
                     "offset": e["offset"], "si_exp": e.get("si_exp"),
                     "label": e["label"]}
                    for e in entries],
    }
    if si_prefixes:
        for r in si_prefixes:
            r["is_ref"] = r["payload_id"] == payload["ref"]
    return {
        "units": units,
        "payload": payload,
        "si_prefixes": si_prefixes,
    }


# Quantity default units whose SI-prefixed forms get a prefix table;
# kilogram prefixes attach to the gram.
PREFIXABLE_BASE_UNITS = {
    "metre": "metre",
    "kilogram": "gram",
    "second": "second",
    "ampere": "ampere",
    "kelvin": "kelvin",
    "mole": "mole",
    "candela": "candela",
}

# Exponent (relative to the prefixable base) of the actual SI base unit;
# kilogram is the SI base of mass even though prefixes attach to gram.
SI_BASE_EXPONENT = {"gram": 3}

# Prefix exponents shown before the user expands the full list; the CGS
# base row is added to this set when it coincides with a prefixed form.
DEFAULT_VISIBLE_EXPONENTS = {0, 3, -3}


def _si_prefix_rows(db, default_unit, quantity_id):
    """Rows for the SI-prefix table shared by /quantity/<id> and
    /unit/<id>: every SI-prefixed form of the quantity's base unit
    (km kilometre 10^3), largest exponent first, plus the unprefixed
    base unit at 10^0.

    Rows carry a stable payload id ("si_<prefix>") so they can join the
    reference-unit picking, and small linked "SI base"/"CGS base"
    badges. A quantity's registered CGS unit that coincides with a
    prefixed form (centimetre, gram) is badged in place; any other CGS
    unit (dyne) simply stays in the regular units table. Returns None
    when the default unit is not a single prefixable base unit."""
    locale = g.locale
    parts = parse_default_unit(default_unit)
    if len(parts) != 1 or parts[0][1] != 1:
        return None
    base_id = PREFIXABLE_BASE_UNITS.get(parts[0][0])
    if not base_id:
        return None
    base = fetch_unit(db, base_id)
    if not base:
        return None

    base_name = localise(base["name"], locale) or localise(base["name"], "en-us")
    base_symbol_latex = render_symbol(base["symbol"])
    base_factor = float(base["factor"] or 1)
    # The actual SI base unit of the quantity (kilogram for mass), which
    # prefixes attach to the gram.
    default_unit_id = parts[0][0]

    cgs_row = None
    for cu in db.execute(
        "SELECT id, factor FROM unit WHERE quantity_id = ? AND unit_system = 'CGS'",
        (quantity_id,),
    ).fetchall():
        f = float(cu["factor"] or 0)
        if f > 0:
            cgs_row = {"id": cu["id"], "factor": f}
            break

    def system_field(exp):
        """System-column designation for a prefix row: ("SI base" /
        "CGS base", unit id whose page the row name links to) — or None
        for a plain family row, whose "SI" merges into the Unit cell."""
        row_factor = (10 ** exp) * base_factor
        if exp == SI_BASE_EXPONENT.get(base_id, 0) and default_unit_id:
            return ("detail.si_base", default_unit_id)
        if cgs_row and math.isclose(row_factor, cgs_row["factor"], rel_tol=1e-12):
            return ("detail.cgs_base", cgs_row["id"])
        return None

    prefixed = []
    for p in fetch_si_prefixes(db):
        exp = int(p["exponent"])
        combined = localise(p["name"], locale) + base_name.lower()
        sys_key, link_unit_id = system_field(exp) or (None, None)
        prefixed.append({
            "id": f"si_{p['id']}",
            "exp": exp,
            "factor": (10 ** exp) * base_factor,
            "symbol_latex": Markup(render_symbol(p["symbol"]) + base_symbol_latex),
            "name": combined[:1].upper() + combined[1:],
            "system_key": sys_key,
            "link_unit_id": link_unit_id,
            "value_latex": f"10^{{{exp}}}",
        })
    # The unprefixed base row sits between deca (10^1) and deci (10^-1).
    insert_at = next(
        (i for i, r in enumerate(prefixed) if r["exp"] < 0), len(prefixed)
    )
    base_sys = system_field(0) or (None, None)
    prefixed.insert(insert_at, {
        "id": "",
        "exp": 0,
        "factor": base_factor,
        "symbol_latex": Markup(base_symbol_latex),
        "name": base_name,
        "system_key": base_sys[0],
        "link_unit_id": base_sys[1],
        "value_latex": "10^{0}",
    })
    visible = set(DEFAULT_VISIBLE_EXPONENTS)
    if cgs_row:
        visible.update(
            r["exp"] for r in prefixed
            if math.isclose((10 ** r["exp"]) * base_factor,
                            cgs_row["factor"], rel_tol=1e-12)
        )
    for r in prefixed:
        r["collapsed"] = r["exp"] not in visible
    # A registered CGS unit that coincides with a family row (centimetre,
    # gram) is represented there, so the caller can drop the duplicate
    # from the regular units table.
    return prefixed, (cgs_row["id"] if cgs_row else None)


def _append_si_prefix_entries(db, quantity_id, default_unit, entries):
    """Join the SI-prefix family onto the shared units-table state.

    Every prefix row gets a synthetic payload id ("si_<prefix>"; the
    bare base unit becomes "si_base") so both tables in the Units
    section — registered units and the prefix family — share one
    reference-unit picker without colliding with real unit ids.
    Returns (decorated rows for template rendering or None, id of the
    registered CGS unit duplicated by a family row or None)."""
    result = _si_prefix_rows(db, default_unit, quantity_id)
    if result is None:
        return None, None
    rows, cgs_unit_id = result
    for r in rows:
        classes = []
        if not r["id"]:
            classes.append("si-base-row")
        if r["collapsed"]:
            classes.append("si-extra")
        r["row_class"] = " ".join(classes)
        r["payload_id"] = r["id"] or "si_base"
        # Synthetic rows carry their decade exponent so the client-side
        # converter can hop through them (ms -> s -> min -> hour -> day).
        entries.append({
            "id": r["payload_id"],
            "label": r["name"],
            "factor": r["factor"],
            "offset": 0,
            "si_exp": r["exp"],
        })
    return rows, cgs_unit_id


@app.context_processor
def inject_globals():
    locale = g.get("locale", "en-us")
    tree = load_tree()
    db = None
    try:
        db = get_db()
    except sqlite3.OperationalError as exc:
        logger.warning("Database unavailable: %s", exc)
    fs = parse_filter_state(request.args)
    name_map = topic_name_map(tree, locale)
    compressed = compress_selection(tree, fs.ids)

    all_quantities_for_filter = []
    dimension_caches = {"var": {}, "unit": {}, "dim": {}}
    dim_qty_names = {}
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
        try:
            qid_to_name = {
                q["id"]: localise(q["name"], locale)
                for q in db.execute(
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
    cids = {tok["constant_id"] for tok in tokens
            if tok.get("token_kind") == "constant"}
    qrows = {}
    if qids:
        placeholder, qparams = _in_clause(qids)
        qrows = {
            r["id"]: r for r in db.execute(
                f"SELECT id, name, symbol, default_unit FROM quantity "
                f"WHERE id IN ({placeholder})", qparams
            ).fetchall()
        }
    crows = {}
    if cids:
        placeholder, cparams = _in_clause(cids)
        crows = {
            r["id"]: r for r in db.execute(
                f"""
                SELECT c.id, c.name, c.symbol,
                       rq.id AS related_quantity_id,
                       rq.name AS related_quantity_name,
                       rq.symbol AS related_quantity_symbol,
                       rq.default_unit AS related_quantity_default_unit
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
                "quantity_name_overwrite": tok.get("quantity_name_overwrite") or "",
                "label": tok.get("label") or "",
                "default_unit": qrow["default_unit"],
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
                "related_quantity_default_unit": crow["related_quantity_default_unit"],
            })
    return items


def _format_constant_value(value):
    """Format a constant's numerical value as a compact LaTeX string.

    Same thresholds and precision as _constant_value_display so tables
    and the big display box always agree."""
    if value is None:
        return ""
    d = _constant_value_display(value)
    digits = f"{d['int']}.{d['dec']}" if d["dec"] else d["int"]
    if d["exp"] is None:
        return f"{d['sign']}{digits}"
    return f"{d['sign']}{digits} \\times 10^{{{d['exp']}}}"


def _constant_value_display(value):
    """Split a constant's value for the big display box.

    Returns {"sign", "int", "dec", "exp"}: integer digits shown large,
    `dec` digits shrink progressively, and values that are too large or
    too small are normalised to a 10^`exp` factor (mantissa in [1, 10))."""
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
    """LaTeX for the big display box, rendered by KaTeX on the client.

    Sign + integer part, the decimal mark and every decimal digit carry
    \\htmlClass wrappers (.cv-int/.cv-dot/.cv-dec) so the client fit/fade
    layout can measure them and anchor the fade at the end of the
    mantissa. A \\times10^ factor is appended when the value needs one,
    wrapped as .cv-times so the fade can be kept off it."""
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


def _constant_units_table(db, c):
    """Rows for the constant's per-unit value table: exactly the units of
    constant.quantity_id as shown on that quantity's page (its default
    unit first, then its registered units)."""
    si_value = c.get("value")
    rq_id = c.get("quantity_id")
    if si_value is None or not rq_id:
        return []

    locale = g.locale
    quantity_default = (c.get("related_quantity_default_unit")
                        or c.get("default_unit"))
    default_unit_html, default_unit_symbol = _render_default_unit(
        quantity_default, locale
    )
    rows = []
    default_parts = parse_default_unit(quantity_default)
    du_ids = {uid for uid, _ in default_parts}
    if default_parts:
        rows.append({
            "symbol_latex": default_unit_symbol,
            "name_html": default_unit_html,
            "unit_system": _default_unit_system(db, du_ids),
            "value_latex": _format_constant_value(si_value),
        })

    seen_values = {rows[0]["value_latex"]} if rows else set()
    for eu_row in fetch_quantity_units(db, rq_id):
        eu = dict(eu_row)
        if eu["id"] in du_ids:
            continue
        factor = eu["factor"] or 1
        offset = eu["offset"] or 0
        converted = (si_value - offset) / factor
        value_latex = _format_constant_value(converted)
        if value_latex in seen_values:
            continue
        seen_values.add(value_latex)
        rows.append({
            "symbol_latex": Markup(render_symbol(eu["symbol"])),
            "name_html": _unit_name_link(eu["id"]),
            "unit_system": eu.get("unit_system") or "any",
            "value_latex": value_latex,
        })
    return rows


def _constant_detail_item(db, item, locale):
    """Detail-table entry for one constant token: symbol + linked name,
    parenthesised related quantity, related quantity's default unit."""
    cid = item.get("constant_id")
    if not cid:
        return None
    name = item.get("constant_name") or cid.replace("_", " ").title()
    name_html = (
        f'<a href="/constant/{html_module.escape(cid)}">'
        f"{html_module.escape(name)}</a>"
    )
    rq_id = item.get("related_quantity_id")
    rq_name = item.get("related_quantity_name")
    rq_symbol = (item.get("related_quantity_symbol") or "").strip()
    paren_parts = []
    if rq_name:
        paren_parts.append(f"${rq_symbol}$" if rq_symbol else "")
        paren_parts.append(
            f'<a href="/quantity/{html_module.escape(rq_id)}">'
            f"{html_module.escape(rq_name)}</a>"
        )
    paren_html = (
        f"({' '.join(part for part in paren_parts if part)})"
        if any(paren_parts) else ""
    )

    unit_html, unit_sym = _render_default_unit(
        item.get("related_quantity_default_unit"), locale
    )
    return {
        "symbol_latex": item.get("constant_symbol") or "",
        "name_html": Markup(name_html),
        "paren_html": Markup(paren_html) if paren_html else "",
        "default_unit_html": unit_html,
        "default_unit_symbol_latex": unit_sym,
    }


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
            const_item = _constant_detail_item(db, item, locale)
            if const_item:
                result.append(const_item)
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
    formula_sql, token_sql = build_formula_sql(db, formula_id)
    return render_template(
        "formula.html",
        formula=row, latex=latex,
        relations=related, detail_items=detail_items,
        dim_latex=dim_latex, links=links,
        formula_sql=formula_sql, token_sql=token_sql,
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

    units_table = _quantity_units_table(db, quantity_id, q["default_unit"])
    units = units_table["units"]

    dim_caches = _get_dimension_caches()
    dim_latex = format_dimensions_latex(
        *extract_dimensions_from_row(q),
        variable_symbols=dim_caches["var"],
        unit_symbols=dim_caches["unit"],
        dim_symbols=dim_caches["dim"],
        mode=g.get("dim_mode", "dim"),
    )
    constants = []
    for const in fetch_quantity_constants(db, quantity_id):
        const = dict(const)
        const["value_latex"] = _format_constant_value(const["value"])
        const["unit_symbol_latex"] = _render_unit_symbol(const["unit_default"])
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
    )


@app.route("/constant/<constant_id>")
def constant_detail(constant_id):
    db = get_db()
    locale = g.locale
    c = fetch_constant(db, constant_id)
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
    for f in fetch_constant_formulas(db, constant_id):
        f = dict(f)
        f["latex"] = render_formula(db, f["id"], locale=locale) or ""
        formulas.append(f)

    dim_caches = _get_dimension_caches()
    dim_latex = format_dimensions_latex(
        *compute_default_unit_dimensions(db, c.get("default_unit")),
        variable_symbols=dim_caches["var"],
        unit_symbols=dim_caches["unit"],
        dim_symbols=dim_caches["dim"],
        mode=g.get("dim_mode", "dim"),
    )

    display = _constant_value_display(c["value"]) if c.get("value") is not None else None
    unit_symbol_latex = _render_unit_symbol(c.get("default_unit"))
    units = _constant_units_table(db, c)

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
    db = get_db()
    unit = fetch_unit(db, unit_id)
    if not unit:
        return "Unit not found", 404
    unit = dict(unit)
    locale = g.locale
    qty = fetch_quantity(db, unit["quantity_id"])
    unit["quantity_name_localized"] = localise(qty["name"], locale) if qty else unit.get("quantity_id", "")
    _attach_breadcrumbs(unit, locale)
    units = table_data = si_prefixes = None
    if qty:
        # On a unit's own page the reference unit is that unit.
        units_table = _quantity_units_table(
            db, unit["quantity_id"], qty["default_unit"], ref_unit_id=unit_id,
        )
        units = units_table["units"]
        table_data = units_table["payload"]
        si_prefixes = units_table["si_prefixes"]
    return render_template(
        "unit.html",
        unit=unit,
        units=units,
        table_data=table_data,
        si_prefixes=si_prefixes,
    )


@app.route("/search")
def search_page():
    query = request.args.get("q", "").strip()[:SEARCH_QUERY_MAX_LENGTH]
    db = get_db()
    locale = g.locale
    sort_key = _resolve_sort(request.args.get("sort"), SEARCH_SORT_KEYS, DEFAULT_SEARCH_SORT)
    hits = search_headings(db, query, locale=locale)
    hits = sort_search_rows(db, hits, sort_key, locale)
    results = _enrich_search_hits(db, hits, locale)
    return render_template(
        "search.html",
        query=query,
        results=results,
        sort=sort_key,
        available_sorts=SEARCH_SORT_KEYS,
    )


def _enrich_search_hits(db, hits, locale):
    """Attach latex / symbol data to each search hit so the template can
    render formula-card style entries."""
    formula_ids = [h[1] for h in hits if h[0] == "formula"]
    quantity_ids = [h[1] for h in hits if h[0] == "quantity"]
    unit_ids = [h[1] for h in hits if h[0] == "unit"]
    constant_ids = [h[1] for h in hits if h[0] == "constant"]

    formula_meta = {}
    if formula_ids:
        placeholder, params = _in_clause(formula_ids)
        for r in db.execute(
            f"SELECT id, json_extract(name, '$.en-us') AS name_en FROM formula WHERE id IN ({placeholder})",
            params,
        ).fetchall():
            formula_meta[r["id"]] = {"name_en": r["name_en"] or r["id"]}

    quantity_meta = {}
    if quantity_ids:
        placeholder, params = _in_clause(quantity_ids)
        for r in db.execute(
            f"SELECT id, symbol FROM quantity WHERE id IN ({placeholder})",
            params,
        ).fetchall():
            quantity_meta[r["id"]] = {"symbol": r["symbol"] or ""}

    unit_meta = {}
    if unit_ids:
        placeholder, params = _in_clause(unit_ids)
        for r in db.execute(
            f"SELECT u.id, u.symbol, u.name FROM unit u WHERE u.id IN ({placeholder})",
            params,
        ).fetchall():
            unit_meta[r["id"]] = {
                "symbol": r["symbol"] or "",
                "name": localise(r["name"], locale) if r["name"] else r["id"],
            }

    constant_meta = {}
    if constant_ids:
        placeholder, params = _in_clause(constant_ids)
        for r in db.execute(
            f"SELECT id, symbol FROM constant WHERE id IN ({placeholder})",
            params,
        ).fetchall():
            constant_meta[r["id"]] = {"symbol": r["symbol"] or ""}

    enriched = []
    for kind, ent_id, display_name in hits:
        if kind == "formula":
            meta = formula_meta.get(ent_id, {})
            enriched.append({
                "kind": kind, "id": ent_id,
                "href": f"/formula/{ent_id}",
                "latex": render_formula(db, ent_id, locale),
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
    suggestions = suggest_headings(get_db(), query, locale=locale)
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
        f'<input type="text" class="text-field" id="token-search" placeholder="{html_module.escape(_("create.search_placeholder"))}" autocomplete="off">'
        '</div>'
        f'<div class="token-sidebar">{"".join(sections)}</div>'
    )


def _render_breadcrumb(selected_id, tree, name_map):
    """Server-rendered topic breadcrumb (root > ... > selected > child trigger)."""
    selected_node = _find_node(tree, selected_id) if selected_id else None
    if selected_node is not None:
        current_kids = selected_node.get("children") or []
        path = topic_path(tree, selected_id) or [selected_id]
    else:
        current_kids = tree
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

    if current_kids:
        if parts:
            parts.append(' &gt; ')
        trigger_label = _("create.topic")
        menu_items = "".join(
            _render_menu_item(kid, name_map) for kid in current_kids
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
