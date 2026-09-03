"""CSV / XLSX / ODS / SQL export of all tables."""

import csv
import io
from pathlib import Path

from scifind_lib.constants import PROJECT_DIR
from scifind_lib.db import sql_literal
from scifind_lib.dimensions import dimension_columns


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
    "compound_unit": ["id", "quantity_id", "name_overwrite", "symbol_overwrite", "unit", "system", "is_base"],
    "quantity": [
        "id", "name", "symbol", "symbol_overwrite", "topic",
        "difficulty", "description", "links",
        "hidden",
    ],
    "unit": [
        "id", "name", "symbol", "quantity_id", "system", "is_base",
        "factor", "offset",
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


def export_to_xlsx(conn, output):
    """Export all tables as sheets in an XLSX workbook (file path or file-like)."""
    from openpyxl import Workbook
    workbook = Workbook()
    first = True
    for table, columns, rows in _iter_export_tables(conn):
        if first:
            sheet = workbook.active
            sheet.title = table[:31]
            first = False
        else:
            sheet = workbook.create_sheet(title=table[:31])
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
    """Build (formula_sql, token_sql) for an existing formula, mirroring
    build_create_sql's two-block layout (the token block also carries any
    formula_relation rows pointing at the formula)."""

    def build_insert_sql(table, where):
        columns = list(EXPORT_TABLE_COLUMNS[table])
        rows = conn.execute(
            f"SELECT {','.join(columns)} FROM {table} WHERE {where} ORDER BY rowid",
            (formula_id,) * where.count("?"),
        ).fetchall()
        if not rows:
            return ""
        col_list = ", ".join(columns)
        out = []
        for row in rows:
            values = ", ".join(sql_literal(row[c]) for c in columns)
            out.append(
                f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({values});\n"
            )
        return "".join(out)

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
        col_list = ", ".join(columns)
        out.append(f"\n-- table: {table}\n")
        for row in rows:
            values = ", ".join(sql_literal(v) for v in row)
            out.append(
                f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({values});\n"
            )
    out.append("\nCOMMIT;\n")
    return "".join(out)