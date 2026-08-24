"""default_unit JSON parsing and HTML/LaTeX rendering."""
# Licensed under the LICENSE file in the project root.

import html
import json

from scifind_lib.i18n import (
    exponent_word,
    locale_accusative_names,
    locale_quantities_special,
    locale_words,
    localise,
)


def parse_default_unit(json_text):
    """Parse default_unit JSON into [(unit_id, exponent)]."""
    if not json_text:
        return []
    try:
        return [(p["unit"], p["exponent"]) for p in json.loads(json_text)]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def split_numerator_denominator(parts):
    return (
        [(u, e) for u, e in parts if e >= 0],
        [(u, -e) for u, e in parts if e < 0],
    )


def format_default_unit_html(
    json_text, unit_url=None, unit_name=None, locale="en-us", unit_quantity_map=None,
):
    """Render default_unit JSON as HTML with optional unit links."""
    parts = parse_default_unit(json_text)
    if not parts:
        return ""
    words = locale_words(locale)
    numerators, denominators = split_numerator_denominator(parts)
    num_html = render_unit_group(numerators, unit_url, unit_name, locale)
    if not denominators:
        return num_html
    per_word = words["per"]
    use_special = False
    if unit_quantity_map:
        special = locale_quantities_special(locale)
        for uid, _ in denominators:
            if unit_quantity_map.get(uid) in special:
                per_word = words.get("perSpecial", per_word)
                use_special = True
                break
    den_html = render_unit_group(denominators, unit_url, unit_name, locale,
                                 use_special_exponents=use_special)
    if not num_html:
        return f"{words['reciprocal']} {den_html}"
    return f"{num_html} {per_word} {den_html}"


def format_default_unit_symbol(json_text, unit_symbol=None):
    """Render default_unit JSON as a LaTeX symbol expression."""
    parts = parse_default_unit(json_text)
    if not parts:
        return ""
    numerators, denominators = split_numerator_denominator(parts)

    def render(items):
        if not items:
            return ""
        out = []
        for unit_id, exponent in items:
            sym = unit_symbol(unit_id) if unit_symbol else unit_id
            out.append(sym if exponent == 1 else f"{sym}^{{{int(exponent)}}}")
        return " \\cdot ".join(out)

    num_str = render(numerators)
    den_str = render(denominators)
    if not den_str:
        return num_str
    if not num_str:
        return f"1 / ({den_str})" if len(denominators) > 1 else f"1 / {den_str}"
    return f"{num_str} / ({den_str})" if len(denominators) > 1 else f"{num_str} / {den_str}"


def render_unit_group(parts, url_func, name_func=None, locale="en-us", use_special_exponents=False):
    """Render [(unit_id, exponent)] as HTML with natural-language exponents."""
    accusative = locale_accusative_names(locale) if use_special_exponents else {}
    items = []
    for i, (unit_id, exponent) in enumerate(parts):
        label = name_func(unit_id) if name_func else unit_id.replace("_", " ").title()
        if use_special_exponents and label.lower() in accusative:
            label = accusative[label.lower()]
        if i > 0 and label:
            label = label[0].lower() + label[1:]
        word = exponent_word(exponent, locale, denominator=use_special_exponents)
        text = (f'<a href="{html.escape(url_func(unit_id))}">{html.escape(label)}</a>'
                if url_func else html.escape(label))
        if word:
            text += " " + html.escape(word)
        items.append(text)
    return "-".join(items)


def unit_name_map(db, locale):
    """{unit_id: localised name} for every unit."""
    return {r["id"]: localise(r["name"], locale)
            for r in db.execute("SELECT id, name FROM unit").fetchall()}


def unit_symbol_map(db):
    return {r["id"]: r["symbol"]
            for r in db.execute("SELECT id, symbol FROM unit").fetchall()}


def unit_quantity_map(db):
    return {r["id"]: r["quantity_id"]
            for r in db.execute("SELECT id, quantity_id FROM unit").fetchall()}
