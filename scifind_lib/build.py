"""build_create_sql — generate the two INSERT SQL strings for /create."""
# Licensed under the LICENSE file in the project root.

import json
import re

from scifind_lib.db import sql_literal as sql_str
from scifind_lib.dimensions import format_number
from scifind_lib.parser import parse_equation


QTY_OVERRIDE_FIELDS = ("label", "symbol_overwrite", "quantity_name_overwrite")


def build_create_sql(
    conn, name_en, topic, difficulty, equation, overrides=None, description=None,
    links=None, translations=None, formula_id=None,
):
    """Build (formula_sql, token_sql) for a brand-new formula.

    Raises ValueError on missing fields or an unparseable equation.
    """
    if not name_en or not name_en.strip():
        raise ValueError("name is required")
    if not topic or not topic.strip():
        raise ValueError("topic is required")
    if not equation or not equation.strip():
        raise ValueError("equation is required")
    difficulty = int(difficulty) if difficulty not in (None, "") else 2
    if difficulty < 1 or difficulty > 10:
        raise ValueError("difficulty must be 1..10")

    formula_id = (formula_id or "").strip()
    if formula_id:
        if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", formula_id):
            raise ValueError(
                "formula id may only contain lowercase letters and digits "
                "separated by single underscores"
            )
    else:
        formula_id = re.sub(r"[^a-z0-9]+", "_", name_en.strip().lower()).strip("_")
    if not formula_id:
        raise ValueError("name must contain at least one alphanumeric character")

    tokens = parse_equation(conn, equation)
    overrides = overrides or {}
    translations = translations or {}

    def add_locale(blob, value, locale):
        """Return a JSON dict string with `locale: value` merged into `blob`."""
        obj = {}
        if blob:
            try:
                parsed = json.loads(blob)
                if isinstance(parsed, dict):
                    obj = parsed
            except (ValueError, TypeError):
                obj = {}
        obj[locale] = value
        return json.dumps(obj, ensure_ascii=False)

    name_json = json.dumps({"en-us": name_en.strip()}, ensure_ascii=False)
    desc_json = json.dumps({"en-us": description}, ensure_ascii=False) if description else None
    links_json = json.dumps(links, ensure_ascii=False) if links else None
    tr_overrides_by_loc = {}
    if translations:
        for loc, tr in translations.items():
            if not isinstance(tr, dict) or loc == "en-us":
                continue
            t_name = tr.get("name")
            if t_name:
                name_json = add_locale(name_json, t_name.strip(), loc)
            t_desc = tr.get("description")
            if t_desc:
                desc_json = add_locale(desc_json, t_desc, loc)
            t_ov = tr.get("overrides") or {}
            if t_ov:
                tr_overrides_by_loc[loc] = t_ov

    formula_sql = (
        "INSERT OR IGNORE INTO formula (id, name, topic, difficulty, description, links) VALUES\n"
        f"({sql_str(formula_id)}, {sql_str(name_json)}, "
        f"{sql_str(topic)}, {difficulty}, {sql_str(desc_json)}, "
        f"{sql_str(links_json)});"
    )

    def i18n_override(field, key):
        ov = overrides.get(key) or {}
        base = ov.get(field)
        if base is None:
            # Accept the shorter override-field vocabulary used by the
            # /create form ("symbol", "name") alongside the token-column
            # names ("symbol_overwrite", "quantity_name_overwrite").
            alias = {"symbol_overwrite": "symbol",
                     "quantity_name_overwrite": "name"}.get(field)
            if alias:
                base = ov.get(alias)
        per_locale = {loc: (t_ov.get(key) or {}).get(field)
                      for loc, t_ov in tr_overrides_by_loc.items()
                      if (t_ov.get(key) or {}).get(field)}
        if not base and not per_locale:
            return "NULL"
        obj = {}
        if base:
            obj["en-us"] = base
        obj.update(per_locale)
        return sql_str(json.dumps(obj, ensure_ascii=False))

    rows = []
    for pos, tok in enumerate(tokens, start=1):
        kind = tok["token_kind"]
        if kind == "number":
            rows.append(
                f"({sql_str(formula_id)}, {pos}, 'number', "
                f"NULL, NULL, NULL, {tok['value']}, NULL, NULL, NULL)"
            )
        elif kind == "quantity":
            qid = tok["quantity_id"]
            key = qid + "|" + (tok.get("label") or "") + "|" + str(pos)
            overrides_sql = ", ".join(
                i18n_override(field, key) for field in QTY_OVERRIDE_FIELDS
            )
            rows.append(
                f"({sql_str(formula_id)}, {pos}, 'quantity', "
                f"{sql_str(qid)}, NULL, NULL, NULL, {overrides_sql})"
            )
        elif kind == "constant":
            rows.append(
                f"({sql_str(formula_id)}, {pos}, 'constant', "
                f"NULL, {sql_str(tok['constant_id'])}, NULL, NULL, NULL, NULL, NULL)"
            )
        else:  # operator
            op_id = tok["operator_id"]
            if op_id in ("paren_open", "paren_close"):
                raise ValueError("unbalanced parentheses")
            rows.append(
                f"({sql_str(formula_id)}, {pos}, 'operator', "
                f"NULL, NULL, {sql_str(op_id)}, NULL, NULL, NULL, NULL)"
            )

    token_sql = (
        "INSERT OR IGNORE INTO formula_token\n"
        "  (formula_id, position, token_kind, quantity_id, constant_id,\n"
        "   operator_id, value, label, symbol_overwrite, quantity_name_overwrite)\n"
        "VALUES\n"
        + ",\n".join(rows)
        + ";"
    )
    return formula_sql, token_sql