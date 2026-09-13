"""Presenters: display helpers + request-scoped unit tables."""

import html
import json
import re

from flask import g
from markupsafe import Markup

from scifind_lib.constants import SUPERSCRIPT_DIGITS, is_slug
from scifind_lib.conversion import UnitGraph, precompute_latex_map
from scifind_lib.db import cached_process, db_cache_key
from scifind_lib.i18n import localise, with_subscript, wrap_symbol_in_latex
from scifind_lib.fetch import (
    fetch_compound_units,
    fetch_quantity_units,
    fetch_si_prefix_map,
    unit_is_base,
)
from scifind_lib.tree import topic_name
from scifind_lib.units import (
    compound_slug_is_base,
    format_compound_unit_html,
    format_compound_unit_symbol,
    inject_si_prefix_nodes,
    parse_compound_unit,
    prefix_name_callback,
    select_base_unit_with_fallback,
    si_prefix_sections,
    unit_name_callback,
    unit_name_map,
    unit_quantity_map,
    unit_symbol_map,
)

def format_unit_symbol_plain(compound_unit_json):
    """Render a compound_unit JSON list as a compact string like m·s⁻²."""
    return "·".join(f"{uid}{str(exp).translate(SUPERSCRIPT_DIGITS)}"
                    for uid, exp in parse_compound_unit(compound_unit_json))


def group_by_topic(rows, tree, locale="en-us"):
    """Group `rows` by their localised topic name, preserving insertion order."""
    by_topic = {}
    for row in rows:
        topic = topic_name(row["topic_id"], tree, locale) or "General"
        by_topic.setdefault(topic, []).append(row)
    return by_topic


def render_variable_symbol(item, locale="en-us"):
    """Render the base variable symbol (without exponent) for display tables."""
    var = (localise(item.get("symbol_overwrite") or "", locale)
           or item.get("quantity_symbol")
           or item.get("quantity_id")
           or "?")
    label = localise(item.get("label") or "", locale)
    return with_subscript(var, label)


_MARKER_RE = re.compile(r"\[\s*\S[^\]]*\]")


def _marker_link(raw, original):
    qid, sep, display = raw.partition("|")
    qid = qid.strip().lower().replace(" ", "_")
    display = display.strip() if sep else raw.strip()
    if not is_slug(qid):
        return html.escape(original)
    return f'<a href="/quantity/{html.escape(qid)}">{html.escape(display)}</a>'


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


_ENTITY_LINK_KINDS = frozenset({"formula", "quantity", "unit", "constant"})
_ENTITY_LINK_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")


def build_entity_link(kind, ent_id, display):
    """Render ``<a href="/<kind>/<id>">display</a>``; bad ids render as escaped text only."""
    if kind not in _ENTITY_LINK_KINDS or not isinstance(ent_id, str) \
            or not _ENTITY_LINK_ID_RE.fullmatch(ent_id):
        return html.escape(display or "")
    return f'<a href="/{kind}/{html.escape(ent_id)}">{html.escape(display or ent_id)}</a>'


def _cached(key, loader):
    if key not in g:
        setattr(g, key, loader())
    return getattr(g, key)


def _names():
    return _cached("unit_name_map",
                   lambda: unit_name_map(g.db, g.get("locale", "en-us")))


def _symbols():
    return _cached("unit_symbol_map", lambda: unit_symbol_map(g.db))


def _quantities():
    return _cached("unit_quantity_map", lambda: unit_quantity_map(g.db))


def _prefixes(field, locale=None):
    return _cached(f"prefix_{field}_map",
                   lambda: fetch_si_prefix_map(
                       g.db, field, locale or g.get("locale", "en-us")))


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "")


def _unit_name():
    """Request-scoped unit-name lookup with first-letter capitalisation."""
    return unit_name_callback(_names())


def _prefix_name(locale):
    """Request-scoped SI-prefix-name lookup."""
    return prefix_name_callback(_prefixes("name", locale))


def unit_name_link(unit_id):
    names = _names()
    if unit_id in names:
        return Markup(build_entity_link("unit", unit_id, names[unit_id]))
    return Markup(html.escape(unit_id.replace("_", " ").title()))


def _render_unit_html(unit_json, locale):
    names = _names()
    return format_compound_unit_html(
        unit_json,
        unit_url=lambda uid: f"/unit/{uid}" if uid in names else None,
        unit_name=unit_name_callback(names),
        locale=locale,
        unit_quantity_map=_quantities(),
        prefix_name=_prefix_name(locale),
    )


def _render_unit_symbol(unit_json, locale=None):
    symbols = _symbols()
    loc = locale or g.get("locale", "en-us")
    # `format_compound_unit_symbol` wraps each part in \\mathrm{} itself,
    # so pass raw symbols here to avoid double-wrapping.
    return format_compound_unit_symbol(
        unit_json,
        unit_symbol=lambda uid: symbols.get(uid, uid),
        prefix_symbol=lambda exp: _prefixes("symbol", loc).get(exp, ""),
    )


def render_compound_unit(cu_row, locale):
    """Render a base row (unit or compound_unit) as (html, latex_symbol)."""
    if not cu_row:
        return Markup(""), ""
    if cu_row["kind"] == "unit":
        return Markup(unit_name_link(cu_row["id"])), wrap_symbol_in_latex(cu_row["symbol"])
    sym_latex = (wrap_symbol_in_latex(cu_row["symbol_overwrite"])
                 if cu_row.get("symbol_overwrite")
                 else _render_unit_symbol(cu_row["unit"], locale))
    name_html = (localise(cu_row["name_overwrite"], locale)
                 if cu_row.get("name_overwrite")
                 else _render_unit_html(cu_row["unit"], locale))
    return Markup(name_html), sym_latex


def _format_system_label(system, is_base, tr):
    if not system:
        return tr("unit.system_any")
    if is_base:
        return tr("unit.system_base").format(system=tr(f"unit.system_{system.lower()}"))
    return tr(f"unit.system_{system.lower()}")


def _row_is_base(conn, row_id, kind):
    """True if `row_id` is the base row for its quantity."""
    if not row_id:
        return False
    return unit_is_base(conn, row_id) if kind == "unit" else compound_slug_is_base(conn, row_id)


def _make_entry(eid, symbol_latex, name_html, label, system):
    return {"id": eid, "symbol_latex": symbol_latex, "name_html": name_html,
            "label": label, "system": system}


def _si_prefix_entries(conn, quantity_id, base, locale, tr):
    """Prefixed-form entries derived from the SI prefix table (or None)."""
    si_prefixes = si_prefix_sections(
        conn, quantity_id, locale, unit_names=_names(), unit_syms=_symbols(),
        prefix_names=_prefixes("name", locale), prefix_syms=_prefixes("symbol", locale),
    )
    if not si_prefixes:
        return [], None
    base_id = base["id"] if base else None
    any_label = _format_system_label(None, False, tr)
    entries = [_make_entry(r["payload_id"], Markup(r["symbol_latex"]),
                           Markup(r["name"]), r["name"], any_label)
               for section in si_prefixes.values() for r in section["rows"]
               if r["payload_id"] != base_id]
    return entries, si_prefixes


def _base_entry(conn, base, locale, tr):
    if not base:
        return None
    label_json = (json.dumps([{"unit": base["id"], "exponent": 1}])
                  if base["kind"] == "unit" else base["unit"])
    default_html, default_sym = render_compound_unit(base, locale)
    return _make_entry(
        base["id"], default_sym, default_html,
        format_compound_unit_html(label_json, locale=locale,
                                  unit_name=_unit_name(), prefix_name=_prefix_name(locale)),
        _format_system_label(base.get("system"), _row_is_base(conn, base["id"], base["kind"]), tr),
    )


def _plain_unit_entries(conn, quantity_id, base, locale, tr):
    base_id = base["id"] if base and base["kind"] == "unit" else None
    entries = []
    for eu in map(dict, fetch_quantity_units(conn, quantity_id)):
        if eu["id"] == base_id:
            continue
        entries.append(_make_entry(
            eu["id"], Markup(wrap_symbol_in_latex(eu["symbol"])), unit_name_link(eu["id"]),
            localise(eu.get("name"), locale) or eu["id"].replace("_", " "),
            _format_system_label(eu.get("system"), _row_is_base(conn, eu["id"], "unit"), tr),
        ))
    return entries


def _compound_name_html(cu_row, unit_html, locale):
    """(name_html, label) showing the parts-derived name unless duplicated."""
    no_json = cu_row.get("name_overwrite")
    override_text = localise(no_json, locale) if no_json else ""
    if override_text:
        parts_text = _strip_html(format_compound_unit_html(
            cu_row["unit"], locale=locale, unit_quantity_map=_quantities(),
            unit_name=_unit_name(), prefix_name=_prefix_name(locale))).strip()
        if parts_text and parts_text.lower() != override_text.lower():
            combined = f"{override_text} ({parts_text})"
            return Markup(combined), combined
        return Markup(override_text), override_text
    return unit_html, format_compound_unit_html(
        cu_row["unit"], locale=locale,
        unit_name=_unit_name(), prefix_name=_prefix_name(locale))


def _compound_entries(conn, quantity_id, base, locale, tr, skip_ids):
    base_id = base["id"] if base and base["kind"] == "compound_unit" else None
    entries = []
    for _row in fetch_compound_units(conn, quantity_id):
        cu_row = dict(_row)
        if cu_row["id"] in skip_ids or cu_row["id"] == base_id:
            continue
        unit_html, unit_sym = render_compound_unit(cu_row, locale)
        cu_name_html, cu_label = _compound_name_html(cu_row, unit_html, locale)
        entries.append(_make_entry(
            cu_row["id"], unit_sym, cu_name_html, cu_label,
            _format_system_label(cu_row.get("system"),
                                 _row_is_base(conn, cu_row["id"], "compound_unit"), tr),
        ))
    return entries


def quantity_units_table(conn, quantity_id, system, ref_unit_id=None, *, tr):
    """Unit-table payload for quantity/unit pages."""
    locale = g.locale
    if db_cache_key() is None:
        return _quantity_units_table_uncached(conn, quantity_id, system, ref_unit_id, tr=tr)
    return dict(cached_process(("units_table", quantity_id, system, locale, ref_unit_id),
        lambda: _quantity_units_table_uncached(conn, quantity_id, system, ref_unit_id, tr=tr)))


def _quantity_units_table_uncached(conn, quantity_id, system, ref_unit_id=None, *, tr):
    locale = g.locale
    base = select_base_unit_with_fallback(conn, quantity_id, system)

    graph = UnitGraph(conn, quantity_id)
    inject_si_prefix_nodes(graph, conn, quantity_id, locale, system,
                           unit_syms=_symbols())
    latex_map = precompute_latex_map(graph)
    latex_by_ref = lambda eid: {rid: latex_map.get(eid, {}).get(rid) for rid in latex_map}

    default_id = base["id"] if base else None
    prefix_entries, si_prefixes = _si_prefix_entries(conn, quantity_id, base, locale, tr)
    base_entry = _base_entry(conn, base, locale, tr)
    entries = [*prefix_entries,
               *([base_entry] if base_entry else []),
               *_plain_unit_entries(conn, quantity_id, base, locale, tr)]

    # Skip compound rows already shown as SI prefix entries (hectare = hm²,
    # etc.) — they only belong in the prefix table.
    rows = [r for section in (si_prefixes or {}).values() for r in section["rows"]]
    entries.extend(_compound_entries(
        conn, quantity_id, base, locale, tr, {r["id"] for r in rows}))
    si_payload_ids = {r["payload_id"] for r in rows}

    ref_id = ref_unit_id if ref_unit_id and any(e["id"] == ref_unit_id for e in entries) else default_id
    ref_label = next((_strip_html(str(e["label"])) for e in entries if e["id"] == ref_id), "")

    units_rows = [{
        "id": e["id"] or "",
        "symbol_latex": e["symbol_latex"],
        "name_html": e["name_html"],
        "label": _strip_html(e["label"]) if e.get("label") else (e["id"] or "").replace("_", " "),
        "system": e["system"],
        "is_ref": e["id"] == ref_id,
        "latex_by_ref": latex_by_ref(e["id"]),
    } for e in entries
        if not (e["id"] or "").startswith("si_") and e["id"] not in si_payload_ids]

    si_prefix_sections = [{
        "component": section["component"],
        "label": section["label"],
        "payload": [{
            "id": r["payload_id"],
            "symbol_latex": Markup(r["symbol_latex"]),
            "name": r["name"],
            "system_key": r.get("system_key"),
            "link_unit_id": r.get("link_unit_id"),
            "value_latex": r.get("value_latex", ""),
            "is_ref": r["payload_id"] == ref_id,
            "collapsed": bool(r.get("collapsed")),
            "latex_by_ref": latex_by_ref(r["payload_id"]),
        } for r in section["rows"]],
    } for section in (si_prefixes or {}).values()]
    si_payload = [row for section in si_prefix_sections for row in section["payload"]]
    payload = {"ref": ref_id or "", "ref_label": ref_label,
               "entries": units_rows, "si_entries": si_payload}
    return {"units": units_rows, "payload": payload,
            "si_prefixes": si_payload, "si_prefix_sections": si_prefix_sections}
