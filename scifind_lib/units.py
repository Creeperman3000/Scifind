"""Units: parsing, slugs, base resolution, HTML/LaTeX rendering + SI prefixes."""

import html
import json
import logging
import re

from markupsafe import Markup

from scifind_lib.constants import DEFAULT_VISIBLE_EXPONENTS
from scifind_lib.db import in_clause
from scifind_lib.i18n import (
    localise,
    locale_unit_words,
    unit_exponent_word,
    wrap_symbol_in_latex,
)
from scifind_lib.util import anchor, safe_json_list

logger = logging.getLogger(__name__)


def parse_compound_unit(json_text):
    """Parse compound_unit JSON into [(unit_id, exponent)] (or [] on NULL / unparseable)."""
    return [(uid, exp) for uid, exp, _prefix in parse_compound_unit_parts(json_text)]


def _as_triple(entry):
    """One compound-unit entry as (unit_id, exponent, prefix_or_None), or None."""
    if not isinstance(entry, dict):
        return None
    unit_id, exp = entry.get("unit"), entry.get("exponent")
    if not isinstance(unit_id, str) or not isinstance(exp, (int, float)):
        return None
    prefix = entry.get("prefix")
    if prefix is not None:
        try:
            prefix = int(prefix)
        except (TypeError, ValueError):
            prefix = None
    return (unit_id, exp, prefix)


def parse_compound_unit_parts(json_text):
    """Parse compound_unit JSON into [(unit_id, exponent, prefix_or_None)]."""
    if not json_text:
        return []
    parsed = safe_json_list(json_text)
    if not isinstance(parsed, list):
        return []
    triples = [_as_triple(e) for e in parsed]
    return [] if any(t is None for t in triples) else triples


def split_numerator_denominator(items):
    """Split (unit_id, exponent, prefix) triples into numerator/denominator lists."""
    return (
        [item for item in items if item[1] >= 0],
        [(uid, -exp, prefix) for uid, exp, prefix in items if exp < 0],
    )


def _fraction_parts(json_text):
    """(numerators, denominators) triples, or None when empty/unparseable."""
    parts = parse_compound_unit_parts(json_text)
    return split_numerator_denominator(parts) if parts else None


def si_prefix_factor(exp):
    """SI prefix multiplier (si_prefix.id is the power of 10)."""
    return 10 ** int(exp)


def _visible_exponents_uncached(conn=None):
    return set(DEFAULT_VISIBLE_EXPONENTS)


def _visible_exponents(conn=None):
    return set(DEFAULT_VISIBLE_EXPONENTS)


def _is_dimensionless(conn, quantity_id):
    row = conn.execute("SELECT * FROM quantity WHERE id = ?", (quantity_id,)).fetchone()
    return all((row[c] or 0) == 0 for c in row.keys()
               if c.startswith("dim_") and c not in ("dim_symbol", "dim_position"))


def _canon_int(n):
    """Slug-safe integer token: 3 -> "3", -2 -> "m2" (slugs allow [a-z0-9_])."""
    n = int(n)
    return f"m{-n}" if n < 0 else str(n)


def _part_slug(unit_id, exponent, prefix):
    """One (unit_id, exponent, prefix) triple as its contribution to a canonical slug.

    Examples: metre^1 -> "metre"; gram kilo^1 -> "gram_p3";
    metre centi^2 -> "metre_pm2_squared"; second^-1 alone -> "per_second".
    """
    exp = int(exponent)
    token = unit_id if prefix is None else f"{unit_id}_p{_canon_int(prefix)}"
    if exp == 1:
        return token
    if exp == -1:
        return f"per_{token}"
    if exp == 2:
        return f"{token}_squared"
    if exp == 3:
        return f"{token}_cubed"
    return f"{token}_e{_canon_int(exp)}"


def compound_unit_slug(quantity_id, unit_json):
    """Canonical id for (quantity_id, compound_unit JSON).

    Pure function of the parts: no database access, no locale. The same
    parts always give the same id, so ids are stable across locales and
    need no stored column (recomputing can never drift from the parts).
    """
    entries = parse_compound_unit_parts(unit_json)
    if not entries:
        return ""
    try:
        canonical = [(u, int(e), p) for u, e, p in entries]
    except (TypeError, ValueError):
        return ""
    join = lambda parts: "_".join(_part_slug(u, e, p) for u, e, p in parts)

    if len(canonical) == 1:
        base = _part_slug(*canonical[0])
    else:
        num = [t for t in canonical if t[1] > 0]
        den = [(u, -e, p) for u, e, p in canonical if e < 0]
        if num and den:
            base = f"{join(num)}_per_{join(den)}"
        else:
            base = join(num + den)  # one side empty; den holds magnitudes

    if not base or not quantity_id:
        return base
    return f"{base}_{quantity_id}"


def format_compound_unit_html(
    json_text, unit_url=None, unit_name=None, locale="en-us", unit_quantity_map=None,
    quantity_pers=None, unit_accusatives=None, prefix_name=None,
):
    """Render compound_unit JSON as HTML with optional unit links.

    The "per" word defaults to ``unitWords.per`` for the locale, but a
    denominator part whose quantity carries ``quantity.per_overwrite``
    for this locale switches to that word (e.g. Czech time -> "za")
    and renders the denominator in the accusative (``unit.name_accusative``).
    """
    split = _fraction_parts(json_text)
    if split is None:
        return ""
    numerators, denominators = split
    words = locale_unit_words(locale)
    num_html = _render_unit_group(numerators, unit_url, unit_name, locale,
                                   prefix_name=prefix_name)
    if not denominators:
        return num_html
    use_special, per_word = False, words["per"]
    if unit_quantity_map and quantity_pers:
        for uid, _e, _p in denominators:
            qid = unit_quantity_map.get(uid)
            override = localise(quantity_pers.get(qid) or "", locale) if qid else ""
            if override:
                use_special, per_word = True, override
                break
    den_html = _render_unit_group(denominators, unit_url, unit_name, locale,
                                   use_special_exponents=use_special,
                                   unit_accusatives=unit_accusatives,
                                   prefix_name=prefix_name)
    if not num_html:
        return f"{words['reciprocal']} {den_html}"
    return f"{num_html} {per_word} {den_html}"


def _render_symbol_items(items, unit_symbol, prefix_symbol):
    """(unit_id, exponent, prefix) triples as LaTeX factors joined with \\cdot."""
    factors = []
    for unit_id, exponent, prefix in items:
        sym = unit_symbol(unit_id) if unit_symbol else unit_id
        if prefix is not None and prefix_symbol:
            sym = prefix_symbol(prefix) + sym
        sym_latex = wrap_symbol_in_latex(sym) if sym else ""
        factors.append(sym_latex if exponent == 1 else f"{sym_latex}^{{{int(exponent)}}}")
    return " \\cdot ".join(factors)


def format_compound_unit_symbol(json_text, unit_symbol=None, prefix_symbol=None):
    """Render compound_unit JSON as a LaTeX symbol expression."""
    split = _fraction_parts(json_text)
    if split is None:
        return ""
    numerators, denominators = split
    num_str = _render_symbol_items(numerators, unit_symbol, prefix_symbol)
    den_str = _render_symbol_items(denominators, unit_symbol, prefix_symbol)
    if not den_str:
        return num_str
    den = f"({den_str})" if len(denominators) > 1 else den_str
    return f"1 / {den}" if not num_str else f"{num_str} / {den}"


def _lower_first(text):
    """Lowercase the first character (empty-safe)."""
    return text[:1].lower() + text[1:] if text else text


def strip_compound_html(text):
    """Plain text from compound-unit HTML (tags stripped, escapes resolved)."""
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def _render_unit_group(items, url_func, name_func=None, locale="en-us",
                       use_special_exponents=False, unit_accusatives=None,
                       prefix_name=None):
    """Render (unit_id, exponent, prefix) triples as HTML with natural-language exponents.

    Exponents 2/3 render before the noun ("Square inch") when the locale
    provides attributive words ("square"/"cubic"); locales without them
    keep the post-noun form ("Inch squared").
    """
    words = locale_unit_words(locale)
    fragments = []
    for i, (unit_id, exponent, prefix) in enumerate(items):
        label = name_func(unit_id) if name_func else unit_id.replace("_", " ").title()
        link = url_func(unit_id) if url_func else None
        pref_text = ""
        if prefix is not None and prefix_name:
            pref = prefix_name(prefix) or ""
            # Lowercase the base so a leading prefix joins as one word
            # ("Centi"+"metre"="Centimetre"); linked parts keep the
            # prefix as plain text so only the base name links.
            if i == 0:
                label = _lower_first(label)
            else:
                pref = _lower_first(pref)
            if link:
                pref_text = pref
            else:
                label = pref + label
        if use_special_exponents and unit_accusatives:
            acc = localise(unit_accusatives.get(unit_id) or "", locale)
            if acc:
                label = acc
        if i > 0:
            label = _lower_first(label)
        attr = (None if use_special_exponents else words.get(
            "square" if exponent == 2 else "cubic" if exponent == 3 else ""))
        if attr:
            # Attributive form carries the capital, so the base stays lowercase
            # ("Square centimetre", never "Square Centimetre").
            if link and pref_text:
                pref_text = _lower_first(pref_text)
            else:
                label = _lower_first(label)
            link_text = (anchor(link, label) if link else html.escape(label))
            fragments.append(f"{attr} {pref_text}{link_text}")
            continue
        word = unit_exponent_word(exponent, locale, denominator=use_special_exponents)
        link_text = (anchor(link, label) if link else html.escape(label))
        fragment = pref_text + link_text
        if word:
            fragment += " " + html.escape(word)
        fragments.append(fragment)
    return " ".join(fragments)


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


def quantity_per_map(conn):
    """{quantity_id: per_overwrite JSON text} for denominator prepositions."""
    return {r["id"]: r["per_overwrite"]
            for r in conn.execute("SELECT id, per_overwrite FROM quantity").fetchall()}


def unit_accusative_map(conn):
    """{unit_id: name_accusative JSON text} for declined denominator names."""
    return {r["id"]: r["name_accusative"]
            for r in conn.execute("SELECT id, name_accusative FROM unit").fetchall()}


def _compound_slug_map(conn, only_base=False):
    """{canonical id: row} for compound units (ids derived from parts, never stored)."""
    slug_map = {}
    sql = "SELECT * FROM compound_unit" + (" WHERE is_base = 1" if only_base else "")
    for row in conn.execute(sql).fetchall():
        row_dict = dict(row)
        if slug := compound_unit_slug(row_dict.get("quantity_id"), row_dict.get("unit")):
            slug_map.setdefault(slug, {"kind": "compound_unit", **row_dict, "id": slug})
    return slug_map


def compound_unit_by_slug(conn, slug, quantity_id=None):
    """One compound_unit row matching a canonical id (or None)."""
    if not slug:
        return None
    hit = _compound_slug_map(conn).get(slug)
    if hit is None or (quantity_id is not None and hit.get("quantity_id") != quantity_id):
        return None
    return dict(hit)


def compound_slug_is_base(conn, slug):
    """True if the compound_unit matching `slug` has is_base = 1."""
    if not slug:
        return False
    return slug in _compound_slug_map(conn, only_base=True)


def resolve_base_unit(conn, unit_id=None, compound_id=None, fallback_qid=None,
                      system="SI"):
    """Single base-unit resolve path: explicit unit/compound id, else base-with-fallback."""
    base = None
    if unit_id:
        from scifind_lib.fetch import fetch_unit
        row = fetch_unit(conn, unit_id)
        base = {"kind": "unit", **dict(row)} if row else None
    elif compound_id:
        base = compound_unit_by_slug(conn, compound_id, fallback_qid)
    if base is None and fallback_qid:
        base = select_base_unit_with_fallback(conn, fallback_qid, system)
    return base


def select_base_unit(conn, quantity_id, system):
    """Canonical base row for (quantity_id, system), or None; prefers compound rows, then unit rows."""
    if not quantity_id:
        return None
    return select_base_units_batched(conn, [quantity_id], system).get(quantity_id)


def select_base_unit_with_fallback(conn, quantity_id, system):
    """select_base_unit, falling back to SI if the chosen system has no base for this quantity."""
    return (select_base_unit(conn, quantity_id, system)
            or (select_base_unit(conn, quantity_id, "SI") if system != "SI" else None))


def select_base_units_batched(conn, quantity_ids, system):
    """{quantity_id: base row} for many quantities with ≤4 queries (no N+1)."""
    qids = list(dict.fromkeys(quantity_ids))
    if not qids:
        return {}

    def _load(ids, sys):
        marks, params = in_clause(ids)
        sql = f"SELECT * FROM {{}} WHERE quantity_id IN ({marks}) AND system = ? AND is_base = 1"
        found = {}
        for r in conn.execute(sql.format("compound_unit"), params + (sys,)).fetchall():
            comp_row = {"kind": "compound_unit", **dict(r)}
            if slug := compound_unit_slug(comp_row.get("quantity_id"), comp_row.get("unit")):
                found.setdefault(comp_row["quantity_id"], {**comp_row, "id": slug})
        for r in conn.execute(sql.format("unit"), params + (sys,)).fetchall():
            found.setdefault(r["quantity_id"], {"kind": "unit", **dict(r)})
        return found

    base_by_quantity = _load(qids, system)
    if missing := [qid for qid in qids if qid not in base_by_quantity]:
        if system != "SI":
            base_by_quantity.update({k: v for k, v in _load(missing, "SI").items() if k not in base_by_quantity})
    return base_by_quantity


def unit_name_callback(names):
    """Capitalise-first unit-name lookup over a ``{id: name}`` map."""
    first = True

    def unit_name(uid):
        nonlocal first
        name = names.get(uid, uid.replace("_", " ")).lower()
        if first:
            first = False
            return name.capitalize()
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


def _swapped_entries(parts_with_prefix, part_uid, exp):
    """Parts with `part_uid`'s prefix swapped to `exp` (0 strips it); other parts untouched."""
    entries = []
    for uid, e, old_prefix in parts_with_prefix:
        if uid == part_uid:
            entry = {"unit": uid, "exponent": e}
            if exp != 0:
                entry["prefix"] = exp
            entries.append(entry)
        elif old_prefix is None:
            entries.append({"unit": uid, "exponent": e})
        else:
            entries.append({"unit": uid, "exponent": e, "prefix": int(old_prefix)})
    return entries


def _db_prefix_entries(conn, quantity_id):
    """{part_uid: {prefix_exp: non-base compound row}} for prefixed DB compounds."""
    from scifind_lib.fetch import fetch_compound_units

    found = {}
    for row in fetch_compound_units(conn, quantity_id, only_non_base=True):
        for u in safe_json_list(row["unit"]):
            if not isinstance(u, dict) or u.get("prefix") is None:
                continue
            try:
                exp = int(u["prefix"])
            except (ValueError, TypeError):
                continue
            if u.get("unit"):
                found.setdefault(u["unit"], {}).setdefault(exp, row)
    return found


def _prefixable_parts(conn, parts_with_prefix):
    """[(part_uid, part_exp, base_prefix)] for the prefixable parts.

    The prefix anchor is always the part with its old prefix stripped
    (e.g. mass SI base ``gram_p3`` anchors on ``gram``), so attaching a
    new prefix is just swapping the exponent — no per-quantity special
    cases. A part is prefixable when its unit is an SI base unit, with
    ``gram`` included as mass's anchor.
    """
    from scifind_lib.fetch import fetch_prefixable_base_units

    prefixable = fetch_prefixable_base_units(conn)
    existing_prefix = {}
    for uid, _exp, prefix in parts_with_prefix:
        if prefix is not None and uid not in existing_prefix:
            existing_prefix[uid] = int(prefix)
    return [(uid, exp, existing_prefix.get(uid, 0))
            for uid, exp, _prefix in parts_with_prefix if uid in prefixable]


def inject_si_prefix_nodes(graph, conn, quantity_id, locale, system, *, unit_syms):
    """Inject synthetic SI-prefixed nodes for the prefix table; dimensionless skipped."""
    from scifind_lib.fetch import (
        fetch_si_prefixes,
        fetch_unit,
    )

    if _is_dimensionless(conn, quantity_id):
        return
    base = select_base_unit_with_fallback(conn, quantity_id, system)
    if not base:
        return

    if base["kind"] == "unit":
        # A plain-unit base anchors prefixes on itself.
        pref_base_id = base["id"]
        base_unit_row = fetch_unit(conn, pref_base_id)
        if base_unit_row is None:
            return
        base_symbol = base_unit_row["symbol"]
        for p in fetch_si_prefixes(conn):
            exp = int(p["id"])
            pid = f"si_{p['id']}"
            graph.edges[pid] = graph.make_edge(pref_base_id, si_prefix_factor(exp))
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

        for part_uid, _part_exp, base_prefix in prefixable_parts:
            for p in fetch_si_prefixes(conn):
                exp = int(p["id"])
                if exp == base_prefix:
                    continue
                pid = f"si_{p['id']}_{part_uid}"
                prefixed_sym_latex = _build_compound_sym_latex(
                    unit_syms, localise(p["symbol"], locale), part_uid, parts
                )
                graph.compound_rows[pid] = {
                    "id": pid,
                    "unit": json.dumps(_swapped_entries(parts_with_prefix, part_uid, exp)),
                    "symbol_overwrite": prefixed_sym_latex,
                    "system": "SI",
                    "quantity_id": quantity_id,
                    "is_base": 0,
                }


def _prefixed_unit_name(prefix_word, base_name, link_unit_id):
    return html.escape(prefix_word) + anchor(f"/unit/{link_unit_id}", base_name.lower())


def _collapse_flags(rows, conn, fallback="si_base"):
    visible = _visible_exponents(conn)
    for r in rows:
        r["collapsed"] = (not r.get("is_db_entry", False)) and (r["exp"] not in visible)
        r["payload_id"] = r["id"] or fallback
    return rows


def si_prefix_sections(conn, quantity_id, locale, *,
                       unit_names, unit_syms, prefix_names, prefix_syms,
                       quantity_pers=None, unit_accusatives=None):
    """Prefix-table sections for a quantity's SI base unit, or None for dimensionless."""
    from scifind_lib.fetch import (
        fetch_compound_units,
        fetch_first_unit,
        fetch_si_prefixes,
        fetch_unit,
    )

    if _is_dimensionless(conn, quantity_id):
        return None
    base = select_base_unit_with_fallback(conn, quantity_id, "SI")
    if not base:
        base = fetch_first_unit(conn, quantity_id)
        if not base:
            return None
        base = {"kind": "unit", **dict(base)}
    if base["kind"] == "unit":
        base_id = base["id"]
        base_unit_row = fetch_unit(conn, base_id)
        if base_unit_row is None:
            return None
        base_symbol = base_unit_row["symbol"]
        base_name = localise(base_unit_row["name"], locale)

        def system_key(exp):
            return "detail.si_base" if exp == 0 else None

        def make_prefix_rows():
            base_symbol_latex = wrap_symbol_in_latex(base_symbol)
            prefixed = [{
                "id": base_id,
                "exp": 0,
                "symbol_latex": base_symbol_latex,
                "name": base_name,
                "system_key": system_key(0),
                "link_unit_id": base_id,
                "value_latex": "10^{0}",
            }]

            for p in fetch_si_prefixes(conn):
                exp = int(p["id"])
                prefix_sym = localise(p["symbol"], locale)
                normalised_prefix = _normalise_prefix_symbol(prefix_sym, base_symbol)
                prefix_word = localise(p["name"], locale)
                prefixed.append({
                    "id": f"si_{p['id']}",
                    "exp": exp,
                    "symbol_latex": wrap_symbol_in_latex(normalised_prefix + base_symbol),
                    "name": Markup(_prefixed_unit_name(prefix_word, base_name, base_id)),
                    "system_key": system_key(exp),
                    "link_unit_id": None,
                    "value_latex": f"10^{{{exp}}}",
                })
            _collapse_flags(prefixed, conn, base_id or "si_base")
            prefixed.sort(key=lambda x: x["exp"], reverse=True)
            return prefixed

        rows = make_prefix_rows()
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

    prefix_map = _db_prefix_entries(conn, quantity_id)

    def make_component_section(part_uid, part_exp, base_prefix):
        prefixed = []
        db_prefix_entries = prefix_map.get(part_uid, {})

        prefixed.append({
            "id": f"{base_id}_{part_uid}_base",
            "exp": base_prefix,
            "symbol_latex": base_symbol_latex,
            "name": format_compound_unit_html(
                base["unit"], locale=locale,
                unit_name=unit_name_callback(unit_names),
                unit_url=lambda uid: f"/unit/{uid}" if uid in unit_names else None,
                unit_quantity_map=unit_quantity_map(conn),
                quantity_pers=quantity_pers or quantity_per_map(conn),
                unit_accusatives=unit_accusatives or unit_accusative_map(conn),
                prefix_name=prefix_name_callback(prefix_names),
            ),
            "system_key": "detail.si_base",
            "link_unit_id": None,
            "value_latex": f"10^{{{base_prefix * part_exp}}}",
        })

        for p in fetch_si_prefixes(conn):
            exp = int(p["id"])
            if exp == base_prefix:
                continue

            if exp in db_prefix_entries:
                db_entry = db_prefix_entries[exp]
                name_json = db_entry["name_overwrite"]
                db_entry_name = localise(name_json, locale) if name_json else ""
                if not db_entry_name:
                    # No overwrite (or no translation for this locale):
                    # derive from the parts instead of the slug. Plain text
                    # (no links): the template wraps this in an outer link.
                    db_entry_name = strip_compound_html(format_compound_unit_html(
                        db_entry["unit"], locale=locale,
                        unit_name=unit_name_callback(unit_names),
                        unit_quantity_map=unit_quantity_map(conn),
                        quantity_pers=quantity_per_map(conn),
                        unit_accusatives=unit_accusative_map(conn),
                        prefix_name=prefix_name_callback(prefix_names),
                    )) or db_entry["id"].replace("_", " ").title()
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

        _collapse_flags(prefixed, conn, f"{base_id}_{part_uid}" or "si_base")
        prefixed.sort(key=lambda x: x["exp"], reverse=True)
        return prefixed

    sections = {}
    for part_uid, part_exp, base_prefix in prefixable_parts:
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
