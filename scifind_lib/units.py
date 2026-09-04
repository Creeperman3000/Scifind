"""unit and compound_unit parsing, base-unit resolution, HTML/LaTeX rendering."""

import html
import json
import logging

from scifind_lib.i18n import (
    unit_exponent_word,
    locale_accusative_names,
    locale_quantities_special,
    locale_unit_words,
    localise,
)

logger = logging.getLogger(__name__)


def parse_compound_unit(json_text):
    """Parse compound_unit JSON into [(unit_id, exponent)] (or [] on NULL / unparseable).

    The `prefix` field is dropped; use `parse_compound_unit_parts` when a
    part's SI prefix is needed (symbol/name/conversion rendering).
    """
    parts = parse_compound_unit_parts(json_text)
    return [(uid, exp) for uid, exp, _prefix in parts]


def parse_compound_unit_parts(json_text):
    """Parse compound_unit JSON into [(unit_id, exponent, prefix_or_None)].

    `prefix_or_None` is the int exponent into `si_prefix` (e.g. -2 for
    centi, 3 for kilo) or None when the part has no prefix. Returns []
    on NULL / unparseable JSON.
    """
    if not json_text:
        return []
    try:
        parsed = json.loads(json_text)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("parse_compound_unit_parts: bad JSON: %s", exc)
        return []
    if not isinstance(parsed, list):
        return []
    out = []
    for entry in parsed:
        if not isinstance(entry, dict):
            return []
        unit_id = entry.get("unit")
        exp = entry.get("exponent")
        if not isinstance(unit_id, str) or not isinstance(exp, (int, float)):
            return []
        prefix = entry.get("prefix")
        if prefix is not None:
            try:
                prefix = int(prefix)
            except (TypeError, ValueError):
                prefix = None
        out.append((unit_id, exp, prefix))
    return out


def split_numerator_denominator(items):
    return (
        [item for item in items if item[1] >= 0],
        [(item[0], -item[1], item[2]) if len(item) == 3 else (item[0], -item[1])
         for item in items if item[1] < 0],
    )


def format_compound_unit_html(
    json_text, unit_url=None, unit_name=None, locale="en-us", unit_quantity_map=None,
    prefix_name=None,
):
    """Render compound_unit JSON as HTML with optional unit links.

    `prefix_name`: optional callable(prefix_exp) -> localized prefix name
    (e.g. "Centi"), used to build prefixed part names like "centimetre".
    """
    parts = parse_compound_unit_parts(json_text)
    if not parts:
        return ""
    words = locale_unit_words(locale)
    numerators, denominators = split_numerator_denominator(parts)
    num_html = _render_unit_group(numerators, unit_url, unit_name, locale,
                                  prefix_name=prefix_name, raw_3=True)
    if not denominators:
        return num_html
    per_word = words["per"]
    use_special = False
    if unit_quantity_map:
        special = locale_quantities_special(locale)
        for uid, _e, _p in denominators:
            if unit_quantity_map.get(uid) in special:
                per_word = words.get("perSpecial", per_word)
                use_special = True
                break
    den_html = _render_unit_group(denominators, unit_url, unit_name, locale,
                                  use_special_exponents=use_special,
                                  prefix_name=prefix_name, raw_3=True)
    if not num_html:
        return f"{words['reciprocal']} {den_html}"
    return f"{num_html} {per_word} {den_html}"


def format_compound_unit_symbol(json_text, unit_symbol=None, prefix_symbol=None):
    """Render compound_unit JSON as a LaTeX symbol expression.

    `prefix_symbol`: optional callable(prefix_exp) -> LaTeX prefix symbol
    (e.g. "\\mathrm{c}"), prepended to the unit symbol for prefixed parts.

    All raw unit/prefix symbols are wrapped in \\mathrm{...} so they render
    as upright text in LaTeX.
    """
    parts = parse_compound_unit_parts(json_text)
    if not parts:
        return ""
    numerators, denominators = split_numerator_denominator(parts)

    def _wrap(s):
        from scifind_lib.i18n import wrap_symbol_in_latex
        return wrap_symbol_in_latex(s) if s else ""

    def render_items(items):
        if not items:
            return ""
        out = []
        for item in items:
            if len(item) == 3:
                unit_id, exponent, prefix = item
            else:
                unit_id, exponent = item
                prefix = None
            sym = unit_symbol(unit_id) if unit_symbol else unit_id
            if prefix is not None and prefix_symbol:
                sym = prefix_symbol(prefix) + sym
            sym_latex = _wrap(sym)
            out.append(sym_latex if exponent == 1 else f"{sym_latex}^{{{int(exponent)}}}")
        return " \\cdot ".join(out)

    num_str = render_items(numerators)
    den_str = render_items(denominators)
    if not den_str:
        return num_str
    if not num_str:
        return f"1 / ({den_str})" if len(denominators) > 1 else f"1 / {den_str}"
    return f"{num_str} / ({den_str})" if len(denominators) > 1 else f"{num_str} / {den_str}"


def _render_unit_group(items, url_func, name_func=None, locale="en-us",
                       use_special_exponents=False, prefix_name=None, raw_3=False):
    """Render unit parts as HTML with natural-language exponents.

    `items` may be (unit_id, exponent) pairs or, when `raw_3`, the
    (unit_id, exponent, prefix) triples produced by the prefix-aware
    parser. `prefix_name(prefix_exp)` supplies localized prefix names
    (e.g. 'Centi').

    When a prefix is present and the part is linked, the prefix is
    rendered as plain text before the link so the link wraps only the
    base unit name (e.g. "Kilo[gram]" instead of "[Kilogram]").
    """
    accusative = locale_accusative_names(locale) if use_special_exponents else {}
    out = []
    for i, item in enumerate(items):
        if raw_3:
            unit_id, exponent, prefix = item
        else:
            unit_id, exponent = item
            prefix = None
        label = name_func(unit_id) if name_func else unit_id.replace("_", " ").title()
        pref_text = ""
        if prefix is not None and prefix_name:
            pref = prefix_name(prefix) or ""
            # `name_func` capitalizes the first part of the compound; when a
            # prefix prefixes that part we need the lowercase base so the
            # prefix name joins the base word ("Centi"+"metre"="Centimetre").
            if i == 0 and label:
                label = label[0].lower() + label[1:]
            if i > 0 and pref:
                pref = pref[0].lower() + pref[1:]
            # When the part is linked, keep the prefix as plain text so
            # the link wraps only the base unit name. Otherwise join the
            # prefix and the base into a single word (e.g. "centimetre").
            link = url_func(unit_id) if url_func else None
            if link:
                pref_text = pref
            else:
                label = pref + label
        if use_special_exponents and label.lower() in accusative:
            label = accusative[label.lower()]
        if i > 0 and label:
            label = label[0].lower() + label[1:]
        word = unit_exponent_word(exponent, locale, denominator=use_special_exponents)
        if url_func:
            link = url_func(unit_id)
            if link:
                link_text = f'<a href="{html.escape(link)}">{html.escape(label)}</a>'
            else:
                link_text = html.escape(label)
        else:
            link_text = html.escape(label)
        text = pref_text + link_text
        if word:
            text += " " + html.escape(word)
        out.append(text)
    return "-".join(out)


def unit_name_map(conn, locale):
    return {r["id"]: localise(r["name"], locale)
            for r in conn.execute("SELECT id, name FROM unit").fetchall()}


def unit_symbol_map(conn):
    return {r["id"]: r["symbol"]
            for r in conn.execute("SELECT id, symbol FROM unit").fetchall()}


def unit_quantity_map(conn):
    return {r["id"]: r["quantity_id"]
            for r in conn.execute("SELECT id, quantity_id FROM unit").fetchall()}


def compound_unit_by_id(conn, cu_id):
    """One compound_unit row tagged with kind='compound_unit' (or None)."""
    if not cu_id:
        return None
    row = conn.execute(
        "SELECT * FROM compound_unit WHERE id = ?", (cu_id,),
    ).fetchone()
    if not row:
        return None
    return {"kind": "compound_unit", **dict(row)}


def unit_by_id(conn, unit_id):
    """One unit row tagged with kind='unit' (or None)."""
    if not unit_id:
        return None
    row = conn.execute(
        "SELECT * FROM unit WHERE id = ?", (unit_id,),
    ).fetchone()
    if not row:
        return None
    return {"kind": "unit", **dict(row)}


def select_base_unit(conn, quantity_id, system):
    """Canonical base row for (quantity_id, system), or None.

    Search order: compound_unit.is_base=1, then unit.is_base=1. Returns
    a dict with a 'kind' key ('compound_unit' or 'unit') and the row's
    columns. Caller is expected to retry with system='SI' on a None result.
    """
    if not quantity_id:
        return None
    row = conn.execute(
        "SELECT * FROM compound_unit "
        "WHERE quantity_id = ? AND system = ? AND is_base = 1 "
        "LIMIT 1",
        (quantity_id, system),
    ).fetchone()
    if row:
        return {"kind": "compound_unit", **dict(row)}
    row = conn.execute(
        "SELECT * FROM unit WHERE quantity_id = ? AND system = ? AND is_base = 1 LIMIT 1",
        (quantity_id, system),
    ).fetchone()
    if row:
        return {"kind": "unit", **dict(row)}
    return None


def select_base_unit_with_fallback(conn, quantity_id, system):
    """select_base_unit, falling back to SI if the chosen system has no base for this quantity."""
    chosen = select_base_unit(conn, quantity_id, system)
    if chosen is not None:
        return chosen
    if system != "SI":
        return select_base_unit(conn, quantity_id, "SI")
    return None