#!/usr/bin/env python3
"""
Scifind — CLI tool for the structured physics formula database.

Usage:
    formula init                            Create and seed the database
    formula list [options]                  List formulas
    formula show <id>                       Show formula details
    formula search <query>                  Full-text search
    formula quantities [--formula F]        List quantities
    formula quantity <id>                   Show quantity details
    formula units [--quantity Q]            List units
    formula browse                          Browse branch/topic tree
    formula export [options]                Export all tables
    formula import <file>                   Import tables from file
"""

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path

_project_dir = Path(__file__).resolve().parent
if str(_project_dir) not in sys.path:
    sys.path.insert(0, str(_project_dir))

from formula_lib import (
    db_path, get_conn, en, rebuild_fts, migrate_db,
    render_formula_items, render_dimensions, dims_from_row, DIM_ORDER, DIM_COLS,
    render_default_unit_html, parse_default_unit_json,
    get_formula_detail, get_formula_items,
    get_formula_conditions, get_formula_relations, get_formula_quantities,
    get_quantity_detail, get_quantity_units, get_quantity_formulas,
    get_formulas_by_science,
    search,
    export_csv, export_csv_dir, export_xlsx, export_ods,
    import_csv, import_csv_dir, import_xlsx, import_ods,
)

SCRIPT_DIR = _project_dir


# Init

def cmd_init(args):
    conn = get_conn()
    schema = (SCRIPT_DIR / "schema.sql").read_text()
    conn.executescript(schema)
    seed = (SCRIPT_DIR / "seed.sql").read_text()
    conn.executescript(seed)
    views = (SCRIPT_DIR / "views.sql").read_text()
    conn.executescript(views)
    units_seed = (SCRIPT_DIR / "seed_units.sql")
    if units_seed.exists():
        conn.executescript(units_seed.read_text())
    migrate_db(conn)
    n = rebuild_fts(conn)
    changes = conn.total_changes
    conn.close()
    print(f"Database initialised at {db_path()}")
    print(f"  {changes} SQL statements executed, {n} formulas indexed for search.")


# List

def cmd_list(args):
    conn = get_conn()
    where = []
    params = []
    if args.branch:
        where.append("json_extract(f.branch, '$.en-us') = ?")
        params.append(args.branch)
    if args.topic:
        where.append("json_extract(f.topic, '$.en-us') = ?")
        params.append(args.topic)
    if args.difficulty:
        parts = args.difficulty.split("-")
        if len(parts) == 1:
            where.append("f.difficulty = ?")
            params.append(int(parts[0]))
        else:
            where.append("f.difficulty BETWEEN ? AND ?")
            params.extend([int(parts[0]), int(parts[1])])

    sql = """
        SELECT f.id, json_extract(f.name, '$.en-us') AS name_en,
               json_extract(f.branch, '$.en-us') AS branch_en,
               json_extract(f.topic, '$.en-us') AS topic_en,
               f.difficulty
        FROM formula f
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY f.branch, f.topic, f.difficulty, f.id"

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    if not rows:
        print("No formulas found.")
        return
    by_branch = {}
    for r in rows:
        b = r["branch_en"] or "Uncategorised"
        t = r["topic_en"] or "General"
        by_branch.setdefault(b, {}).setdefault(t, []).append(r)
    for branch, topics in by_branch.items():
        print(f"\n\u2500\u2500 \033[1m{branch}\033[0m \u2500\u2500")
        for topic, formulas in topics.items():
            print(f"  \033[33m{topic}\033[0m:")
            for f in formulas:
                s = "\u2605" * min(f["difficulty"], 5) + "\u2606" * max(0, 5 - min(f["difficulty"], 5))
                print(f"    {f['id']:40s} {s}  {f['name_en']}")
    print()


# Show

def cmd_show(args):
    conn = get_conn()
    row = get_formula_detail(conn, args.id)
    if not row:
        print(f"Formula '{args.id}' not found.")
        sys.exit(1)
    items = get_formula_items(conn, args.id)
    conds = get_formula_conditions(conn, args.id)
    relations = get_formula_relations(conn, args.id)
    quantities = get_formula_quantities(conn, args.id)
    conn.close()

    name = en(row["name"])
    desc = en(row["description"])
    diff = row["difficulty"]
    branch = en(row["branch"])
    topic = en(row["topic"])
    stars = "\u2605" * min(diff, 5) + "\u2606" * max(0, 5 - min(diff, 5))

    print(f"\n  \033[1m{name}\033[0m  {stars}")
    if branch:
        print(f"  \033[33m{branch}\033[0m \u2192 \033[36m{topic}\033[0m  (difficulty {diff}/10)")

    if items:
        latex = render_formula_items(items)
        print(f"\n  \033[90m$$\033[0m")
        print(f"  \033[97m{latex}\033[0m")
        print(f"  \033[90m$$\033[0m")

    if desc:
        wrapped = textwrap.fill(desc, width=72, initial_indent="  ", subsequent_indent="  ")
        print(f"\n  \033[2m{wrapped}\033[0m")

    if conds:
        print(f"\n  \033[1mConditions:\033[0m")
        for c in conds:
            state = "\u2611" if c["default_on"] else "\u2610"
            print(f"    {state} {c['name_en']}  \u2192  {c['replacement_formula_id']}")

    if quantities:
        print(f"\n  \033[1mQuantities:\033[0m")
        for q in quantities:
            print(f"    ${q['symbol']}$  {q['name_en']}  (\033[90m{q['id']}\033[0m)")

    if relations:
        print(f"\n  \033[1mRelated:\033[0m")
        for r in relations:
            print(f"    \033[90m{r['relation_type']}\033[0m \u2192 {r['related_id']}  ({r['related_name']})")
    print()


# Search

def cmd_search(args):
    conn = get_conn()
    rows = search(conn, args.query, args.limit or 20)
    conn.close()
    if not rows:
        print("No results.")
        return
    print(f"\n  \033[1m{len(rows)} result(s)\033[0m for \033[33m'{args.query}'\033[0m\n")
    for r in rows:
        if r["kind"] == "formula":
            s = "\u2605" * min(r["difficulty"], 5) + "\u2606" * max(0, 5 - min(r["difficulty"], 5))
            print(f"  \033[36mformula \033[0m{r['id']:40s} {s}  {r['name_en']}")
        elif r["kind"] == "quantity":
            print(f"  \033[32mquantity\033[0m {r['id']:40s}        {r['name_en']} ($\\{r['extra']}$)")
        elif r["kind"] == "unit":
            print(f"  \033[33munit    \033[0m{r['id']:40s}        {r['name_en']} ($\\{r['extra']}$)")
    print()


# Quantities list

def cmd_quantities(args):
    conn = get_conn()
    if args.formula:
        rows = get_formula_quantities(conn, args.formula)
    else:
        rows = conn.execute("""
            SELECT q.id, q.symbol, json_extract(q.name, '$.en-us') AS name_en,
                   q.default_unit, q.dim_M, q.dim_L, q.dim_T, q.dim_I, q.dim_\u0398, q.dim_N, q.dim_J
            FROM quantity q ORDER BY q.id
        """).fetchall()
    conn.close()
    if not rows:
        print("No quantities found.")
        return
    print(f"\n  \033[1mQuantities\033[0m" + (f" for \033[33m{args.formula}\033[0m" if args.formula else "") + "\n")
    for q in rows:
        dims = render_dimensions(*dims_from_row(q))
        unit_parts = parse_default_unit_json(q["default_unit"])
        unit_str = "\u00b7".join(f"{uid}^{exp}" for uid, exp in unit_parts) if unit_parts else ""
        print(f"  ${q['symbol']}$  \033[1m{q['name_en']}\033[0m  (\033[90m{q['id']}\033[0m)")
        print(f"      Dimensions: \033[2m{dims}\033[0m" + (f"  default unit: {unit_str}" if unit_str else ""))
    print()


# Quantity detail

def cmd_quantity(args):
    conn = get_conn()
    q = get_quantity_detail(conn, args.id)
    if not q:
        print(f"Quantity '{args.id}' not found.")
        sys.exit(1)
    units = get_quantity_units(conn, args.id)
    formulas = get_quantity_formulas(conn, args.id)
    conn.close()

    name = en(q["name"])
    desc = en(q["description"])
    dims = render_dimensions(q["dim_M"], q["dim_L"], q["dim_T"], q["dim_I"], q["dim_\u0398"], q["dim_N"], q["dim_J"])
    unit_parts = parse_default_unit_json(q["default_unit"])
    unit_str = "\u00b7".join(f"{uid}^{exp}" for uid, exp in unit_parts) if unit_parts else ""

    print(f"\n  \033[1m${q['symbol']}$ \u2014 {name}\033[0m  (\033[90m{q['id']}\033[0m)")
    if dims:
        print(f"  Dimensions: \033[2m{dims}\033[0m")
    if unit_str:
        print(f"  Default unit: {unit_str}")

    if desc:
        wrapped = textwrap.fill(desc, width=72, initial_indent="  ", subsequent_indent="  ")
        print(f"\n  \033[2m{wrapped}\033[0m")

    if units:
        print(f"\n  \033[1mUnits:\033[0m")
        for u in units:
            s = "\u2713" if u["default_unit"] else " "
            off = f" + {u['offset']}" if u["offset"] else ""
            print(f"    [{s}] ${u['symbol']}$  {u['id']}  [{u['unit_system'] or 'any'}]  \u00d7{u['factor']}{off} \u2192 SI")

    if formulas:
        print(f"\n  \033[1mAppears in formulas:\033[0m")
        for f in formulas:
            s = "\u2605" * min(f["difficulty"], 5) + "\u2606" * max(0, 5 - min(f["difficulty"], 5))
            print(f"    {f['id']:40s} {s}  {f['name_en']}")
    print()


# Units

def cmd_units(args):
    conn = get_conn()
    if args.quantity:
        rows = conn.execute("""
            SELECT u.*, json_extract(q.name, '$.en-us') AS quantity_name
            FROM unit u JOIN quantity q ON q.id = u.quantity_id
            WHERE u.quantity_id = ?
            ORDER BY u.default_unit DESC, u.unit_system
        """, (args.quantity,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT u.*, json_extract(q.name, '$.en-us') AS quantity_name
            FROM unit u JOIN quantity q ON q.id = u.quantity_id
            ORDER BY q.id, u.default_unit DESC, u.unit_system
        """).fetchall()
    conn.close()
    if not rows:
        print("No units found.")
        return
    print(f"\n  \033[1mUnits\033[0m" + (f" for \033[33m{args.quantity}\033[0m" if args.quantity else "") + "\n")
    for u in rows:
        s = "\u2713" if u["default_unit"] else " "
        off = f" + {u['offset']}" if u["offset"] else ""
        print(f"  [{s}] ${u['symbol']}$  \033[1m{u['id']}\033[0m  [{u['unit_system'] or 'any'}]  \u00d7{u['factor']}{off} \u2192 SI")
    print()


# Browse

def cmd_browse(args):
    conn = get_conn()
    rows = conn.execute("""
        SELECT f.id, json_extract(f.name, '$.en-us') AS name_en,
               json_extract(f.branch, '$.en-us') AS branch_en,
               json_extract(f.topic, '$.en-us') AS topic_en, f.difficulty
        FROM formula f ORDER BY f.branch, f.topic, f.difficulty, f.id
    """).fetchall()
    conn.close()
    tree = {}
    for r in rows:
        b = r["branch_en"] or "Uncategorised"
        t = r["topic_en"] or "General"
        tree.setdefault(b, {}).setdefault(t, []).append(r)
    for branch, topics in tree.items():
        print(f"\n  \033[1m{branch}\033[0m")
        for topic, formulas in topics.items():
            print(f"    \033[33m{topic}\033[0m")
            for f in formulas:
                s = "\u2605" * min(f["difficulty"], 5) + "\u2606" * max(0, 5 - min(f["difficulty"], 5))
                print(f"      {f['id']:38s} {s}  {f['name_en']}")
    print()


# Export

def cmd_export(args):
    conn = get_conn()
    fmt = (args.format or "csv").lower()

    if fmt == "csvdir":
        d = args.output or "."
        export_csv_dir(conn, d)
        print(f"Exported per-table CSV files to {d}/")
    elif fmt in ("xlsx", "ods"):
        out = args.output or f"formulas.{fmt}"
        if fmt == "xlsx":
            export_xlsx(conn, out)
        else:
            export_ods(conn, out)
        print(f"Exported to {out}")
    else:
        data = export_csv(conn)
        conn.close()
        if args.output:
            Path(args.output).write_text(data)
            print(f"Exported to {args.output}")
        else:
            sys.stdout.write(data)
    conn.close()


# Import

def cmd_import(args):
    conn = get_conn()
    migrate_db(conn)
    path = Path(args.file)
    ext = path.suffix.lower()

    if path.is_dir():
        counts = import_csv_dir(conn, str(path))
    elif ext == ".xlsx":
        counts = import_xlsx(conn, str(path))
    elif ext == ".ods":
        counts = import_ods(conn, str(path))
    else:
        data = path.read_text() if args.file != "-" else sys.stdin.read()
        counts = import_csv(conn, data)

    rebuild_fts(conn)
    conn.close()
    print("Imported:")
    for table, n in counts.items():
        print(f"  {table}: {n} rows")


# Main

def main():
    parser = argparse.ArgumentParser(
        description="Scifind \u2014 structured physics formula database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              formula init
              formula list --branch "Classical mechanics" --difficulty 1-3
              formula show newton_second_law_of_motion
              formula search "heat work"
              formula quantities
              formula quantity length
              formula units --quantity length
              formula export --output backup.csv
              formula export --format csvdir -o ./backup
              formula export --format xlsx -o formulas.xlsx
              formula export --format ods -o formulas.ods
              formula import backup.csv
              formula import ./backup
              formula import formulas.xlsx
        """),
    )
    parser.add_argument("--db", help=f"Database path (default: {db_path()})")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create and seed the database")

    p_list = sub.add_parser("list", help="List formulas")
    p_list.add_argument("--branch", "-b", help="Filter by branch")
    p_list.add_argument("--topic", "-t", help="Filter by topic")
    p_list.add_argument("--difficulty", "-d", help="Difficulty range: N or N-M")

    p_show = sub.add_parser("show", help="Show formula")
    p_show.add_argument("id", help="Formula ID")

    p_search = sub.add_parser("search", help="Full-text search")
    p_search.add_argument("query", help="Search terms")
    p_search.add_argument("--limit", "-l", type=int, default=20, help="Max results")

    p_quantities = sub.add_parser("quantities", help="List quantities")
    p_quantities.add_argument("--formula", "-f", help="Filter by formula ID")

    p_quantity = sub.add_parser("quantity", help="Show quantity details")
    p_quantity.add_argument("id", help="Quantity ID")

    p_units = sub.add_parser("units", help="List units")
    p_units.add_argument("--quantity", "-q", help="Filter by quantity ID")

    sub.add_parser("browse", help="Browse by branch/topic")

    p_export = sub.add_parser("export", help="Export all tables")
    p_export.add_argument("--format", "-f", choices=["csv", "csvdir", "xlsx", "ods"],
                          default="csv", help="Output format (default: csv)")
    p_export.add_argument("--output", "-o", help="Output file or directory")

    p_import = sub.add_parser("import", help="Import tables from file or directory")
    p_import.add_argument("file", help="CSV/XLSX/ODS file or CSV directory")

    args = parser.parse_args()
    if args.db:
        os.environ["FORMULA_DB"] = args.db

    commands = {
        "init": cmd_init,
        "list": cmd_list,
        "show": cmd_show,
        "search": cmd_search,
        "quantities": cmd_quantities,
        "quantity": cmd_quantity,
        "units": cmd_units,
        "browse": cmd_browse,
        "export": cmd_export,
        "import": cmd_import,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
