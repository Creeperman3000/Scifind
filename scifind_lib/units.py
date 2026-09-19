"""Units: parsing, slugs, base resolution, HTML/LaTeX rendering + SI prefixes."""

import html
import json
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
from scifind_lib.util import anchor, request_cached, safe_json_list


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
        try: prefix = int(prefix)
        except (TypeError, ValueError): prefix = None
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
    return 10 ** exp


def _is_dimensionless(conn, quantity_id):
    row = conn.execute("SELECT * FROM quantity WHERE id = ?", (quantity_id,)).fetchone()
    if row is None:
        raise ValueError(f"unknown quantity: {quantity_id!r}")
    return all((row[c] or 0) == 0 for c in row.keys()
               if c.startswith("dim_") and c not in ("dim_symbol", "dim_position"))


def _canon_num(number):
    """Slug-safe numeric token, preserving fractional values."""
    f = float(number)
    if f == int(f):
        n = int(f)
        return f"m{-n}" if n < 0 else str(n)
    return ("m" if f < 0 else "") + str(abs(f)).replace(".", "p")


def _exp_str(number):
    f = float(number)
    return str(int(f)) if f == int(f) else str(f)


def _part_slug(unit_id, exponent, prefix):
    """One (unit_id, exponent, prefix) triple as its contribution to a canonical slug."""
    exp = float(exponent)
    token = unit_id if prefix is None else f"{unit_id}_p{_canon_num(prefix)}"
    forms = {1: token, -1: f"per_{token}", 2: f"{token}_squared", 3: f"{token}_cubed"}
    return forms.get(exp, f"{token}_e{_canon_num(exp)}")


def compound_unit_slug(quantity_id, unit_json):
    """Canonical id for (quantity_id, compound_unit JSON)."""
    entries = parse_compound_unit_parts(unit_json)
    if not entries:
        return ""
    try:
        canonical = [(uid, float(exp), prefix) for uid, exp, prefix in entries]
    except (TypeError, ValueError):
        return ""
    join = lambda parts: "_".join(_part_slug(uid, exp, prefix) for uid, exp, prefix in parts)
    if len(canonical) == 1:
        base = _part_slug(*canonical[0])
    else:
        num, den = split_numerator_denominator(canonical)
        base = f"{join(num)}_per_{join(den)}" if num and den else join(num + den)

    if not base or not quantity_id:
        return base
    return f"{base}_{quantity_id}"


def _lower_first_html(fragment):
    """Lowercase the first text character of an HTML fragment (tags preserved)."""
    return re.sub(r"((?:<[^>]*>|\s)*)(\S)",
                  lambda m: m.group(1) + m.group(2).lower(), fragment, count=1)


def format_compound_unit_html(
    json_text, unit_url=None, unit_name=None, locale="en-us", unit_quantity_map=None,
    quantity_pers=None, unit_accusatives=None, prefix_name=None,
):
    """Render compound_unit JSON as HTML with optional unit links."""
    split = _fraction_parts(json_text)
    if split is None:
        return ""
    numerators, denominators = split
    words = locale_unit_words(locale)
    render = lambda items, **kw: _render_unit_group(
        items, unit_url, unit_name, locale,
        unit_accusatives=unit_accusatives, prefix_name=prefix_name, **kw)
    num_html = render(numerators, decline=False, case="nom")
    if not denominators:
        return num_html
    if not num_html:
        return f"{words.get('reciprocal') or ''} {_lower_first_html(render(denominators, decline=False, case='nom'))}".strip()
    use_special, per_word = False, words.get("per") or ""
    if unit_quantity_map and quantity_pers:
        for uid, _e, _p in denominators:
            qid = unit_quantity_map.get(uid)
            override = localise(quantity_pers.get(qid) or "", locale) if qid else ""
            if override:
                use_special, per_word = True, override
                break
    return f"{num_html} {per_word} {render(denominators, use_special_exponents=use_special, case='acc')}"


def _render_symbol_items(items, unit_symbol, prefix_symbol):
    """(unit_id, exponent, prefix) triples as LaTeX factors joined with \\cdot."""
    def _factor(unit_id, exponent, prefix):
        sym = unit_symbol(unit_id) if unit_symbol else unit_id
        if prefix is not None and prefix_symbol:
            sym = prefix_symbol(prefix) + sym
        sym_latex = wrap_symbol_in_latex(sym) if sym else ""
        return sym_latex if exponent == 1 else f"{sym_latex}^{{{_exp_str(exponent)}}}"
    return " \\cdot ".join(_factor(*t) for t in items)


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


def compound_overwrite_cell(overwrite_text, unit_json, locale, *,
                            unit_names, unit_quantity_map=None,
                            quantity_pers=None, unit_accusatives=None,
                            prefix_names=None):
    """Table-cell HTML for a name overwrite: ``overwrite (linked parts)``."""
    linked_parts = format_compound_unit_html(
        unit_json, locale=locale,
        unit_name=unit_name_callback(unit_names),
        unit_url=lambda uid: f"/unit/{uid}" if uid in unit_names else None,
        unit_quantity_map=unit_quantity_map,
        quantity_pers=quantity_pers,
        unit_accusatives=unit_accusatives,
        prefix_name=prefix_name_callback(prefix_names or {}),
    ).strip()
    parts_text = strip_compound_html(linked_parts).strip()
    if linked_parts and parts_text \
            and parts_text.lower() != (overwrite_text or "").lower():
        return Markup(f"{html.escape(overwrite_text)} ({linked_parts})")
    return Markup(html.escape(overwrite_text or ""))


def _render_unit_group(items, url_func, name_func=None, locale="en-us",
                       use_special_exponents=False, unit_accusatives=None,
                       prefix_name=None, decline=True, case="nom"):
    """Render (unit_id, exponent, prefix) triples as HTML with natural-language exponents."""
    words = locale_unit_words(locale)
    fragments = []
    for i, (unit_id, exponent, prefix) in enumerate(items):
        label = name_func(unit_id) if name_func else unit_id
        # Feminine nouns carry a distinct accusative; masculine/neuter don't.
        acc = localise((unit_accusatives or {}).get(unit_id) or "", locale) if unit_accusatives else ""
        feminine = bool(acc) and acc.lower() != label.lower()
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
        if decline and acc:
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
            fragments.append(f"{attr} {pref_text}{(anchor(link, label) if link else html.escape(label))}")
            continue
        word = unit_exponent_word(exponent, locale, denominator=use_special_exponents)
        if not use_special_exponents and feminine and abs(exponent) == 3:
            word = words.get("cubed_f_acc" if case == "acc" else "cubed_f_nom") or word
        fragment = pref_text + (anchor(link, label) if link else html.escape(label))
        if word:
            fragment += " " + html.escape(word)
        fragments.append(fragment)
    return " ".join(fragments)


def _column_map(conn, table, column):
    return {r["id"]: r[column]
            for r in conn.execute(f"SELECT id, {column} FROM {table}").fetchall()}


def unit_name_map(conn, locale):
    return {r["id"]: localise(r["name"], locale)
            for r in conn.execute("SELECT id, name FROM unit").fetchall()}


def unit_symbol_map(conn):
    return _column_map(conn, "unit", "symbol")


def unit_quantity_map(conn):
    return _column_map(conn, "unit", "quantity_id")


def quantity_per_map(conn):
    """{quantity_id: per_overwrite JSON text} for denominator prepositions."""
    return _column_map(conn, "quantity", "per_overwrite")


def unit_accusative_map(conn):
    """{unit_id: name_accusative JSON text} for declined denominator names."""
    return _column_map(conn, "unit", "name_accusative")


def _build_compound_slug_map(conn):
    """{canonical id: row} for compound units (ids derived from parts, never stored)."""
    slug_map = {}
    for row in conn.execute("SELECT * FROM compound_unit").fetchall():
        row_dict = dict(row)
        if slug := compound_unit_slug(row_dict.get("quantity_id"), row_dict.get("unit")):
            slug_map.setdefault(slug, {"kind": "compound_unit", **row_dict, "id": slug})
    return slug_map


def _compound_slug_map(conn):
    return request_cached("_compound_slug_map", lambda: _build_compound_slug_map(conn))


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
    hit = compound_unit_by_slug(conn, slug) if slug else None
    return bool(hit and hit.get("is_base"))


def resolve_base_unit(conn, unit_id=None, compound_id=None, fallback_qid=None,
                      system="SI"):
    """Single base-unit resolve path: explicit unit/compound id, else base-with-fallback."""
    if unit_id:
        from scifind_lib.fetch import fetch_unit
        if row := fetch_unit(conn, unit_id):
            return {"kind": "unit", **dict(row)}
        raise ValueError(f"unknown unit: {unit_id!r}")
    elif compound_id:
        if base := compound_unit_by_slug(conn, compound_id, fallback_qid):
            return base
    if fallback_qid:
        return select_base_unit_with_fallback(conn, fallback_qid, system)
    return None


def resolve_constant_base(conn, constant, system="SI"):
    """Base row for a constant: explicit ``unit`` JSON wins, else quantity base, else None."""
    unit_json = constant.get("unit")
    qid = constant.get("quantity_id") or constant.get("related_quantity_id")
    if unit_json:
        slug = compound_unit_slug(qid, unit_json)
        if not slug:
            return None
        return compound_unit_by_slug(conn, slug, qid) or {
            "kind": "compound_unit", "id": slug, "unit": unit_json,
            "quantity_id": qid, "system": "SI"}
    return select_base_unit_with_fallback(conn, qid, system) if qid else None


def select_base_unit(conn, quantity_id, system):
    """Canonical base row for (quantity_id, system), or None; prefers compound rows, then unit rows."""
    if not quantity_id:
        return None
    return select_base_units_batched(conn, [quantity_id], system).get(quantity_id)


def select_base_unit_with_fallback(conn, quantity_id, system):
    """select_base_unit, falling back to SI if the chosen system has no base for this quantity."""
    if system != "SI":
        return select_base_unit(conn, quantity_id, system) or select_base_unit(conn, quantity_id, "SI")
    return select_base_unit(conn, quantity_id, system)


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
    if (missing := [qid for qid in qids if qid not in base_by_quantity]) and system != "SI":
        base_by_quantity.update(_load(missing, "SI"))
    return base_by_quantity


def unit_name_callback(names):
    """Capitalise-first unit-name lookup over a ``{id: name}`` map."""
    first = True

    def unit_name(uid):
        nonlocal first
        name = names.get(uid, uid).lower()
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
        prefix = exp if uid == part_uid else old_prefix
        entry = {"unit": uid, "exponent": e}
        if prefix is not None and (uid != part_uid or prefix != 0):
            entry["prefix"] = int(prefix)
        entries.append(entry)
    return entries


def _db_prefix_entries(conn, quantity_id):
    """{part_uid: {prefix_exp: non-base compound row}} for prefixed DB compounds."""
    from scifind_lib.fetch import fetch_compound_units

    found = {}
    for row in fetch_compound_units(conn, quantity_id, only_non_base=True):
        for u in safe_json_list(row["unit"]):
            if not isinstance(u, dict) or not u.get("unit") or u.get("prefix") is None:
                continue
            try:
                exp = int(u["prefix"])
            except (ValueError, TypeError):
                continue
            found.setdefault(u["unit"], {}).setdefault(exp, row)
    return found


def _prefixable_parts(conn, parts_with_prefix):
    """[(part_uid, part_exp, base_prefix)] for prefixable parts (SI bases + unprefixed SI compound parts)."""
    from scifind_lib.fetch import fetch_prefixable_base_units

    prefixable = fetch_prefixable_base_units(conn)
    base_prefix = {}
    for uid, _exp, prefix in parts_with_prefix:
        if prefix is not None and uid not in base_prefix:
            base_prefix[uid] = int(prefix)
    return [(uid, exp, base_prefix.get(uid, 0))
            for uid, exp, _prefix in parts_with_prefix if uid in prefixable]


def _prefix_exps(prefix_rows, base_prefix):
    """Prefix exps except the base's own, plus implicit 0 when the base is prefixed."""
    exps = [e for e in prefix_rows if e != base_prefix]
    if base_prefix != 0:
        # si_prefix table carries no 0 row.
        exps.append(0)
    return exps


def _finalize_rows(rows, fallback="si_base"):
    """Collapse flags + exp-desc sort for a prefix-table row list."""
    visible = set(DEFAULT_VISIBLE_EXPONENTS)
    for r in rows:
        # exp 0 is the unprefixed form and is always visible.
        r["collapsed"] = (not r.get("is_db_entry", False)) and (r["exp"] not in visible) and (r["exp"] != 0)
        r["payload_id"] = r["id"] or fallback
    rows.sort(key=lambda x: x["exp"], reverse=True)
    return rows


def inject_si_prefix_nodes(graph, conn, quantity_id, locale, *, unit_syms):
    """Inject synthetic SI-prefixed nodes for the prefix table; dimensionless skipped."""
    from scifind_lib.fetch import (
        fetch_si_prefixes,
        fetch_unit,
    )

    if _is_dimensionless(conn, quantity_id):
        return
    base = select_base_unit_with_fallback(conn, quantity_id, "SI")
    if not base:
        return
    prefixes = fetch_si_prefixes(conn)

    if base["kind"] == "unit":
        pref_base_id = base["id"]
        base_unit_row = fetch_unit(conn, pref_base_id)
        if base_unit_row is None:
            return
        base_symbol = base_unit_row["symbol"]
        for p in prefixes:
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
        prefix_rows = {int(p["id"]): p for p in prefixes}
        for part_uid, _part_exp, base_prefix in prefixable_parts:
            for exp in _prefix_exps(prefix_rows, base_prefix):
                pid = f"si_{exp}_{part_uid}"
                row = prefix_rows.get(exp)
                prefix_sym = "" if row is None else localise(row["symbol"], locale)
                graph.compound_rows[pid] = {
                    "id": pid,
                    "unit": json.dumps(_swapped_entries(parts_with_prefix, part_uid, exp)),
                    "symbol_overwrite": _build_compound_sym_latex(unit_syms, prefix_sym, part_uid, parts),
                    "system": "SI",
                    "quantity_id": quantity_id,
                    "is_base": 0,
                }


def _composition_key(parts_with_prefix):
    """Canonical composition key: sorted (unit_id, exponent, prefix-or-0) triples."""
    return tuple(sorted(
        (uid, int(exp), int(prefix) if prefix is not None else 0)
        for uid, exp, prefix in parts_with_prefix))


def _authoritative_compositions(conn, quantity_id):
    """Composition keys already covered by real unit/compound_unit rows."""
    keys = set()
    for r in conn.execute(
            "SELECT id FROM unit WHERE quantity_id = ?", (quantity_id,)):
        keys.add(((r["id"], 1, 0),))
    for r in conn.execute(
            "SELECT unit FROM compound_unit WHERE quantity_id = ?", (quantity_id,)):
        parts = parse_compound_unit_parts(r["unit"])
        if parts:
            keys.add(_composition_key(parts))
    return keys


def si_prefix_sections(conn, quantity_id, locale, *,
                       unit_names, unit_syms, prefix_names, prefix_syms,
                       quantity_pers=None, unit_accusatives=None):
    """Prefix-table sections for a quantity's SI base unit, or None for dimensionless."""
    from scifind_lib.fetch import (
        fetch_si_prefixes,
        fetch_unit,
    )

    if _is_dimensionless(conn, quantity_id):
        return None
    base = select_base_unit_with_fallback(conn, quantity_id, "SI")
    if not base:
        return None
    # A plain-unit base is a single unprefixed part, so both kinds share
    # the component-section path below.
    is_plain = base["kind"] == "unit"
    if is_plain:
        base_id = base["id"]
        base_unit_row = fetch_unit(conn, base_id)
        if base_unit_row is None:
            return None
        parts_with_prefix = [(base_id, 1, None)]
        parts = [(base_id, 1)]
        prefixable_parts = [(base_id, 1, 0)]
    else:
        parts_with_prefix = parse_compound_unit_parts(base["unit"])
        parts = [(uid, exp) for uid, exp, _prefix in parts_with_prefix]
        if not parts:
            return None
        prefixable_parts = _prefixable_parts(conn, parts_with_prefix)
        if not prefixable_parts:
            return None
    base_id = base.get("id")
    prefix_map = _db_prefix_entries(conn, quantity_id)
    prefix_rows = {int(p["id"]): p for p in fetch_si_prefixes(conn)}
    uqm = unit_quantity_map(conn)
    pers = quantity_pers or quantity_per_map(conn)
    accs = unit_accusatives or unit_accusative_map(conn)
    pname_cb = prefix_name_callback(prefix_names)
    url = lambda uid: f"/unit/{uid}" if uid in unit_names else None

    def html_for(unit_json):
        # unit_name_callback capitalises only the first unit it sees.
        return format_compound_unit_html(
            unit_json, locale=locale, unit_name=unit_name_callback(unit_names), unit_url=url,
            unit_quantity_map=uqm, quantity_pers=pers,
            unit_accusatives=accs, prefix_name=pname_cb,
        )

    if is_plain:
        base_symbol_latex = wrap_symbol_in_latex(base_unit_row["symbol"])
        base_name_html = localise(base_unit_row["name"], locale)
    else:
        base_symbol_latex = base.get("symbol_overwrite") or format_compound_unit_symbol(
            base["unit"],
            unit_symbol=lambda uid: unit_syms.get(uid, uid),
            prefix_symbol=lambda exp: prefix_syms.get(exp, str(exp)),
        )
        base_name_html = html_for(base["unit"])
    authoritative = _authoritative_compositions(conn, quantity_id)

    def make_component_section(part_uid, base_prefix):
        db_prefix_entries = prefix_map.get(part_uid, {})
        prefixed = [{
            "id": base_id if is_plain else f"{base_id}_{part_uid}_base",
            "exp": base_prefix,
            "symbol_latex": base_symbol_latex,
            "name": base_name_html,
            "label": strip_compound_html(base_name_html),
            "system_key": "detail.si_base",
            "link_unit_id": base_id if is_plain else None,
        }]
        for exp in _prefix_exps(prefix_rows, base_prefix):
            p = prefix_rows.get(exp)
            if exp in db_prefix_entries:
                db_entry = db_prefix_entries[exp]
                overwrite = localise(db_entry["name_overwrite"] or "", locale)
                if overwrite:
                    db_entry_name = compound_overwrite_cell(
                        overwrite, db_entry["unit"], locale, unit_names=unit_names,
                        unit_quantity_map=uqm, quantity_pers=pers,
                        unit_accusatives=accs, prefix_names=prefix_names,
                    )
                    db_entry_label = overwrite
                else:
                    db_entry_name = html_for(db_entry["unit"]) or html.escape(db_entry["id"])
                    db_entry_label = strip_compound_html(db_entry_name)
                if db_entry["symbol_overwrite"]:
                    db_sym_latex = db_entry["symbol_overwrite"]
                else:
                    db_parts = parse_compound_unit(db_entry["unit"])
                    if db_parts and p is not None:
                        db_sym_latex = _build_compound_sym_latex(
                            unit_syms, localise(p["symbol"], locale), part_uid, db_parts)
                    else:
                        db_sym_latex = format_compound_unit_symbol(
                            db_entry["unit"],
                            unit_symbol=lambda uid: unit_syms.get(uid, uid),
                            prefix_symbol=lambda e: prefix_syms.get(e, str(e)),
                        )
                prefixed.append({
                    "id": db_entry["id"],
                    "exp": exp,
                    "symbol_latex": db_sym_latex,
                    "name": db_entry_name,
                    "label": db_entry_label,
                    "system_key": None,
                    "link_unit_id": None,
                    "is_db_entry": True,
                })
                continue
            prefix_sym = "" if p is None else localise(p["symbol"], locale)
            swapped = _swapped_entries(parts_with_prefix, part_uid, exp)
            # A real row already covering this composition wins; skip the twin.
            if _composition_key(
                    (u["unit"], u["exponent"], u.get("prefix")) for u in swapped
                    ) in authoritative:
                continue
            pref_name_html = html_for(json.dumps(swapped))
            prefixed.append({
                "id": f"si_{exp}" if is_plain else f"si_{exp}_{part_uid}",
                "exp": exp,
                "symbol_latex": _build_compound_sym_latex(unit_syms, prefix_sym, part_uid, parts),
                "name": pref_name_html,
                "label": strip_compound_html(pref_name_html),
                "system_key": None,
                "link_unit_id": None,
            })
        return _finalize_rows(prefixed, base_id if is_plain else f"{base_id}_{part_uid}")

    sections = {}
    for part_uid, _part_exp, base_prefix in prefixable_parts:
        if is_plain:
            label = base_name_html
        else:
            part_unit_row = fetch_unit(conn, part_uid)
            part_name = localise(part_unit_row["name"], locale) if part_unit_row else part_uid
            label = part_name
        sections[part_uid] = {
            "component": part_uid,
            "label": label,
            "rows": make_component_section(part_uid, base_prefix),
        }

    return sections
