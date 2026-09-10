"""Persistence: create-SQL builder + full-database export."""

import csv
import io
import json
import re
import zipfile
from pathlib import Path

from scifind_lib.constants import PROJECT_DIR, is_slug
from scifind_lib.db import insert_statement, sql_literal
from scifind_lib.formula import dimension_columns
from scifind_lib.parser import parse_equation, quantity_token_key

QTY_OVERRIDE_FIELDS = ("symbol_overwrite", "name_overwrite")  # schema order
_QTY_OVERRIDE_ALIASES = {"symbol_overwrite": "symbol", "name_overwrite": "name"}
FORMULA_COLUMNS = ["id", "name", "topic", "difficulty", "description", "links"]
TOKEN_COLUMNS = [
    "formula_id", "position", "token_kind", "quantity_id", "constant_id",
    "operator_id", "value", "symbol_overwrite", "name_overwrite",  # schema order
]


def resolve_formula_id(name_en, formula_id=""):
    """Validate an explicit id or slugify it from the English name."""
    formula_id = (formula_id or "").strip()
    if formula_id:
        if not is_slug(formula_id):
            raise ValueError(
                "formula id may only contain lowercase letters and digits "
                "separated by single underscores"
            )
        return formula_id
    slug = re.sub(r"[^a-z0-9]+", "_", name_en.strip().lower()).strip("_")
    if not slug:
        raise ValueError("name must contain at least one alphanumeric character")
    return slug


def merge_locale_value(blob, value, locale):
    """Return `blob` (a JSON object string) with `locale` set to `value`."""
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


def build_i18n_override_value(overrides, tr_overrides_by_loc, field, key):
    """None or JSON {locale: value} string for one quantity token override."""
    ov = overrides.get(key) or {}
    base = ov.get(field)
    if base is None:
        base = ov.get(_QTY_OVERRIDE_ALIASES[field])
    per_locale = {loc: (t_ov.get(key) or {}).get(field)
                  for loc, t_ov in tr_overrides_by_loc.items()
                  if (t_ov.get(key) or {}).get(field)}
    if not base and not per_locale:
        return None
    obj = {}
    if base:
        obj["en-us"] = base
    obj.update(per_locale)
    return json.dumps(obj, ensure_ascii=False)


def token_row_values(formula_id, pos, tok, overrides, tr_overrides_by_loc):
    """Value list (parallel to TOKEN_COLUMNS) for one parsed token."""
    kind = tok["token_kind"]
    if kind == "number":
        return [formula_id, pos, "number", None, None, None, tok["value"], None, None]
    if kind == "quantity":
        key = quantity_token_key(tok["quantity_id"], tok.get("label"), pos)
        return (
            [formula_id, pos, "quantity", tok["quantity_id"], None, None, None]
            + [build_i18n_override_value(overrides, tr_overrides_by_loc, f, key)
               for f in QTY_OVERRIDE_FIELDS]
        )
    if kind == "constant":
        return [formula_id, pos, "constant", None, tok["constant_id"], None, None, None, None]
    op_id = tok["operator_id"]
    if op_id in ("paren_open", "paren_close"):
        raise ValueError("unbalanced parentheses")
    return [formula_id, pos, "operator", None, None, op_id, None, None, None]


def build_create_sql(
    conn, name_en, topic, difficulty, equation, overrides=None, description=None,
    links=None, translations=None, formula_id=None,
):
    """Build (formula_sql, token_sql) for a brand-new formula."""
    if not name_en or not name_en.strip():
        raise ValueError("name is required")
    if not topic or not topic.strip():
        raise ValueError("topic is required")
    if not equation or not equation.strip():
        raise ValueError("equation is required")
    difficulty = int(difficulty) if difficulty not in (None, "") else 2
    if difficulty < 1 or difficulty > 10:
        raise ValueError("difficulty must be 1..10")

    formula_id = resolve_formula_id(name_en, formula_id)

    tokens = parse_equation(conn, equation)
    overrides = overrides or {}
    translations = translations or {}

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
                name_json = merge_locale_value(name_json, t_name.strip(), loc)
            t_desc = tr.get("description")
            if t_desc:
                desc_json = merge_locale_value(desc_json, t_desc, loc)
            t_ov = tr.get("overrides") or {}
            if t_ov:
                tr_overrides_by_loc[loc] = t_ov

    formula_sql = insert_statement(
        "formula", FORMULA_COLUMNS,
        [formula_id, name_json, topic, difficulty, desc_json, links_json],
    )

    rows = [
        token_row_values(formula_id, pos, tok, overrides, tr_overrides_by_loc)
        for pos, tok in enumerate(tokens, start=1)
    ]

    token_sql = (
        "INSERT OR IGNORE INTO formula_token\n"
        f"  ({', '.join(TOKEN_COLUMNS)})\n"
        "VALUES\n"
        + ",\n".join(f"({', '.join(sql_literal(v) for v in row)})" for row in rows)
        + ";"
    )
    return formula_sql, token_sql


EXPORT_TABLE_ORDER = [
    "formula", "formula_token", "formula_relation",
    "operator", "constant", "compound_unit", "quantity", "unit",
]

EXPORT_TABLE_COLUMNS = {
    "formula": ["id", "name", "topic", "difficulty", "description", "links"],
    "formula_token": [
        "formula_id", "position", "token_kind",
        "quantity_id", "constant_id", "operator_id",
        "value", "symbol_overwrite", "name_overwrite",
    ],
    "formula_relation": ["formula_id", "related_id", "relation_type", "description"],
    "operator": ["id", "symbol", "arity", "precedence", "associativity", "operator_type"],
    "constant": ["id", "name", "symbol", "difficulty", "description",
                 "links", "value", "quantity_id", "unit_id", "compound_unit_id"],
    "compound_unit": [
        "quantity_id", "name_overwrite", "symbol_overwrite", "unit",
        "system", "is_base",
    ],
    "quantity": [
        "id", "name", "symbol", "symbol_overwrite", "topic",
        "difficulty", "description", "links",
        "hidden",
    ],
    "unit": [
        "id", "name", "symbol", "quantity_id", "system", "is_base",
        "reference_unit_id", "factor", "is_factor_reciprocal",
        "constant_id", "constant_operator_id", "offset",
    ],
}


def _iter_export_tables(conn):
    """Yield (table_name, columns, rows) for all tables in export order."""
    for table in EXPORT_TABLE_ORDER:
        columns = list(EXPORT_TABLE_COLUMNS[table])
        if table == "quantity":
            insert_at = columns.index("hidden") + 1
            columns[insert_at:insert_at] = dimension_columns()
        rows = conn.execute(
            f"SELECT {','.join(columns)} FROM {table} ORDER BY rowid"
        ).fetchall()
        yield table, columns, [[r[c] for c in columns] for r in rows]


def export_to_csv(conn):
    """Export all tables to a single CSV string with section headers."""
    buffer = io.StringIO()
    for table, columns, rows in _iter_export_tables(conn):
        buffer.write(f"=== {table} ===\n")
        writer = csv.writer(buffer)
        writer.writerow(columns)
        writer.writerows(rows)
        buffer.write("\n")
    return buffer.getvalue()


def export_to_csv_directory(conn, directory):
    """Export each table to a separate CSV file in a directory."""
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    for table, columns, rows in _iter_export_tables(conn):
        with open(out_dir / f"{table}.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)


def export_to_csv_zip(conn):
    """Export each table to a same-named CSV inside a ZIP archive (bytes)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for table, columns, rows in _iter_export_tables(conn):
            text = io.StringIO()
            writer = csv.writer(text)
            writer.writerow(columns)
            writer.writerows(rows)
            zf.writestr(f"{table}.csv", text.getvalue())
    return buffer.getvalue()


def export_to_xlsx(conn, output):
    """Export all tables as sheets in an XLSX workbook (file path or file-like)."""
    from openpyxl import Workbook
    workbook = Workbook()
    for i, (table, columns, rows) in enumerate(_iter_export_tables(conn)):
        sheet = workbook.active if i == 0 else workbook.create_sheet(title=table[:31])
        if i == 0:
            sheet.title = table[:31]
        sheet.append(columns)
        for row in rows:
            sheet.append(row)
    workbook.save(output)


def export_to_ods(conn, output):
    """Export all tables as sheets in an ODS spreadsheet (file path or file-like)."""
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableRow, TableCell
    from odf.text import P
    document = OpenDocumentSpreadsheet()
    for table, columns, rows in _iter_export_tables(conn):
        sheet = Table(name=table[:31])
        document.spreadsheet.addElement(sheet)
        for row_data in [columns] + rows:
            row = TableRow()
            for value in row_data:
                cell = TableCell()
                cell.addElement(P(text=str(value) if value is not None else ""))
                row.addElement(cell)
            sheet.addElement(row)
    document.save(output)


def build_formula_insert_sql(conn, formula_id):
    """Build (formula_sql, token_sql) for an existing formula, including its relation rows."""

    def build_insert_sql(table, where):
        columns = list(EXPORT_TABLE_COLUMNS[table])
        rows = conn.execute(
            f"SELECT {','.join(columns)} FROM {table} WHERE {where} ORDER BY rowid",
            (formula_id,) * where.count("?"),
        ).fetchall()
        return "".join(
            insert_statement(table, columns, [row[c] for c in columns]) + "\n"
            for row in rows
        )

    formula_sql = build_insert_sql("formula", "id = ?")
    token_sql = (
        build_insert_sql("formula_token", "formula_id = ?")
        + build_insert_sql("formula_relation", "formula_id = ? OR related_id = ?")
    )
    return formula_sql, token_sql


def export_to_sql(conn):
    """Export the schema and all table contents as a SQL script string."""
    schema = (PROJECT_DIR / "schema.sql").read_text(encoding="utf-8")
    out = [
        "-- Scifind SQL export\n",
        "-- Restore with: sqlite3 scifind.db < this_file.sql\n",
        "\n",
        schema.rstrip("\n"),
        "\nPRAGMA foreign_keys = OFF;\n",
        "BEGIN TRANSACTION;\n",
    ]
    for table, columns, rows in _iter_export_tables(conn):
        out.append(f"\n-- table: {table}\n")
        for row in rows:
            out.append(insert_statement(table, columns, row) + "\n")
    out.append("\nCOMMIT;\n")
    return "".join(out)

# Single source of truth: export reuses the canonical token column order.
EXPORT_TABLE_COLUMNS["formula_token"] = TOKEN_COLUMNS
EXPORT_TABLE_COLUMNS["formula"] = FORMULA_COLUMNS
