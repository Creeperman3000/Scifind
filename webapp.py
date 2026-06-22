#!/usr/bin/env python3
"""Flask webapp for Scifind — a structured physics formula database."""

import html
import io
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

from flask import Flask, render_template, request, g, Response, redirect, session
from itertools import groupby
from markupsafe import Markup

_project_dir = Path(__file__).resolve().parent
if str(_project_dir) not in sys.path:
    sys.path.insert(0, str(_project_dir))

from formula_lib import (
    get_conn, render_formula_items, render_dimensions_latex,
    render_si_unit_html, render_si_unit_latex, parse_si_unit_json,
    decompose_si_unit_parts,
    render_unit_decomposition, is_composite_unit,
    get_formula_detail, get_formula_items,
    get_formula_conditions, get_formula_relations, get_formula_variables,
    get_variable_detail, get_variable_units, get_variable_formulas,
    get_unit_detail,
    get_base_units, get_all_variables, get_all_formulas, get_formulas_by_science,
    search, migrate_db,
    export_csv, export_csv_dir, export_xlsx, export_ods,
    import_csv, import_csv_dir, import_xlsx, import_ods, rebuild_fts,
    en as locale_en,
)

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

_db_migrated = False

# Cache for dimension symbol lookups (built lazily by fmt_dim)
_dim_var_latex_map = None
_dim_unit_symbol_map = None


@app.before_request
def detect_locale():
    """Detect user locale from ?locale param → session → Accept-Language."""
    locale = request.args.get("locale")
    if locale in ("en-us", "en-uk"):
        session["locale"] = locale
    if session.get("locale") in ("en-us", "en-uk"):
        g.locale = session["locale"]
    else:
        lang = request.headers.get("Accept-Language", "")[:5]
        g.locale = "en-uk" if lang.startswith("en-GB") else "en-us"

    dim_mode = request.args.get("dim_mode")
    if dim_mode in ("var", "unit"):
        session["dim_mode"] = dim_mode
    g.dim_mode = session.get("dim_mode", "var")


@app.template_global()
def locale_text(data):
    """Extract locale-appropriate text from JSON i18n string."""
    if not data:
        return ""
    try:
        d = json.loads(data)
        val = d.get(g.locale) or d.get("en-us") or data
        return val
    except (json.JSONDecodeError, TypeError):
        return str(data)


def _l(row, locale, *fields):
    """Apply locale to JSON text fields in a row."""
    if locale == "en-us":
        return row
    r = dict(row)
    for f in fields:
        raw = r.get(f)
        if raw and isinstance(raw, str) and (raw.startswith("{") or raw.startswith('"')):
            r[f"{f}_en"] = locale_en(raw, locale)
        # handle raw_name -> name pattern
        raw_key = f"{f}_raw"
        if raw_key in r and r[raw_key] and isinstance(r[raw_key], str) and r[raw_key].startswith("{"):
            r[f] = locale_en(r[raw_key], locale)
    return r


def _unit_name_map(db, locale):
    """Build {id: name} map with locale applied. Cached per request on g."""
    cache_key = "_unit_names_" + locale
    if hasattr(g, cache_key):
        return getattr(g, cache_key)
    rows = db.execute("SELECT id, name FROM units").fetchall()
    result = {r["id"]: locale_en(r["name"], locale) for r in rows}
    setattr(g, cache_key, result)
    return result


def get_db():
    global _db_migrated
    if "db" not in g:
        g.db = get_conn()
        if not _db_migrated:
            migrate_db(g.db)
            _db_migrated = True
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.template_global()
def render_formula(formula_items):
    return render_formula_items(formula_items)


@app.template_global()
def unit_name(unit_id):
    """Render a unit name with links, decomposing composites (e.g. 'metre_per_second')."""
    loc = g.locale if hasattr(g, "locale") else "en-us"
    names = _unit_name_map(g.db, loc) if "db" in g else _unit_name_map(get_db(), loc)
    return Markup(render_unit_decomposition(
        unit_id,
        name_func=lambda uid: names.get(uid, uid.replace("_"," ").title()),
        url_func=lambda uid: f"/unit/{uid}",
        locale=loc,
    ))


@app.template_global()
def fmt_dim(dim_M=0, dim_L=0, dim_T=0, dim_I=0, dim_Θ=0, dim_N=0, dim_J=0):
    global _dim_var_latex_map, _dim_unit_symbol_map
    if _dim_var_latex_map is None:
        _dim_var_latex_map = {}
        _dim_unit_symbol_map = {}
        db = get_db()
        for var_id in ("mass", "length", "period", "electric_current",
                       "temperature", "amount", "luminous_intensity"):
            row = db.execute("SELECT latex FROM variables WHERE id=?", (var_id,)).fetchone()
            if row:
                _dim_var_latex_map[var_id] = f"\\mathrm{{{row['latex']}}}"
            row = db.execute("SELECT symbol FROM units WHERE variable_id=? AND si_unit=1", (var_id,)).fetchone()
            if row:
                sym = row["symbol"]
                if sym.startswith("\\mathrm"):
                    _dim_unit_symbol_map[var_id] = sym
                else:
                    _dim_unit_symbol_map[var_id] = f"\\mathrm{{{sym}}}"
    return render_dimensions_latex(
        dim_M, dim_L, dim_T, dim_I, dim_Θ, dim_N, dim_J,
        var_latex_map=_dim_var_latex_map,
        unit_symbol_map=_dim_unit_symbol_map,
        mode=g.get("dim_mode", "var"),
    )


@app.template_global()
def si_unit_latex(si_unit_json):
    return render_si_unit_latex(si_unit_json)


_SYMBOL_MATH = {
    "\\newton": "\\mathrm{N}", "\\ohm": "\\mathrm{\\Omega}",
    "\\degreeCelsius": "\\mathrm{^{\\circ}C}", "\\celsius": "\\mathrm{^{\\circ}C}",
    "\\meter": "\\mathrm{m}", "\\metre": "\\mathrm{m}",
    "\\kilogram": "\\mathrm{kg}", "\\kilogramme": "\\mathrm{kg}",
    "\\second": "\\mathrm{s}", "\\kelvin": "\\mathrm{K}",
    "\\gram": "\\mathrm{g}", "\\ampere": "\\mathrm{A}",
    "\\mole": "\\mathrm{mol}", "\\candela": "\\mathrm{cd}",
    "\\hertz": "\\mathrm{Hz}",
    "\\text{\\textdegree C}": "\\mathrm{^{\\circ}C}",
    "\\Omega": "\\mathrm{\\Omega}",
}


@app.template_global()
def render_symbol(symbol):
    """Convert a LaTeX/siunitx symbol to \\mathrm{} LaTeX."""
    if not symbol:
        return ""
    s = symbol.strip()
    if s in _SYMBOL_MATH:
        return _SYMBOL_MATH[s]
    # Already wrapped in \mathrm{} or has braces that make it safe
    if s.startswith("\\mathrm{") or s.startswith("\\") or s.startswith("{}"):
        return s
    return "\\mathrm{" + html.escape(s) + "}"


@app.template_global()
def uniq_topics(formulas):
    seen = set()
    out = []
    for f in formulas:
        t = f["topic_en"]
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


# ── Home ─────────────────────────────────────────────

@app.route("/")
def index():
    db = get_db()
    locale = g.locale
    base_units = get_base_units(db)
    base_units = [_l(u, locale, "name", "var_name") for u in base_units]
    by_science = get_formulas_by_science(db)
    return render_template("index.html", base_units=base_units, by_science=by_science)


# ── Formula ──────────────────────────────────────────

@app.route("/formula/<formula_id>")
def formula_detail(formula_id):
    db = get_db()
    locale = g.locale
    row = get_formula_detail(db, formula_id)
    if not row:
        return "Formula not found", 404
    row = _l(row, locale, "name", "description", "science", "branch", "topic")
    items = get_formula_items(db, formula_id)
    latex = render_formula_items(items) if items else ""
    conds = get_formula_conditions(db, formula_id)
    relations = get_formula_relations(db, formula_id)
    variables = get_formula_variables(db, formula_id)
    unit_names = _unit_name_map(db, locale)
    parsed_vars = []
    for v in variables:
        v = _l(v, locale, "name")
        si_html = render_si_unit_html(v["si_unit"],
                     unit_url_func=lambda uid: f"/unit/{uid}",
                     unit_name_func=lambda uid: unit_names.get(uid, uid.replace("_"," ").title()),
                     locale=locale)
        parsed_vars.append(dict(v, si_html=si_html))
    return render_template(
        "formula.html",
        formula=row, latex=latex, conds=conds,
        relations=relations, variables=parsed_vars,
    )


# ── Variable ─────────────────────────────────────────

@app.route("/variable/<variable_id>")
def variable_detail(variable_id):
    db = get_db()
    locale = g.locale
    v = get_variable_detail(db, variable_id)
    if not v:
        return "Variable not found", 404
    v = _l(v, locale, "name", "description")
    unit_names = _unit_name_map(db, locale)
    units = [_l(u, locale, "name") for u in get_variable_units(db, variable_id)]
    formulas = get_variable_formulas(db, variable_id)
    return render_template(
        "variable.html",
        var=v,
        units=units, formulas=formulas,
    )


# ── Unit ─────────────────────────────────────────────

@app.route("/unit/<unit_id>")
def unit_detail(unit_id):
    db = get_db()
    u = get_unit_detail(db, unit_id)
    if not u:
        return "Unit not found", 404
    if is_composite_unit(unit_id):
        return redirect(f"/variable/{u['variable_id']}")
    u = _l(u, g.locale, "name")
    return render_template("unit.html", unit=u)


# ── Search ───────────────────────────────────────────

@app.route("/search")
def search_page():
    q = request.args.get("q", "")
    if not q:
        return render_template("search.html", query="", results=[])
    results = search(get_db(), q)
    return render_template("search.html", query=q, results=results)


# ── All Variables ────────────────────────────────────

@app.route("/variables")
def all_variables():
    db = get_db()
    locale = g.locale
    unit_names = _unit_name_map(db, locale)
    vars = get_all_variables(db)
    rows = []
    for v in vars:
        v = _l(v, locale, "name")
        si_html = render_si_unit_html(v["si_unit"],
                     unit_url_func=lambda uid: f"/unit/{uid}",
                     unit_name_func=lambda uid: unit_names.get(uid, uid.replace("_"," ").title()),
                     locale=locale)
        rows.append(dict(v, si_html=si_html))
    return render_template("variables.html", vars=rows)


# ── All Formulas ─────────────────────────────────────

@app.route("/formulas")
def all_formulas():
    db = get_db()
    locale = g.locale
    topic = request.args.get("topic")
    if topic:
        formulas = [f for f in get_all_formulas(db) if f["topic_en"] == topic]
    else:
        formulas = get_all_formulas(db)
    formulas = [_l(f, locale, "name", "science", "branch", "topic") for f in formulas]
    return render_template("formulas.html", formulas=formulas)


# ── Export & Import ───────────────────────────────────

@app.route("/export")
def export():
    fmt = request.args.get("format", "csv")
    db = get_db()

    if fmt == "xlsx":
        buf = io.BytesIO()
        export_xlsx(db, buf)
        buf.seek(0)
        return Response(
            buf.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=formulas.xlsx"},
        )

    if fmt == "ods":
        buf = io.BytesIO()
        export_ods(db, buf)
        buf.seek(0)
        return Response(
            buf.getvalue(),
            mimetype="application/vnd.oasis.opendocument.spreadsheet",
            headers={"Content-Disposition": "attachment; filename=formulas.ods"},
        )

    # default: CSV (per-table files bundled as ZIP)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        with tempfile.TemporaryDirectory() as tmp:
            export_csv_dir(db, tmp)
            for p in Path(tmp).iterdir():
                zf.write(p, p.name)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=formulas_csv.zip"},
    )

@app.route("/import", methods=["POST"])
def import_file():
    file = request.files.get("file")
    if not file:
        return "No file uploaded", 400

    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    raw = file.stream.read()
    db = get_db()

    if ext == ".xlsx":
        buf = io.BytesIO(raw)
        counts = import_xlsx(db, buf)
    elif ext == ".ods":
        buf = io.BytesIO(raw)
        counts = import_ods(db, buf)
    elif ext == ".zip":
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                zf.extractall(tmp)
            counts = import_csv_dir(db, tmp)
    else:
        csv_str = raw.decode("utf-8")
        counts = import_csv(db, csv_str)

    rebuild_fts(db)
    return redirect("/")




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)