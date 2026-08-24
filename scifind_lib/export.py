"""CSV / XLSX / ODS / SQL export of all tables."""
# Licensed under the LICENSE file in the project root.

import csv
import io
from pathlib import Path

from scifind_lib.constants import PROJECT_DIR
from scifind_lib.db import sql_literal
from scifind_lib.dimensions import dimension_columns


EXPORT_TABLE_ORDER = [
    "formula", "formula_token", "formula_relation",
    "operator", "constant", "quantity", "unit",
]

EXPORT_TABLE_COLUMNS = {
    "formula": ["id", "name", "topic", "difficulty", "description", "links"],
    "formula_token": [
        "formula_id", "position", "token_kind",
        "quantity_id", "constant_id", "operator_id",
        "value", "label", "symbol_overwrite", "quantity_name_overwrite",
    ],
    "formula_relation": ["formula_id", "related_id", "relation_type", "description"],
    "operator": ["id", "symbol", "math", "arity", "precedence", "associativity", "operator_type"],
    "constant": ["id", "name", "symbol", "value", "default_unit"],
    "quantity": [
        "id", "name", "symbol", "symbol_overwrite", "topic",
        "difficulty", "description", "links", "default_unit",
    ],
    "unit": [
        "id", "name", "symbol", "quantity_id", "default_unit", "unit_system",
        "factor", "latex_factor", "offset",
    ],
}


def _each_table(conn):
    """Yield (table_name, columns, rows) for all tables in export order."""
    for table in EXPORT_TABLE_ORDER:
        columns = list(EXPORT_TABLE_COLUMNS[table])
        if table == "quantity":
            columns[9:9] = dimension_columns()
        rows = conn.execute(
            f"SELECT {','.join(columns)} FROM {table} ORDER BY rowid"
        ).fetchall()
        yield table, columns, [[r[c] for c in columns] for r in rows]


def export_to_csv(conn):
    """Export all tables to a single CSV string with section headers."""
    buffer = io.StringIO()
    for table, columns, rows in _each_table(conn):
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
    for table, columns, rows in _each_table(conn):
        with open(out_dir / f"{table}.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)


def export_to_xlsx(conn, output):
    """Export all tables as sheets in an XLSX workbook (file path or file-like)."""
    from openpyxl import Workbook
    workbook = Workbook()
    first = True
    for table, columns, rows in _each_table(conn):
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
    for table, columns, rows in _each_table(conn):
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
    for table, columns, rows in _each_table(conn):
        col_list = ", ".join(columns)
        out.append(f"\n-- table: {table}\n")
        for row in rows:
            values = ", ".join(sql_literal(v) for v in row)
            out.append(
                f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({values});\n"
            )
    out.append("\nCOMMIT;\n")
    return "".join(out)