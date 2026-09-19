"""Presenters: display helpers + request-scoped unit tables."""

import html
import json
import math
import re

from flask import g
from markupsafe import Markup

from scifind_lib.constants import SUPERSCRIPT_DIGITS, is_slug
from scifind_lib.conversion import UnitGraph, render_equation
from scifind_lib.i18n import localise, with_subscript, wrap_symbol_in_latex
from scifind_lib.util import anchor, entity_link, request_cached
from scifind_lib.fetch import (
    fetch_compound_units,
    fetch_quantity_units,
    fetch_si_prefix_map,
    unit_is_base,
)
from scifind_lib.tree import topic_name
from scifind_lib.units import (
    compound_overwrite_cell,
    compound_slug_is_base,
    format_compound_unit_html,
    format_compound_unit_symbol,
    inject_si_prefix_nodes,
    parse_compound_unit_parts,
    prefix_name_callback,
    quantity_per_map,
    select_base_unit_with_fallback,
    si_prefix_sections,
    unit_accusative_map,
    unit_name_callback,
    unit_name_map,
    unit_quantity_map,
    unit_symbol_map,
)

def format_unit_symbol_plain(compound_unit_json, prefix_symbols=None):
    """Render a compound_unit JSON list as a compact string like m·s⁻².

    SI prefixes come from `prefix_symbols`, else fall back to ``10^{p}·``.
    """
    parts = []
    for uid, exp, prefix in parse_compound_unit_parts(compound_unit_json):
        if prefix is not None:
            key = int(prefix) if float(prefix) == int(prefix) else prefix
            sym = (prefix_symbols or {}).get(key, (prefix_symbols or {}).get(prefix))
            ptxt = str(int(prefix)) if float(prefix) == int(prefix) else str(float(prefix))
            base = f"{sym}{uid}" if sym else f"10^{{{ptxt}}}·{uid}"
        else:
            base = uid
        etxt = str(int(exp)) if float(exp) == int(exp) else str(float(exp))
        parts.append(f"{base}{etxt.translate(SUPERSCRIPT_DIGITS)}")
    return "·".join(parts)


def group_by_topic(rows, tree, locale="en-us"):
    by_topic = {}
    for row in rows:
        topic = topic_name(row["topic_id"], tree, locale) or row["topic_id"]
        by_topic.setdefault(topic, []).append(row)
    return by_topic


def render_variable_symbol(item, locale="en-us"):
    """Render the base variable symbol (without exponent) for display tables."""
    var = (localise(item.get("symbol_overwrite") or "", locale)
           or item.get("quantity_symbol")
           or item.get("quantity_id")
           or "")
    label = localise(item.get("label") or "", locale)
    return with_subscript(var, label)


_MARKER_RE = re.compile(r"\[\s*\S[^\]]*\]")


def _marker_qid(raw):
    """Normalized slug for a `[id]` / `[id|display]` marker body, or "" if invalid."""
    qid = raw.split("|", 1)[0].strip().lower().replace(" ", "_")
    return qid if is_slug(qid) else ""


def _marker_link(raw, original):
    qid, sep, display = raw.partition("|")
    qid = _marker_qid(qid)
    display = display.strip() if sep else raw.strip()
    if not qid:
        return html.escape(original)
    return anchor(f"/quantity/{qid}", display)


def expand_quantity_markers(text):
    """Replace [quantity_id] or [quantity_id|display_text] markers with <a> links."""
    segments, last = [], 0
    for m in _MARKER_RE.finditer(text):
        if m.start() > last:
            segments.append(html.escape(text[last:m.start()]))
        segments.append(_marker_link(m.group(0)[1:-1].strip(), m.group(0)))
        last = m.end()
    if last < len(text):
        segments.append(html.escape(text[last:]))
    return "".join(segments)


def marker_ids_in(text):
    """Slug ids referenced by [id] / [id|display] markers in `text`."""
    ids = set()
    for m in _MARKER_RE.finditer(text or ""):
        qid = _marker_qid(m.group(0)[1:-1].strip())
        if qid:
            ids.add(qid)
    return ids


def _cached(key, build): return request_cached(key, build)
def _names():
    loc = g.get("locale", "en-us")
    return _cached("_unit_names_" + str(loc), lambda: unit_name_map(g.db, loc))

def _symbols(): return _cached("_unit_symbols", lambda: unit_symbol_map(g.db))
def _quantities(): return _cached("_unit_quantities", lambda: unit_quantity_map(g.db))
def _quantity_pers(): return _cached("_quantity_pers", lambda: quantity_per_map(g.db))
def _accusatives(): return _cached("_unit_accusatives", lambda: unit_accusative_map(g.db))


def _prefixes(field, locale=None):
    locale = locale or g.get("locale", "en-us")
    return request_cached(f"_si_prefix_{field}_{locale}",
                          lambda: fetch_si_prefix_map(g.db, field, locale))


def _strip_html(html_text):
    return re.sub(r"<[^>]+>", "", html_text or "")


def _unit_url(names):
    return lambda uid: f"/unit/{uid}" if uid in names else None


def _html_kwargs(names, locale):
    return dict(unit_url=_unit_url(names), unit_name=unit_name_callback(names),
                unit_quantity_map=_quantities(), quantity_pers=_quantity_pers(),
                unit_accusatives=_accusatives(),
                prefix_name=prefix_name_callback(_prefixes("name", locale)))


def _compound_html(json_text, locale, *, linked=True):
    """format_compound_unit_html with the request's standard maps (links optional)."""
    names = _names()
    kw = _html_kwargs(names, locale)
    if not linked:
        kw["unit_url"] = None
    return format_compound_unit_html(json_text, locale=locale, **kw)


def unit_name_link(unit_id):
    names = _names()
    return Markup(entity_link("unit", unit_id, names[unit_id])) if unit_id in names \
        else Markup(html.escape(unit_id))


def render_compound_unit(cu_row, locale):
    """Render a base row (unit or compound_unit) as (html, latex_symbol)."""
    if not cu_row:
        return Markup(""), ""
    if cu_row["kind"] == "unit":
        return Markup(unit_name_link(cu_row["id"])), wrap_symbol_in_latex(cu_row["symbol"])
    if cu_row.get("symbol_overwrite"):
        sym_latex = wrap_symbol_in_latex(cu_row["symbol_overwrite"])
    else:
        # `format_compound_unit_symbol` wraps each part in \mathrm{} itself,
        # so pass raw symbols here to avoid double-wrapping.
        symbols = _symbols()
        active_locale = locale or g.get("locale", "en-us")
        sym_latex = format_compound_unit_symbol(
            cu_row["unit"],
            unit_symbol=lambda uid: symbols.get(uid, uid),
            prefix_symbol=lambda exp: _prefixes("symbol", active_locale).get(exp, ""),
        )
    overwrite = (localise(cu_row.get("name_overwrite") or "", locale)
                 if cu_row.get("name_overwrite") else "")
    name_html = html.escape(overwrite) if overwrite else _compound_html(cu_row["unit"], locale)
    return Markup(name_html), sym_latex


def _format_system_label(system, is_base, tr):
    if not system:
        return tr("unit.system_any")
    key = tr(f"unit.system_{system.lower()}")
    return tr("unit.system_base").format(system=key) if is_base else key


def _row_is_base(conn, row_id, kind):
    """True if `row_id` is the base row for its quantity."""
    if not row_id:
        return False
    return unit_is_base(conn, row_id) if kind == "unit" else compound_slug_is_base(conn, row_id)


def _make_entry(entry_id, symbol_latex, name_html, label, system, system_raw=None):
    return {"id": entry_id, "symbol_latex": symbol_latex, "name_html": name_html, "label": label,
            "system": system, "system_raw": system_raw}


def _sys_sort_key(raw, selected):
    """(rank, name): selected system first, NULL last, rest alphabetical."""
    if raw == selected:
        return (0, "")
    if raw is None:
        return (2, "")
    return (1, str(raw).lower())


def _num(value):
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _affine_sort_key(graph, entry_id):
    """Direct additive term: offset + constant_shift * C (0 for compounds/synthetic)."""
    row = graph.unit_rows.get(entry_id)
    if not row or (entry_id or "").startswith("si_"):
        return 0.0
    off, shift = _num(row.get("offset")), _num(row.get("constant_shift"))
    if not shift:
        return off
    c = graph._constant_value(row.get("constant_id"))
    return off + shift if c is None or not math.isfinite(c) else off + shift * c


def _mult_sort_key(graph, entry_id):
    """Multiplicative root value; non-finite/unreachable sorts last."""
    v = None
    try:
        if entry_id in graph.unit_rows:
            v = graph.root_value(entry_id)
        elif entry_id in graph.compound_rows:
            v = graph.compound_parts_value(entry_id)
    except (TypeError, ValueError, ArithmeticError):
        v = None
    return v if isinstance(v, (int, float)) and math.isfinite(v) else math.inf


def _attach_sort_keys(graph, rows, selected):
    """Annotate rows with s_* sort keys; returns the rows sorted by the default order."""
    for r in rows:
        rank, alpha = _sys_sort_key(r.get("system_raw"), selected)
        r["s_sys"] = rank
        r["s_sysname"] = alpha
        r["s_aff"] = _affine_sort_key(graph, r.get("id"))
        r["s_val"] = _mult_sort_key(graph, r.get("id"))
        r["s_name"] = str(r.get("label") or r.get("id") or "").casefold()
    rows.sort(key=lambda r: (r["s_sys"], r["s_sysname"], r["s_aff"], r["s_val"], r["s_name"]))
    return rows


def _si_prefix_entries(conn, quantity_id, base, locale, tr):
    """Prefixed-form entries derived from the SI prefix table (or None)."""
    si_prefixes = si_prefix_sections(
        conn, quantity_id, locale, unit_names=_names(), unit_syms=_symbols(),
        prefix_names=_prefixes("name", locale), prefix_syms=_prefixes("symbol", locale),
        quantity_pers=_quantity_pers(), unit_accusatives=_accusatives())
    if not si_prefixes:
        return [], None
    base_id = base["id"] if base else None
    any_label = _format_system_label(None, False, tr)
    entries = [_make_entry(r["payload_id"], Markup(r["symbol_latex"]), Markup(r["name"]),
                           r.get("label") or r["name"], any_label, None)
               for section in si_prefixes.values() for r in section["rows"]
               if r["payload_id"] != base_id]
    return entries, si_prefixes


def _base_entry(conn, base, locale, tr):
    if not base:
        return None
    label_json = json.dumps([{"unit": base["id"], "exponent": 1}]) if base["kind"] == "unit" else base["unit"]
    default_html, default_sym = render_compound_unit(base, locale)
    names = _names()
    return _make_entry(base["id"], default_sym, default_html,
        format_compound_unit_html(label_json, locale=locale, **_html_kwargs(names, locale)),
        _format_system_label(base.get("system"), _row_is_base(conn, base["id"], base["kind"]), tr),
        base.get("system"))


def _plain_unit_entries(conn, quantity_id, base, locale, tr):
    base_id = base["id"] if base and base["kind"] == "unit" else None
    entries = []
    for unit_row in map(dict, fetch_quantity_units(conn, quantity_id)):
        if unit_row["id"] == base_id:
            continue
        entries.append(_make_entry(unit_row["id"], Markup(wrap_symbol_in_latex(unit_row["symbol"])),
            unit_name_link(unit_row["id"]),
            localise(unit_row.get("name"), locale) or unit_row["id"],
            _format_system_label(unit_row.get("system"), _row_is_base(conn, unit_row["id"], "unit"), tr),
            unit_row.get("system")))
    return entries


def _compound_name_html(cu_row, unit_html, locale):
    """(name_html, label): overwrite cell keeps links; label is overwrite only."""
    overwrite_json = cu_row.get("name_overwrite")
    override_text = localise(overwrite_json, locale) if overwrite_json else ""
    if override_text:
        return compound_overwrite_cell(override_text, cu_row["unit"], locale, unit_names=_names(),
            unit_quantity_map=_quantities(), quantity_pers=_quantity_pers(),
            unit_accusatives=_accusatives(), prefix_names=_prefixes("name", locale)), override_text
    return unit_html, format_compound_unit_html(
        cu_row["unit"], locale=locale, **_html_kwargs(_names(), locale))


def _compound_entries(conn, quantity_id, base, locale, tr, skip_ids):
    base_id = base["id"] if base and base["kind"] == "compound_unit" else None
    entries = []
    for row in fetch_compound_units(conn, quantity_id):
        cu_row = dict(row)
        if cu_row["id"] in skip_ids or cu_row["id"] == base_id:
            continue
        unit_html, unit_sym = render_compound_unit(cu_row, locale)
        cu_name_html, cu_label = _compound_name_html(cu_row, unit_html, locale)
        entries.append(_make_entry(cu_row["id"], unit_sym, cu_name_html, cu_label,
            _format_system_label(cu_row.get("system"), _row_is_base(conn, cu_row["id"], "compound_unit"), tr),
            cu_row.get("system")))
    return entries


def quantity_units_table(conn, quantity_id, system, ref_unit_id=None, *, tr):
    """Unit-table payload for quantity/unit pages."""
    return _quantity_units_table_uncached(conn, quantity_id, system, ref_unit_id, tr=tr)


def _column_for_graph(graph, ref_id, row_ids):
    return {rid: render_equation(graph, rid, ref_id) for rid in dict.fromkeys(row_ids) if rid}


def units_column(conn, quantity_id, ref_id, row_ids, locale):
    """{row_id: conversion LaTeX vs ref_id} for a single reference column."""
    graph = UnitGraph(conn, quantity_id, locale)
    inject_si_prefix_nodes(graph, conn, quantity_id, locale, unit_syms=_symbols())
    return _column_for_graph(graph, ref_id, row_ids)


def _quantity_units_table_uncached(conn, quantity_id, system, ref_unit_id=None, *, tr):
    locale = g.locale
    base = select_base_unit_with_fallback(conn, quantity_id, system)

    graph = UnitGraph(conn, quantity_id, locale)
    inject_si_prefix_nodes(graph, conn, quantity_id, locale,
                           unit_syms=_symbols())

    default_id = base["id"] if base else None
    prefix_entries, si_prefixes = _si_prefix_entries(conn, quantity_id, base, locale, tr)
    base_entry = _base_entry(conn, base, locale, tr)
    entries = [*prefix_entries,
               *([base_entry] if base_entry else []),
               *_plain_unit_entries(conn, quantity_id, base, locale, tr)]

    # Skip compound rows already shown as SI prefix entries (hectare = hm²,
    # etc.) — they only belong in the prefix table.
    prefix_rows = [r for section in (si_prefixes or {}).values() for r in section["rows"]]
    entries.extend(_compound_entries(
        conn, quantity_id, base, locale, tr, {r["id"] for r in prefix_rows}))

    # Synthetic base headers have no graph node; alias them to the base id.
    in_graph = lambda pid: pid in graph.unit_rows or pid in graph.compound_rows
    base_alias = {r["payload_id"]: default_id for r in prefix_rows
                  if r.get("system_key") == "detail.si_base"
                  and not in_graph(r["payload_id"]) and default_id}
    ref_of = lambda pid: base_alias.get(pid, pid)

    # Anything shown in the SI table stays out of the main table, comparing by
    # the aliased ids the SI table actually renders. When this empties the main
    # table the template hides it and headers the SI table instead.
    si_payload_ids = {ref_of(r["payload_id"]) for r in prefix_rows}
    si_payload_ids |= {r["payload_id"] for r in prefix_rows}

    ref_id = ref_unit_id if ref_unit_id and any(entry["id"] == ref_unit_id for entry in entries) else default_id
    ref_label = next((_strip_html(str(entry["label"])) for entry in entries if entry["id"] == ref_id), "")

    units_rows = [{
        "id": entry["id"] or "", "symbol_latex": entry["symbol_latex"], "name_html": entry["name_html"],
        "label": _strip_html(entry["label"]) if entry.get("label") else (entry["id"] or ""),
        "system": entry["system"], "system_raw": entry.get("system_raw"),
        "is_ref": entry["id"] == ref_id,
    } for entry in entries
        if not (entry["id"] or "").startswith("si_") and entry["id"] not in si_payload_ids]

    si_prefix_sections = [{
        "component": section["component"], "label": section["label"],
        "payload": [{
            "id": ref_of(r["payload_id"]), "exp": r.get("exp"), "symbol_latex": Markup(r["symbol_latex"]),
            "name": Markup(r["name"]), "label": r.get("label") or _strip_html(str(r.get("name") or "")),
            "system_key": r.get("system_key"), "system_raw": "SI", "link_unit_id": r.get("link_unit_id"),
            "is_ref": ref_of(r["payload_id"]) == ref_id, "collapsed": bool(r.get("collapsed")),
        } for r in section["rows"]],
    } for section in (si_prefixes or {}).values()]
    column = _column_for_graph(graph, ref_id,
        [r["id"] for r in units_rows] + [r["id"] for s in si_prefix_sections for r in s["payload"]])
    for r in units_rows:
        r["latex"] = column.get(r["id"])
    for section in si_prefix_sections:
        for r in section["payload"]:
            r["latex"] = column.get(r["id"])
    _attach_sort_keys(graph, units_rows, system)
    for section in si_prefix_sections:
        _attach_sort_keys(graph, section["payload"], system)
    si_payload = [row for section in si_prefix_sections for row in section["payload"]]
    _strip = lambda row: {k: v for k, v in row.items() if not k.startswith(("s_", "system_raw"))}
    payload = {"ref": ref_id or "", "ref_label": ref_label, "quantity": quantity_id,
               "entries": [_strip(row) for row in units_rows],
               "si_entries": [_strip(row) for row in si_payload]}
    return {"units": units_rows, "payload": payload,
            "si_prefixes": si_payload, "si_prefix_sections": si_prefix_sections}
