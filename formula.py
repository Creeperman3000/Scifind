#!/usr/bin/env python3
"""
formula — CLI tool for the physics formula cheat-sheet database.

Usage:
    formula init                            Create and seed the database
    formula list [options]                  List formulas
    formula show <id>                       Show formula details
    formula search <query>                  Full-text search
    formula variables [--formula F]         List variables
    formula variable <id>                   Show variable details
    formula units [--variable V]            List units
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
    render_si_unit_html, parse_si_unit_json,
    get_formula_detail, get_formula_items,
    get_formula_conditions, get_formula_relations, get_formula_variables,
    get_variable_detail, get_variable_units, get_variable_formulas,
    get_formulas_by_science,
    search,
    export_csv, export_csv_dir, export_xlsx, export_ods,
    import_csv, import_csv_dir, import_xlsx, import_ods,
)

SCRIPT_DIR = _project_dir


# ── Init ────────────────────────────────────────────────

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


# ── List ────────────────────────────────────────────────

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
        FROM formulas f
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
        print(f"\n── \033[1m{branch}\033[0m ──")
        for topic, formulas in topics.items():
            print(f"  \033[33m{topic}\033[0m:")
            for f in formulas:
                s = "★" * min(f["difficulty"], 5) + "☆" * max(0, 5 - min(f["difficulty"], 5))
                print(f"    {f['id']:40s} {s}  {f['name_en']}")
    print()


# ── Show ────────────────────────────────────────────────

def cmd_show(args):
    conn = get_conn()
    row = get_formula_detail(conn, args.id)
    if not row:
        print(f"Formula '{args.id}' not found.")
        sys.exit(1)
    items = get_formula_items(conn, args.id)
    conds = get_formula_conditions(conn, args.id)
    relations = get_formula_relations(conn, args.id)
    variables = get_formula_variables(conn, args.id)
    conn.close()

    name = en(row["name"])
    desc = en(row["description"])
    diff = row["difficulty"]
    branch = en(row["branch"])
    topic = en(row["topic"])
    stars = "★" * min(diff, 5) + "☆" * max(0, 5 - min(diff, 5))

    print(f"\n  \033[1m{name}\033[0m  {stars}")
    if branch:
        print(f"  \033[33m{branch}\033[0m → \033[36m{topic}\033[0m  (difficulty {diff}/10)")

    if items:
        latex = render_formula_items(items)
        print(f"\n  \033[90m$$\033[0m")
        print(f"  \033[97m{latex}\033[0m")
        print(f"  \033[90m$$\033[0m")

    if desc:
        wrapped = textwrap.fill(desc, width=72, initial_indent="  ", subsequent_indent="  ")
        print(f"\n  \033[2m{wrapped}\033[0m")

    if conds:
        print(f"\n  \033[1mAssumptions:\033[0m")
        for c in conds:
            state = "☑" if c["default_on"] else "☐"
            print(f"    {state} {c['name_en']}  →  {c['replacement_formula_id']}")

    if variables:
        print(f"\n  \033[1mVariables:\033[0m")
        for v in variables:
            print(f"    ${v['latex']}$  {v['name_en']}  (\033[90m{v['id']}\033[0m)")

    if relations:
        print(f"\n  \033[1mRelated:\033[0m")
        for r in relations:
            print(f"    \033[90m{r['relation_type']}\033[0m → {r['related_id']}  ({r['related_name']})")
    print()


# ── Search ──────────────────────────────────────────────

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
            s = "★" * min(r["difficulty"], 5) + "☆" * max(0, 5 - min(r["difficulty"], 5))
            print(f"  \033[36mformula \033[0m{r['id']:40s} {s}  {r['name_en']}")
        elif r["kind"] == "variable":
            print(f"  \033[32mvariable\033[0m {r['id']:40s}        {r['name_en']} ($\\{r['extra']}$)")
        elif r["kind"] == "unit":
            print(f"  \033[33munit    \033[0m{r['id']:40s}        {r['name_en']} ($\\{r['extra']}$)")
    print()


# ── Variables list ─────────────────────────────────────

def cmd_variables(args):
    conn = get_conn()
    if args.formula:
        rows = get_formula_variables(conn, args.formula)
    else:
        rows = conn.execute("""
            SELECT v.id, v.latex, json_extract(v.name, '$.en-us') AS name_en,
                   v.si_unit, v.dim_M, v.dim_L, v.dim_T, v.dim_I, v.dim_Θ, v.dim_N, v.dim_J
            FROM variables v ORDER BY v.id
        """).fetchall()
    conn.close()
    if not rows:
        print("No variables found.")
        return
    print(f"\n  \033[1mVariables\033[0m" + (f" for \033[33m{args.formula}\033[0m" if args.formula else "") + "\n")
    for v in rows:
        dims = render_dimensions(*dims_from_row(v))
        unit_parts = parse_si_unit_json(v["si_unit"])
        unit_str = "\u00b7".join(f"{uid}^{exp}" for uid, exp in unit_parts) if unit_parts else ""
        print(f"  ${v['latex']}$  \033[1m{v['name_en']}\033[0m  (\033[90m{v['id']}\033[0m)")
        print(f"      Dimensions: \033[2m{dims}\033[0m" + (f"  SI: {unit_str}" if unit_str else ""))
    print()


# ── Variable detail ────────────────────────────────────

def cmd_variable(args):
    conn = get_conn()
    v = get_variable_detail(conn, args.id)
    if not v:
        print(f"Variable '{args.id}' not found.")
        sys.exit(1)
    units = get_variable_units(conn, args.id)
    formulas = get_variable_formulas(conn, args.id)
    conn.close()

    name = en(v["name"])
    desc = en(v["description"])
    dims = render_dimensions(v["dim_M"], v["dim_L"], v["dim_T"], v["dim_I"], v["dim_Θ"], v["dim_N"], v["dim_J"])
    unit_parts = parse_si_unit_json(v["si_unit"])
    unit_str = "\u00b7".join(f"{uid}^{exp}" for uid, exp in unit_parts) if unit_parts else ""

    print(f"\n  \033[1m${v['latex']}$ — {name}\033[0m  (\033[90m{v['id']}\033[0m)")
    if dims:
        print(f"  Dimensions: \033[2m{dims}\033[0m")
    if unit_str:
        print(f"  SI unit: {unit_str}")

    if desc:
        wrapped = textwrap.fill(desc, width=72, initial_indent="  ", subsequent_indent="  ")
        print(f"\n  \033[2m{wrapped}\033[0m")

    if units:
        print(f"\n  \033[1mUnits:\033[0m")
        for u in units:
            s = "✓" if u["si_unit"] else " "
            off = f" + {u['offset']}" if u["offset"] else ""
            print(f"    [{s}] ${u['symbol']}$  {u['id']}  [{u['unit_system'] or 'any'}]  ×{u['factor_to_si']}{off} → SI")

    if formulas:
        print(f"\n  \033[1mAppears in formulas:\033[0m")
        for f in formulas:
            s = "★" * min(f["difficulty"], 5) + "☆" * max(0, 5 - min(f["difficulty"], 5))
            print(f"    {f['id']:40s} {s}  {f['name_en']}")
    print()


# ── Units ───────────────────────────────────────────────

def cmd_units(args):
    conn = get_conn()
    if args.variable:
        rows = conn.execute("""
            SELECT u.*, json_extract(v.name, '$.en-us') AS var_name
            FROM units u JOIN variables v ON v.id = u.variable_id
            WHERE u.variable_id = ?
            ORDER BY u.si_unit DESC, u.unit_system
        """, (args.variable,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT u.*, json_extract(v.name, '$.en-us') AS var_name
            FROM units u JOIN variables v ON v.id = u.variable_id
            ORDER BY v.id, u.si_unit DESC, u.unit_system
        """).fetchall()
    conn.close()
    if not rows:
        print("No units found.")
        return
    print(f"\n  \033[1mUnits\033[0m" + (f" for \033[33m{args.variable}\033[0m" if args.variable else "") + "\n")
    for u in rows:
        s = "✓" if u["si_unit"] else " "
        off = f" + {u['offset']}" if u["offset"] else ""
        print(f"  [{s}] ${u['symbol']}$  \033[1m{u['id']}\033[0m  [{u['unit_system'] or 'any'}]  ×{u['factor_to_si']}{off} → SI")
    print()


# ── Browse ──────────────────────────────────────────────

def cmd_browse(args):
    conn = get_conn()
    rows = conn.execute("""
        SELECT f.id, json_extract(f.name, '$.en-us') AS name_en,
               json_extract(f.branch, '$.en-us') AS branch_en,
               json_extract(f.topic, '$.en-us') AS topic_en, f.difficulty
        FROM formulas f ORDER BY f.branch, f.topic, f.difficulty, f.id
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
                s = "★" * min(f["difficulty"], 5) + "☆" * max(0, 5 - min(f["difficulty"], 5))
                print(f"      {f['id']:38s} {s}  {f['name_en']}")
    print()


# ── Export ──────────────────────────────────────────────

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


# ── Import ──────────────────────────────────────────────

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


# ── Main ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Physics formula cheat-sheet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              formula init
              formula list --branch "Classical mechanics" --difficulty 1-3
              formula show newton_second_law_of_motion
              formula search "heat work"
              formula variables
              formula variable length
              formula units --variable length
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

    p_vars = sub.add_parser("variables", help="List variables")
    p_vars.add_argument("--formula", "-f", help="Filter by formula ID")

    p_var = sub.add_parser("variable", help="Show variable details")
    p_var.add_argument("id", help="Variable ID")

    p_units = sub.add_parser("units", help="List units")
    p_units.add_argument("--variable", "-v", help="Filter by variable ID")

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
        "variables": cmd_variables,
        "variable": cmd_variable,
        "units": cmd_units,
        "browse": cmd_browse,
        "export": cmd_export,
        "import": cmd_import,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
