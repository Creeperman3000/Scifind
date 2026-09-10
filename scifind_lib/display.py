"""Presenters: display helpers + request-scoped unit tables."""

import html
import json
import re

from flask import g
from markupsafe import Markup

from scifind_lib.constants import SUPERSCRIPT_DIGITS, is_slug
from scifind_lib.conversion import UnitGraph, precompute_latex_map
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
    parts = parse_compound_unit(compound_unit_json)
    if not parts:
        return ""
    return "·".join(f"{uid}{str(exp).translate(SUPERSCRIPT_DIGITS)}"
                    for uid, exp in parts)


def group_by_topic(rows):
    """Group `rows` by their localised topic name, preserving insertion order."""
    by_topic = {}
    for row in rows:
        topic = topic_name(row["topic_id"]) or "General"
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


def expand_quantity_markers(text):
    """Replace [quantity_id] or [quantity_id|display_text] markers with <a> links."""
    placeholder_re = re.compile(r"\[\s*\S[^\]]*\]")
    segments = []
    last = 0
    for m in placeholder_re.finditer(text):
        if m.start() > last:
            segments.append(html.escape(text[last:m.start()]))
        raw = m.group(0)[1:-1].strip()
        if "|" in raw:
            qid, display = raw.split("|", 1)
        else:
            qid = display = raw
        qid = qid.strip().lower().replace(" ", "_")
        display = display.strip()
        if not is_slug(qid):
            segments.append(html.escape(m.group(0)))
        else:
            segments.append(
                f'<a href="/quantity/{html.escape(qid)}">'
                f"{html.escape(display)}</a>"
            )
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
    return (
        f'<a href="/{kind}/{html.escape(ent_id)}">'
        f"{html.escape(display or ent_id)}</a>"
    )


def _get_db():
    return g.db


def _cached(key, loader):
    if key not in g:
        setattr(g, key, loader())
    return getattr(g, key)


def _get_unit_name_map():
    return _cached(
        "unit_name_map",
        lambda: unit_name_map(_get_db(), g.get("locale", "en-us")),
    )


def _get_unit_symbol_map():
    return _cached("unit_symbol_map", lambda: unit_symbol_map(_get_db()))


def _get_unit_quantity_map():
    return _cached("unit_quantity_map", lambda: unit_quantity_map(_get_db()))


def _get_prefix_map(field, locale=None):
    return _cached(
        f"prefix_{field}_map",
        lambda: fetch_si_prefix_map(
            _get_db(), field, locale or g.get("locale", "en-us")),
    )


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "")


def _unit_name():
    """Request-scoped unit-name lookup with first-letter capitalisation."""
    return unit_name_callback(_get_unit_name_map())


def _prefix_name(locale):
    """Request-scoped SI-prefix-name lookup."""
    return prefix_name_callback(_get_prefix_map("name", locale))


def unit_name_link(unit_id):
    names = _get_unit_name_map()
    if unit_id in names:
        return Markup(build_entity_link("unit", unit_id, names[unit_id]))
    return Markup(html.escape(unit_id.replace("_", " ").title()))


def _render_unit_html(unit_json, locale):
    names = _get_unit_name_map()
    return format_compound_unit_html(
        unit_json,
        unit_url=lambda uid: f"/unit/{uid}" if uid in names else None,
        unit_name=unit_name_callback(names),
        locale=locale,
        unit_quantity_map=_get_unit_quantity_map(),
        prefix_name=_prefix_name(locale),
    )


def _render_unit_symbol(unit_json, locale=None):
    symbols = _get_unit_symbol_map()
    loc = locale or g.get("locale", "en-us")
    # `format_compound_unit_symbol` wraps each part in \\mathrm{} itself,
    # so pass raw symbols here to avoid double-wrapping.
    return format_compound_unit_symbol(
        unit_json,
        unit_symbol=lambda uid: symbols.get(uid, uid),
        prefix_symbol=lambda exp: _get_prefix_map("symbol", loc).get(exp, ""),
    )


def render_compound_unit(cu_row, locale):
    """Render a base row (unit or compound_unit) as (html, latex_symbol)."""
    if not cu_row:
        return Markup(""), ""
    if cu_row["kind"] == "unit":
        return Markup(unit_name_link(cu_row["id"])), wrap_symbol_in_latex(cu_row["symbol"])
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


def _format_system_label(system, is_base, tr):
    if not system:
        return tr("unit.system_any")
    if is_base:
        return tr("unit.system_base").format(system=tr(f"unit.system_{system.lower()}"))
    return tr(f"unit.system_{system.lower()}")


def _row_is_base(conn, row_id, system, kind):
    """True if `row_id` is the base row for its quantity, ignoring the `system` filter."""
    if not row_id:
        return False
    if kind == "unit":
        return unit_is_base(conn, row_id)
    return compound_slug_is_base(conn, row_id)


def _entry_latex_by_ref(latex_map, entry_id):
    return {rid: latex_map.get(entry_id, {}).get(rid) for rid in latex_map}


def _si_prefix_entries(conn, quantity_id, base, locale, tr):
    """Prefixed-form entries derived from the SI prefix table (or None)."""
    si_prefixes = si_prefix_sections(
        conn, quantity_id, locale,
        unit_names=_get_unit_name_map(),
        unit_syms=_get_unit_symbol_map(),
        prefix_names=_get_prefix_map("name", locale),
        prefix_syms=_get_prefix_map("symbol", locale),
    )
    if not si_prefixes:
        return [], None
    base_entry_id = base["id"] if base else None
    entries = [
        {
            "id": r["payload_id"],
            "symbol_latex": Markup(r["symbol_latex"]),
            "name_html": Markup(r["name"]),
            "label": r["name"],
            "system": _format_system_label(None, False, tr),
        }
        for section in si_prefixes.values()
        for r in section["rows"]
        if not (base_entry_id and r["payload_id"] == base_entry_id)
    ]
    return entries, si_prefixes


def _base_entry(conn, base, system, locale, tr):
    if not base:
        return None
    label_json = (json.dumps([{"unit": base["id"], "exponent": 1}])
                  if base["kind"] == "unit" else base["unit"])
    default_html, default_sym = render_compound_unit(base, locale)
    return (
        {
            "id": base["id"],
            "symbol_latex": default_sym,
            "name_html": default_html,
            "label": format_compound_unit_html(
                label_json, locale=locale,
                unit_name=_unit_name(),
                prefix_name=_prefix_name(locale)),
            "system": _format_system_label(
                base["system"] if base else "SI",
                _row_is_base(conn, base["id"], system, base["kind"]), tr),
        },
        default_html,
        default_sym,
    )


def _plain_unit_entries(conn, quantity_id, base, system, locale, tr):
    entries = []
    for eu in (dict(u) for u in fetch_quantity_units(conn, quantity_id)):
        if base and base["kind"] == "unit" and eu["id"] == base["id"]:
            continue
        eu_system = eu.get("system") or None
        entries.append({
            "id": eu["id"],
            "symbol_latex": Markup(wrap_symbol_in_latex(eu["symbol"])),
            "name_html": unit_name_link(eu["id"]),
            "label": (localise(eu.get("name"), locale)
                      or eu["id"].replace("_", " ")),
            "system": _format_system_label(
                eu_system, _row_is_base(conn, eu["id"], system, "unit"), tr),
        })
    return entries


def _compound_name_html(cu_row, unit_html, locale):
    """(name_html, label) showing the parts-derived name unless duplicated."""
    no_json = cu_row.get("name_overwrite")
    if no_json and localise(no_json, locale):
        parts_name = format_compound_unit_html(
            cu_row["unit"], locale=locale,
            unit_quantity_map=_get_unit_quantity_map(),
            unit_name=_unit_name(),
            prefix_name=_prefix_name(locale))
        parts_text = _strip_html(parts_name).strip()
        override_text = localise(no_json, locale)
        if parts_text and parts_text.lower() != override_text.lower():
            return (Markup(f"{override_text} ({parts_text})"),
                    f"{override_text} ({parts_text})")
        return Markup(override_text), override_text
    return unit_html, format_compound_unit_html(
        cu_row["unit"], locale=locale,
        unit_name=_unit_name(),
        prefix_name=_prefix_name(locale))


def _compound_entries(conn, quantity_id, base, system, locale, tr, skip_ids):
    entries = []
    for cu_row in fetch_compound_units(conn, quantity_id):
        if cu_row["id"] in skip_ids:
            continue
        cu_row = dict(cu_row)
        if base and base["kind"] == "compound_unit" and cu_row["id"] == base["id"]:
            continue
        unit_html, unit_sym = render_compound_unit(cu_row, locale)
        cu_name_html, cu_label = _compound_name_html(cu_row, unit_html, locale)
        entries.append({
            "id": cu_row["id"],
            "symbol_latex": unit_sym,
            "name_html": cu_name_html,
            "label": cu_label,
            "system": _format_system_label(
                cu_row.get("system") or None,
                _row_is_base(conn, cu_row["id"], system, "compound_unit"), tr),
        })
    return entries


def quantity_units_table(conn, quantity_id, system, ref_unit_id=None, *, tr):
    """Unit-table rows shared by /quantity/<id> and /unit/<id>."""
    locale = g.locale
    base = select_base_unit_with_fallback(conn, quantity_id, system)

    graph = UnitGraph(conn, quantity_id)
    inject_si_prefix_nodes(graph, conn, quantity_id, locale, system,
                           unit_syms=_get_unit_symbol_map())
    latex_map = precompute_latex_map(graph)

    default_id = base["id"] if base else None

    prefix_entries, si_prefixes = _si_prefix_entries(conn, quantity_id, base, locale, tr)
    entries = list(prefix_entries)
    base_result = _base_entry(conn, base, system, locale, tr)
    if base_result:
        entries.append(base_result[0])
    entries.extend(_plain_unit_entries(conn, quantity_id, base, system, locale, tr))

    # Skip compound rows already shown as SI prefix entries (hectare = hm²,
    # etc.) — they only belong in the prefix table.
    si_prefix_entry_ids = set()
    si_payload_ids = set()
    if si_prefixes:
        for section in si_prefixes.values():
            for r in section["rows"]:
                si_prefix_entry_ids.add(r["id"])
                si_payload_ids.add(r["payload_id"])
    entries.extend(_compound_entries(
        conn, quantity_id, base, system, locale, tr, si_prefix_entry_ids))

    if ref_unit_id and any(e["id"] == ref_unit_id for e in entries):
        ref_id = ref_unit_id
    else:
        ref_id = default_id

    ref_label = next(
        (_strip_html(str(e["label"])) for e in entries if e["id"] == ref_id),
        "",
    )

    units_rows = []
    for e in entries:
        if (e["id"] or "").startswith("si_"):
            continue
        # DB-overwritten SI prefix entries are already in the prefix table; skip.
        if e["id"] in si_payload_ids:
            continue
        plain_label = _strip_html(e["label"]) if e.get("label") else (e["id"] or "").replace("_", " ")
        units_rows.append({
            "id": e["id"] or "",
            "symbol_latex": e["symbol_latex"],
            "name_html": e["name_html"],
            "label": plain_label,
            "system": e["system"],
            "is_ref": e["id"] == ref_id,
            "latex_by_ref": _entry_latex_by_ref(latex_map, e["id"]),
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
                    "latex_by_ref": _entry_latex_by_ref(latex_map, pid),
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
