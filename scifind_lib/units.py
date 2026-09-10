"""Units: parsing, slugs, base resolution, HTML/LaTeX rendering + SI prefixes."""

import html
import json
import logging

from markupsafe import Markup

from scifind_lib.i18n import (
    localise,
    locale_accusative_names,
    locale_quantities_special,
    locale_unit_words,
    unit_exponent_word,
    wrap_symbol_in_latex,
)

logger = logging.getLogger(__name__)


def parse_compound_unit(json_text):
    """Parse compound_unit JSON into [(unit_id, exponent)] (or [] on NULL / unparseable)."""
    return [(uid, exp) for uid, exp, _prefix in parse_compound_unit_parts(json_text)]


def parse_compound_unit_parts(json_text):
    """Parse compound_unit JSON into [(unit_id, exponent, prefix_or_None)]."""
    if not json_text:
        return []
    try:
        parsed = json.loads(json_text)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("parse_compound_unit_parts: bad JSON: %s", exc)
        return []
    if not isinstance(parsed, list):
        return []
    triples = []
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
        triples.append((unit_id, exp, prefix))
    return triples


def split_numerator_denominator(items):
    """Split (unit_id, exponent, prefix) triples into numerator/denominator lists."""
    return (
        [item for item in items if item[1] >= 0],
        [(uid, -exp, prefix) for uid, exp, prefix in items if exp < 0],
    )


def _split_parts(json_text):
    """Parse JSON into (numerators, denominators) triples, or (None, None)."""
    parts = parse_compound_unit_parts(json_text)
    if not parts:
        return None, None
    return split_numerator_denominator(parts)


_PREFIX_NAMES = {
    -30: "quecti", -27: "ronti", -24: "yocto", -21: "zepto", -18: "atto",
    -15: "femto", -12: "pico", -9: "nano", -6: "micro", -3: "milli",
    -2: "centi", -1: "deci",
    1: "deca", 2: "hecto", 3: "kilo", 6: "mega", 9: "giga", 12: "tera",
    15: "peta", 18: "exa", 21: "zetta", 24: "yotta", 27: "ronna", 30: "quetta",
}


def _prefix_name(prefix):
    return _PREFIX_NAMES.get(prefix, f"p{prefix}")


def _part_slug(unit_id, exponent, prefix):
    """Render one (unit_id, exponent, prefix) as its contribution to a slug."""
    if prefix is not None and unit_id == "metre" and prefix < 0:
        if exponent == 2:
            return f"{_prefix_name(prefix)}{unit_id}_squared"
        if exponent == 3:
            return f"cubic_{_prefix_name(prefix)}{unit_id}"
    if prefix is not None:
        return f"{_prefix_name(prefix)}{unit_id}"
    if exponent == -1:
        return f"per_{unit_id}"
    if exponent == 1:
        return unit_id
    if exponent == 2:
        return f"{unit_id}_squared"
    if exponent == 3:
        return f"{unit_id}_cubed"
    return f"{unit_id}_e{int(exponent)}"


# (unit_id, prefix, exponent) -> slug for single-part compositions with
# irregular names (hectare/are/litre family).
_SINGLE_SLUG_SPECIALS = {
    ("metre", 2, 2): "hectare",
    ("metre", 1, 2): "are",
    ("metre", -1, 3): "litre",
    ("metre", -2, 3): "cubic_centimetre",
    ("metre", -3, 3): "cubic_millimetre",
}


def compound_unit_slug(quantity_id, unit_json):
    """Derive a slug from `(quantity_id, unit JSON)`; the quantity suffix keeps compositions distinct."""
    raw = parse_compound_unit_parts(unit_json)
    if not raw:
        return ""
    canonical = []
    for unit_id, exponent, prefix in raw:
        try:
            exponent = int(exponent)
        except (TypeError, ValueError):
            return ""
        canonical.append((unit_id, prefix, exponent))

    if len(canonical) == 1:
        unit_id, prefix, exponent = canonical[0]
        if prefix is None and exponent == 1 and quantity_id == "dimensionless":
            base = unit_id
        else:
            base = _SINGLE_SLUG_SPECIALS.get(
                (unit_id, prefix, exponent),
                _part_slug(unit_id, exponent, prefix),
            )
    elif (len(canonical) == 2 and all(u == "metre" for u, _, _ in canonical)
            and sorted(c[2] for c in canonical) == [-1, 1]):
        base = "millimetre_of_mercury"
    else:
        num_parts = [(u, p, e) for u, p, e in canonical if e > 0]
        den_parts = [(u, p, -e) for u, p, e in canonical if e < 0]
        if not num_parts or not den_parts:
            base = "_".join(_part_slug(u, e, p) for u, p, e in canonical)
        else:
            num_slug = "_".join(_part_slug(u, e, p) for u, p, e in num_parts)
            if num_slug == "revolution" and len(num_parts) == 1:
                num_slug = "revolutions"
            den_slug = "_".join(_part_slug(u, e, p) for u, p, e in den_parts)
            base = f"{num_slug}_per_{den_slug}"

    if not base:
        return ""
    if not quantity_id:
        return base
    return f"{base}_{quantity_id}"


def format_compound_unit_html(
    json_text, unit_url=None, unit_name=None, locale="en-us", unit_quantity_map=None,
    prefix_name=None,
):
    """Render compound_unit JSON as HTML with optional unit links."""
    split = _split_parts(json_text)
    if split[0] is None:
        return ""
    numerators, denominators = split
    words = locale_unit_words(locale)
    num_html = _render_unit_group(numerators, unit_url, unit_name, locale,
                                  prefix_name=prefix_name)
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
                                  prefix_name=prefix_name)
    if not num_html:
        return f"{words['reciprocal']} {den_html}"
    return f"{num_html} {per_word} {den_html}"


def format_compound_unit_symbol(json_text, unit_symbol=None, prefix_symbol=None):
    """Render compound_unit JSON as a LaTeX symbol expression."""
    split = _split_parts(json_text)
    if split[0] is None:
        return ""
    numerators, denominators = split

    def render_items(items):
        out = []
        for unit_id, exponent, prefix in items:
            sym = unit_symbol(unit_id) if unit_symbol else unit_id
            if prefix is not None and prefix_symbol:
                sym = prefix_symbol(prefix) + sym
            sym_latex = wrap_symbol_in_latex(sym) if sym else ""
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
                       use_special_exponents=False, prefix_name=None):
    """Render (unit_id, exponent, prefix) triples as HTML with natural-language exponents."""
    accusative = locale_accusative_names(locale) if use_special_exponents else {}
    fragments = []
    for i, (unit_id, exponent, prefix) in enumerate(items):
        label = name_func(unit_id) if name_func else unit_id.replace("_", " ").title()
        pref_text = ""
        if prefix is not None and prefix_name:
            pref = prefix_name(prefix) or ""
            # Lowercase the base so a leading prefix joins as one word
            # ("Centi"+"metre"="Centimetre").
            if i == 0 and label:
                label = label[0].lower() + label[1:]
            if i > 0 and pref:
                pref = pref[0].lower() + pref[1:]
            # Linked parts keep the prefix as plain text so only the base
            # name links; otherwise join prefix+base into one word.
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
        link = url_func(unit_id) if url_func else None
        link_text = (f'<a href="{html.escape(link)}">{html.escape(label)}</a>'
                     if link else html.escape(label))
        text = pref_text + link_text
        if word:
            text += " " + html.escape(word)
        fragments.append(text)
    return "-".join(fragments)


def _unit_column_map(conn, column):
    return {r["id"]: r[column]
            for r in conn.execute(f"SELECT id, {column} FROM unit").fetchall()}


def unit_name_map(conn, locale):
    return {r["id"]: localise(r["name"], locale)
            for r in conn.execute("SELECT id, name FROM unit").fetchall()}


def unit_symbol_map(conn):
    return _unit_column_map(conn, "symbol")


def unit_quantity_map(conn):
    return _unit_column_map(conn, "quantity_id")


def _tag_compound_row(row):
    """dict(row) tagged with kind='compound_unit' and a computed id slug."""
    tagged = {"kind": "compound_unit", **dict(row)}
    tagged["id"] = compound_unit_slug(tagged.get("quantity_id"), tagged.get("unit"))
    return tagged


def compound_unit_by_slug(conn, slug, quantity_id=None):
    """One compound_unit row matching a computed slug (or None)."""
    if not slug:
        return None
    if quantity_id:
        rows = conn.execute(
            "SELECT * FROM compound_unit WHERE quantity_id = ?", (quantity_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM compound_unit").fetchall()
    for row in rows:
        tagged = _tag_compound_row(row)
        if tagged["id"] == slug:
            return tagged
    return None


def compound_slug_is_base(conn, slug):
    """True if the compound_unit matching `slug` has is_base = 1."""
    if not slug:
        return False
    rows = conn.execute(
        "SELECT quantity_id, unit FROM compound_unit WHERE is_base = 1",
    ).fetchall()
    return any(
        compound_unit_slug(r["quantity_id"], r["unit"]) == slug for r in rows
    )


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
    """Canonical base row for (quantity_id, system), or None; prefers compound rows, then unit rows."""
    if not quantity_id:
        return None
    row = conn.execute(
        "SELECT * FROM compound_unit "
        "WHERE quantity_id = ? AND system = ? AND is_base = 1 "
        "LIMIT 1",
        (quantity_id, system),
    ).fetchone()
    if row:
        return _tag_compound_row(row)
    row = conn.execute(
        "SELECT * FROM unit WHERE quantity_id = ? AND system = ? AND is_base = 1 LIMIT 1",
        (quantity_id, system),
    ).fetchone()
    if row:
        return {"kind": "unit", **dict(row)}
    return None


def select_base_unit_with_fallback(conn, quantity_id, system):
    """select_base_unit, falling back to SI if the chosen system has no base for this quantity."""
    return (select_base_unit(conn, quantity_id, system)
            or (select_base_unit(conn, quantity_id, "SI") if system != "SI" else None))


# kilogram is the SI base of mass even though prefixes attach to gram.
SI_BASE_EXPONENT = {"gram": 3}

# Visible before expansion: base, kilo, milli. Deca/hecto are only shown
# by default when a DB entry (hectare, are) exists; synthetic rows collapse.
DEFAULT_VISIBLE_EXPONENTS = {0, 3, -3}


def unit_name_callback(names):
    """Capitalise-first unit-name lookup over a ``{id: name}`` map."""
    first = [True]

    def unit_name(uid):
        name = names.get(uid, uid.replace("_", " ")).lower()
        if first[0]:
            first[0] = False
            return name[0].upper() + name[1:]
        return name

    return unit_name


def prefix_name_callback(pname_map):
    """Prefix-name lookup over an ``{exponent: name}`` map."""
    return lambda exp: pname_map.get(exp, "")


def _normalise_prefix_symbol(prefix_sym, next_token):
    """Separate a backslash-command prefix from a following letter token with a space."""
    if not prefix_sym or not next_token:
        return prefix_sym
    if not next_token[0].isalnum() and next_token[0] != "_":
        return prefix_sym
    if prefix_sym.endswith(" "):
        return prefix_sym
    stripped = prefix_sym.rstrip()
    if not stripped.endswith("\\") and "\\" in stripped:
        last_bs = stripped.rfind("\\")
        tail = stripped[last_bs + 1:]
        if tail and tail.isalpha():
            return prefix_sym + " "
    if stripped.endswith("\\") or stripped.endswith("}"):
        return prefix_sym + " "
    return prefix_sym


def _build_compound_sym_latex(unit_syms, prefix_sym, primary_uid, parts):
    """Prefixed compound LaTeX with the prefix on the primary prefixable part."""
    primary_raw = unit_syms.get(primary_uid, primary_uid)
    combined = _normalise_prefix_symbol(prefix_sym, primary_raw) + primary_raw
    entries = [{"unit": uid, "exponent": exp} for uid, exp in parts]
    return format_compound_unit_symbol(
        json.dumps(entries),
        unit_symbol=lambda uid: combined if uid == primary_uid else unit_syms.get(uid, uid),
    )


def _prefixable_parts(conn, parts_with_prefix):
    """[(part_uid, part_exp, pref_uid, base_prefix)] for the prefixable parts."""
    from scifind_lib.fetch import fetch_prefixable_base_units

    prefixable_map = fetch_prefixable_base_units(conn)
    existing_prefix = {}
    for uid, _exp, prefix in parts_with_prefix:
        if prefix is not None and uid not in existing_prefix:
            existing_prefix[uid] = prefix
    prefixable_parts = []
    for uid, exp, _prefix in parts_with_prefix:
        pref_uid = prefixable_map.get(uid)
        if pref_uid:
            prefixable_parts.append((uid, exp, pref_uid, existing_prefix.get(uid, 0)))
    return prefixable_parts


def inject_si_prefix_nodes(graph, conn, quantity_id, locale, system, *, unit_syms):
    """Inject synthetic SI-prefixed nodes (si_kilo -> base) for the prefix table; dimensionless skipped."""
    from scifind_lib.fetch import (
        fetch_prefixable_base_units,
        fetch_si_prefixes,
        fetch_unit,
    )

    if quantity_id == "dimensionless":
        return
    base = select_base_unit_with_fallback(conn, quantity_id, system)
    if not base:
        return

    prefixable = fetch_prefixable_base_units(conn)
    if base["kind"] == "unit":
        pref_base_id = prefixable.get(base["id"], base["id"])
        base_unit_row = fetch_unit(conn, pref_base_id)
        if base_unit_row is None:
            return
        base_symbol = base_unit_row["symbol"]
        for p in fetch_si_prefixes(conn):
            exp = int(p["id"])
            pid = f"si_{p['id']}"
            graph.edges[pid] = (pref_base_id, 10 ** exp, 0, None, "mul", 0.0)
            prefix_sym = _normalise_prefix_symbol(localise(p["symbol"], locale), base_symbol)
            graph.unit_rows[pid] = {
                "id": pid,
                "symbol": prefix_sym + base_symbol,
                "system": "SI",
                "quantity_id": quantity_id,
                "is_base": 0,
            }
    else:
        parts_with_prefix = parse_compound_unit_parts(base["unit"])
        parts = [(uid, exp) for uid, exp, _prefix in parts_with_prefix]
        if not parts:
            return
        prefixable_parts = _prefixable_parts(conn, parts_with_prefix)
        if not prefixable_parts:
            return

        for part_uid, part_exp, _pref_uid, base_prefix in prefixable_parts:
            for p in fetch_si_prefixes(conn):
                exp = int(p["id"])
                if exp == base_prefix:
                    continue
                pid = f"si_{p['id']}_{part_uid}"
                prefixed_sym_latex = _build_compound_sym_latex(
                    unit_syms, localise(p["symbol"], locale), part_uid, parts
                )
                prefixed_entries = []
                for uid, e, old_prefix in parts_with_prefix:
                    if uid == part_uid:
                        if exp == 0:
                            prefixed_entries.append({"unit": uid, "exponent": e})
                        else:
                            prefixed_entries.append(
                                {"unit": uid, "exponent": e, "prefix": exp}
                            )
                    elif old_prefix is None:
                        prefixed_entries.append({"unit": uid, "exponent": e})
                    else:
                        prefixed_entries.append(
                            {"unit": uid, "exponent": e, "prefix": int(old_prefix)}
                        )
                graph.compound_rows[pid] = {
                    "id": pid,
                    "unit": json.dumps(prefixed_entries),
                    "symbol_overwrite": prefixed_sym_latex,
                    "system": "SI",
                    "quantity_id": quantity_id,
                    "is_base": 0,
                }


def _prefixed_unit_name(prefix_word, base_name, link_unit_id):
    return (
        html.escape(prefix_word)
        + f'<a href="/unit/{link_unit_id}">'
        + html.escape(base_name.lower())
        + "</a>"
    )


def _collapse_flags(rows):
    for r in rows:
        is_db_entry = r.get("is_db_entry", False)
        r["collapsed"] = (not is_db_entry) and (r["exp"] not in DEFAULT_VISIBLE_EXPONENTS)
    return rows


def si_prefix_sections(conn, quantity_id, locale, *,
                       unit_names, unit_syms, prefix_names, prefix_syms):
    """Prefix-table sections for a quantity's SI base unit, or None (dimensionless returns None)."""
    from scifind_lib.fetch import (
        fetch_compound_units,
        fetch_first_unit,
        fetch_prefixable_base_units,
        fetch_si_prefixes,
        fetch_unit,
    )

    if quantity_id == "dimensionless":
        return None
    base = select_base_unit_with_fallback(conn, quantity_id, "SI")
    if not base:
        base = fetch_first_unit(conn, quantity_id)
        if not base:
            return None
        base = {"kind": "unit", **dict(base)}

    prefixable = fetch_prefixable_base_units(conn)
    if base["kind"] == "unit":
        base_id = prefixable.get(base["id"], base["id"])
        base_unit_row = fetch_unit(conn, base_id)
        if base_unit_row is None:
            return None
        base_symbol = base_unit_row["symbol"]
        base_name = localise(base_unit_row["name"], locale)
        base_id_for_link = base_id

        def system_field(exp):
            if exp == SI_BASE_EXPONENT.get(base_id, 0):
                return ("detail.si_base", base_id_for_link)
            return (None, None)

        def make_prefix_rows(base_id, base_name, base_symbol):
            base_symbol_latex = wrap_symbol_in_latex(base_symbol)
            prefixed = [{
                "id": base_id,
                "exp": 0,
                "symbol_latex": base_symbol_latex,
                "name": base_name,
                "system_key": system_field(0)[0],
                "link_unit_id": base_id_for_link,
                "value_latex": "10^{0}",
            }]

            for p in fetch_si_prefixes(conn):
                exp = int(p["id"])
                sys_key, _ = system_field(exp)
                prefix_sym = localise(p["symbol"], locale)
                normalised_prefix = _normalise_prefix_symbol(prefix_sym, base_symbol)
                prefix_word = localise(p["name"], locale)
                prefixed.append({
                    "id": f"si_{p['id']}",
                    "exp": exp,
                    "symbol_latex": wrap_symbol_in_latex(normalised_prefix + base_symbol),
                    "name": Markup(_prefixed_unit_name(prefix_word, base_name, base_id_for_link)),
                    "system_key": sys_key,
                    "link_unit_id": None,
                    "value_latex": f"10^{{{exp}}}",
                })
            for r in prefixed:
                r["collapsed"] = r["exp"] not in DEFAULT_VISIBLE_EXPONENTS
                r["payload_id"] = r["id"] or base_id or "si_base"
            prefixed.sort(key=lambda x: x["exp"], reverse=True)
            return prefixed

        rows = make_prefix_rows(base_id, base_name, base_symbol)
        return {base_id: {"component": base_id, "label": base_name, "rows": rows}}

    parts_with_prefix = parse_compound_unit_parts(base["unit"])
    parts = [(uid, exp) for uid, exp, _prefix in parts_with_prefix]
    if not parts:
        return None

    prefixable_parts = _prefixable_parts(conn, parts_with_prefix)
    if not prefixable_parts:
        return None

    base_id = base.get("id")
    base_symbol_latex = base.get("symbol_overwrite")
    if not base_symbol_latex:
        base_symbol_latex = format_compound_unit_symbol(
            base["unit"],
            unit_symbol=lambda uid: unit_syms.get(uid, uid),
            prefix_symbol=lambda exp: prefix_syms.get(exp, str(exp)),
        )

    def make_component_section(part_uid, part_exp, base_prefix):
        prefixed = []
        db_prefix_entries = {}
        for row in fetch_compound_units(conn, quantity_id, only_non_base=True):
            try:
                units = json.loads(row["unit"])
                if isinstance(units, list):
                    for u in units:
                        if isinstance(u, dict) and "prefix" in u and u.get("unit") == part_uid:
                            pref_val = u["prefix"]
                            if pref_val is not None:
                                try:
                                    pref_exp = int(pref_val)
                                    db_prefix_entries[pref_exp] = row
                                except (ValueError, TypeError):
                                    pass
            except (json.JSONDecodeError, TypeError):
                pass

        base_row_exp = base_prefix
        prefixed.append({
            "id": f"{base_id}_{part_uid}_base",
            "exp": base_row_exp,
            "symbol_latex": base_symbol_latex,
            "name": format_compound_unit_html(
                base["unit"], locale=locale,
                unit_name=unit_name_callback(unit_names),
                unit_url=lambda uid: f"/unit/{uid}" if uid in unit_names else None,
                prefix_name=prefix_name_callback(prefix_names),
            ),
            "system_key": "detail.si_base",
            "link_unit_id": None,
            "value_latex": f"10^{{{base_row_exp * part_exp}}}",
        })

        for p in fetch_si_prefixes(conn):
            exp = int(p["id"])
            if exp == base_row_exp:
                continue

            if exp in db_prefix_entries:
                db_entry = db_prefix_entries[exp]
                name_json = db_entry["name_overwrite"]
                if name_json:
                    db_entry_name = (localise(name_json, locale)
                                     or db_entry["id"].replace("_", " ").title())
                else:
                    db_entry_name = db_entry["id"].replace("_", " ").title()
                sym_overwrite = db_entry["symbol_overwrite"]
                if sym_overwrite:
                    db_sym_latex = sym_overwrite
                else:
                    db_parts = parse_compound_unit(db_entry["unit"])
                    if db_parts and part_uid:
                        prefix_sym = localise(p["symbol"], locale)
                        db_sym_latex = _build_compound_sym_latex(
                            unit_syms, prefix_sym, part_uid, db_parts
                        )
                    else:
                        db_sym_latex = format_compound_unit_symbol(
                            db_entry["unit"],
                            unit_symbol=lambda uid: unit_syms.get(uid, uid),
                            prefix_symbol=lambda exp: prefix_syms.get(exp, str(exp)),
                        )
                prefixed.append({
                    "id": db_entry["id"],
                    "exp": exp,
                    "symbol_latex": db_sym_latex,
                    "name": db_entry_name,
                    "system_key": None,
                    "link_unit_id": part_uid,
                    "value_latex": f"10^{{{exp * part_exp}}}",
                    "is_db_entry": True,
                })
                continue

            prefix_name_val = localise(p["name"], locale)
            prefix_sym = localise(p["symbol"], locale)
            prefixed_parts = [
                {"unit": uid, "exponent": exp_val, "prefix": exp}
                if uid == part_uid
                else {"unit": uid, "exponent": exp_val}
                for uid, exp_val in parts
            ]
            pref_name_html = format_compound_unit_html(
                json.dumps(prefixed_parts), locale=locale,
                unit_name=unit_name_callback(unit_names),
                prefix_name=lambda _exp: prefix_name_val,
                unit_url=lambda uid: f"/unit/{uid}" if uid in unit_names else None,
            )
            pref_sym_latex = _build_compound_sym_latex(
                unit_syms, prefix_sym, part_uid, parts
            )
            prefixed.append({
                "id": f"si_{p['id']}_{part_uid}",
                "exp": exp,
                "symbol_latex": pref_sym_latex,
                "name": pref_name_html,
                "system_key": None,
                "link_unit_id": None,
                "value_latex": f"10^{{{exp * part_exp}}}",
            })

        _collapse_flags(prefixed)
        for r in prefixed:
            r["payload_id"] = r["id"] or f"{base_id}_{part_uid}" or "si_base"
        prefixed.sort(key=lambda x: x["exp"], reverse=True)
        return prefixed

    sections = {}
    for part_uid, part_exp, _pref_uid, base_prefix in prefixable_parts:
        part_unit_row = fetch_unit(conn, part_uid)
        if part_unit_row:
            part_name = localise(part_unit_row["name"], locale)
        else:
            part_name = part_uid.replace("_", " ").title()
        sections[part_uid] = {
            "component": part_uid,
            "label": f"Prefixed on: {part_name}",
            "rows": make_component_section(part_uid, part_exp, base_prefix),
        }

    return sections
