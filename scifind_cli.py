#!/usr/bin/env python3
"""Scifind CLI — explore and manage the formula database from the terminal.

Usage:
    scifind_cli init                            Create and seed the database
    scifind_cli list [options]                  List formulas
    scifind_cli show <id>                       Show formula details
    scifind_cli search <query>                  Full-text search
    scifind_cli quantities [--formula F]        List quantities
    scifind_cli quantity <id>                   Show quantity details
    scifind_cli units [--quantity Q]            List units
    scifind_cli browse                          Browse branch/topic tree
    scifind_cli export [options]                Export all tables
"""

import argparse
import os
import sqlite3
import sys
import textwrap
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from scifind_lib import (
    database_path,
    open_database,
    database_has_formula_table,
    init_database,
    render_formula,
    format_dimensions_plain,
    extract_dimensions_from_row,
    search_headings,
    difficulty_to_stars,
    localise_english,
    fetch_formula,
    fetch_formula_related,
    fetch_formula_quantities,
    fetch_quantity,
    fetch_quantity_units,
    fetch_quantity_formulas,
    fetch_all_quantities,
    export_to_csv,
    export_to_csv_directory,
    export_to_xlsx,
    export_to_ods,
    export_to_sql,
    topic_name,
    format_unit_str,
    group_by_topic,
)


def _exit_with_error(message, code=1):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


_USE_COLOUR = sys.stdout.isatty()
_CODES = {"bold": 1, "dim": 2, "yellow": 33, "cyan": 36}


def _styled(style, text):
    return f"\033[{_CODES[style]}m{text}\033[0m" if _USE_COLOUR else text


def _wrap(text):
    return textwrap.fill(text, width=72, initial_indent="  ", subsequent_indent="  ")


def _print_unit_row(u):
    mark = "\u2713" if u["default_unit"] else " "
    offset_str = f" + {u['offset']}" if u["offset"] else ""
    print(
        f"  [{mark}] ${u['symbol']}$  {_styled("bold", u['id'])}  "
        f"[{u['unit_system'] or 'any'}]  \u00d7{u['factor']}{offset_str} \u2192 SI"
    )


def command_init(args):
    if not args.force:
        existing = open_database()
        try:
            if database_has_formula_table(existing):
                _exit_with_error(
                    "database already initialised. Pass --force to re-initialise "
                    "(this will wipe existing data).",
                    code=2,
                )
        finally:
            existing.close()

    try:
        change_count = init_database(force=args.force)
    except (sqlite3.Error, OSError) as exc:
        _exit_with_error(f"initialisation failed: {exc}")

    print(f"Database initialised at {database_path()}")
    print(f"  {change_count} SQL statements executed.")


def _parse_difficulty_range(raw):
    parts = raw.split("-")
    try:
        if len(parts) == 1:
            value = int(parts[0])
            return value, value
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except ValueError:
        pass
    _exit_with_error(f"invalid difficulty range {raw!r} (expected N or N-M)")


def command_list(args):
    conn = open_database()
    where_clauses = []
    params = []
    if args.topic:
        where_clauses.append("f.topic = ?")
        params.append(args.topic)

    if args.difficulty:
        diff_min, diff_max = _parse_difficulty_range(args.difficulty)
        if diff_min == diff_max:
            where_clauses.append("f.difficulty = ?")
            params.append(diff_min)
        else:
            where_clauses.append("f.difficulty BETWEEN ? AND ?")
            params.extend([diff_min, diff_max])

    sql = """
        SELECT f.id, json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty
        FROM formula f
    """
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY f.topic, f.difficulty, f.id"

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    if not rows:
        print("No formulas found.")
        return

    for topic, items in group_by_topic(rows).items():
        print(f"\n  {_styled("yellow", topic)}:")
        for f in items:
            stars = difficulty_to_stars(f["difficulty"])
            print(f"    {f['id']:40s} {stars}  {f['name_en']}")
    print()


def command_show(args):
    conn = open_database()
    row = fetch_formula(conn, args.id)
    if not row:
        print(f"Formula '{args.id}' not found.")
        sys.exit(1)
    related = fetch_formula_related(conn, args.id)
    quantities = fetch_formula_quantities(conn, args.id)
    latex = render_formula(conn, args.id, locale="en-us")
    conn.close()

    name = localise_english(row["name"])
    description = localise_english(row["description"])
    difficulty = row["difficulty"]
    topic = topic_name(row["topic_id"])
    stars = difficulty_to_stars(difficulty)

    print(f"\n  {_styled("bold", name)}  {stars}")
    if topic:
        print(f"  {_styled("cyan", topic)}  (difficulty {difficulty}/10)")

    if latex:
        print(f"\n  $$")
        print(f"  {latex}")
        print(f"  $$")

    if description:
        print(f"\n  {_styled("dim", _wrap(description))}")

    if quantities:
        print(f"\n  {_styled("bold", 'Quantities:')}")
        for q in quantities:
            print(f"    ${q['symbol']}$  {q['name_en']}  ({_styled("dim", q['id'])})")

    if related:
        print(f"\n  {_styled("bold", 'Related:')}")
        for r in related:
            print(f"    {_styled("dim", r['relation_type'])} \u2192 {r['related_id']}  ({r['related_name']})")
    print()


def command_search(args):
    conn = open_database()
    rows = search_headings(conn, args.query, args.limit or 20)
    conn.close()
    if not rows:
        print("No results.")
        return

    print(f"\n  {_styled("bold", f'{len(rows)} result(s)')} for {_styled("yellow", repr(args.query))}\n")
    for kind, id_, name_en in rows:
        print(f"  [{kind}] {name_en}  ({id_})")
    print()


def command_quantities(args):
    conn = open_database()
    if args.formula:
        rows = fetch_formula_quantities(conn, args.formula)
    else:
        rows = fetch_all_quantities(conn)
    if not rows:
        conn.close()
        print("No quantities found.")
        return

    header = f"\n  {_styled("bold", 'Quantities')}"
    if args.formula:
        header += f" for {_styled("yellow", args.formula)}"
    print(header + "\n")

    for q in rows:
        dimensions = format_dimensions_plain(*extract_dimensions_from_row(q))
        unit_str = format_unit_str(q["default_unit"])
        print(f"  ${q['symbol']}$  {_styled("bold", q['name_en'])}  ({_styled("dim", q['id'])})")
        if unit_str:
            print(f"      Dimensions: {_styled("dim", dimensions)}  default unit: {unit_str}")
        else:
            print(f"      Dimensions: {_styled("dim", dimensions)}")
    conn.close()
    print()


def command_quantity(args):
    conn = open_database()
    q = fetch_quantity(conn, args.id)
    if not q:
        print(f"Quantity '{args.id}' not found.")
        sys.exit(1)
    units = fetch_quantity_units(conn, args.id)
    formulas = fetch_quantity_formulas(conn, args.id)

    name = localise_english(q["name"])
    description = localise_english(q["description"])
    dimensions = format_dimensions_plain(*extract_dimensions_from_row(q))
    conn.close()
    unit_str = format_unit_str(q["default_unit"])

    label = f"${q['symbol']}$ \u2014 {name}"
    print(f"\n  {_styled("bold", label)}  ({_styled("dim", q['id'])})")
    if dimensions:
        print(f"  Dimensions: {_styled("dim", dimensions)}")
    if unit_str:
        print(f"  Default unit: {unit_str}")

    if description:
        print(f"\n  {_styled("dim", _wrap(description))}")

    if units:
        print(f"\n  {_styled("bold", 'Units:')}")
        for u in units:
            _print_unit_row(u)

    if formulas:
        print(f"\n  {_styled("bold", 'Appears in formulas:')}")
        for f in formulas:
            stars = difficulty_to_stars(f["difficulty"])
            print(f"    {f['id']:40s} {stars}  {f['name_en']}")
    print()


def command_units(args):
    conn = open_database()
    base_query = """
        SELECT u.*, json_extract(q.name, '$.en-us') AS quantity_name
        FROM unit u JOIN quantity q ON q.id = u.quantity_id
    """
    if args.quantity:
        rows = conn.execute(
            base_query + " WHERE u.quantity_id = ? ORDER BY u.default_unit DESC, u.unit_system",
            (args.quantity,),
        ).fetchall()
    else:
        rows = conn.execute(
            base_query + " ORDER BY q.id, u.default_unit DESC, u.unit_system"
        ).fetchall()
    conn.close()
    if not rows:
        print("No units found.")
        return

    header = f"\n  {_styled("bold", 'Units')}"
    if args.quantity:
        header += f" for {_styled("yellow", args.quantity)}"
    print(header + "\n")

    for u in rows:
        _print_unit_row(u)
    print()


def command_browse(args):
    conn = open_database()
    rows = conn.execute("""
        SELECT f.id, json_extract(f.name, '$.en-us') AS name_en,
               f.topic AS topic_id, f.difficulty
        FROM formula f ORDER BY f.topic, f.difficulty, f.id
    """).fetchall()
    conn.close()

    for topic, items in group_by_topic(rows).items():
        print(f"\n  {_styled("yellow", topic)}")
        for f in items:
            stars = difficulty_to_stars(f["difficulty"])
            print(f"      {f['id']:38s} {stars}  {f['name_en']}")
    print()


def command_export(args):
    conn = open_database()
    fmt = (args.format or "csv").lower()

    if fmt == "csvdir":
        target = args.output or "."
        export_to_csv_directory(conn, target)
        print(f"Exported per-table CSV files to {target}/")
    elif fmt == "sql":
        output = args.output or "scifind.sql"
        Path(output).write_text(export_to_sql(conn), encoding="utf-8")
        print(f"Exported to {output}")
    elif fmt in ("xlsx", "ods"):
        output = args.output or f"scifind.{fmt}"
        if fmt == "xlsx":
            export_to_xlsx(conn, output)
        else:
            export_to_ods(conn, output)
        print(f"Exported to {output}")
    else:
        data = export_to_csv(conn)
        if args.output:
            Path(args.output).write_text(data, encoding="utf-8")
            print(f"Exported to {args.output}")
        else:
            sys.stdout.write(data)
    conn.close()


def main():
    default_database = database_path()
    parser = argparse.ArgumentParser(
        description="Scifind — structured physics formula database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              scifind_cli init
              scifind_cli list --difficulty 1-3
              scifind_cli show newtons_second_law
              scifind_cli search "heat work"
              scifind_cli quantities
              scifind_cli quantity length
              scifind_cli units --quantity length
              scifind_cli export --output backup.csv
              scifind_cli export --format csvdir -o ./backup
              scifind_cli export --format xlsx -o scifind.xlsx
              scifind_cli export --format ods -o scifind.ods
              scifind_cli export --format sql -o scifind.sql
        """),
    )
    parser.add_argument("--db", help=f"Database path (default: {default_database})")
    subcommands = parser.add_subparsers(dest="command", required=True)

    p_init = subcommands.add_parser("init", help="Create and seed the database")
    p_init.add_argument(
        "--force", action="store_true",
        help="Re-initialise even if database already exists (wipes existing data).",
    )

    p_list = subcommands.add_parser("list", help="List formulas")
    p_list.add_argument("--topic", "-t", help="Filter by topic")
    p_list.add_argument("--difficulty", "-d", help="Difficulty range: N or N-M")

    p_show = subcommands.add_parser("show", help="Show formula")
    p_show.add_argument("id", help="Formula ID")

    p_search = subcommands.add_parser("search", help="Full-text search")
    p_search.add_argument("query", help="Search terms")
    p_search.add_argument("--limit", "-l", type=int, default=20, help="Max results")

    p_quantities = subcommands.add_parser("quantities", help="List quantities")
    p_quantities.add_argument("--formula", help="Filter by formula ID")

    p_quantity = subcommands.add_parser("quantity", help="Show quantity details")
    p_quantity.add_argument("id", help="Quantity ID")

    p_units = subcommands.add_parser("units", help="List units")
    p_units.add_argument("--quantity", "-q", help="Filter by quantity ID")

    subcommands.add_parser("browse", help="Browse by branch/topic")

    p_export = subcommands.add_parser("export", help="Export all tables")
    p_export.add_argument(
        "--format", "-f", choices=["csv", "csvdir", "xlsx", "ods", "sql"],
        default="csv", help="Output format (default: csv)",
    )
    p_export.add_argument("--output", "-o", help="Output file or directory")

    args = parser.parse_args()
    if args.db:
        os.environ["SCIFIND_DB"] = args.db

    commands = {
        "init": command_init,
        "list": command_list,
        "show": command_show,
        "search": command_search,
        "quantities": command_quantities,
        "quantity": command_quantity,
        "units": command_units,
        "browse": command_browse,
        "export": command_export,
    }
    try:
        commands[args.command](args)
    except sqlite3.Error as exc:
        _exit_with_error(f"database error: {exc}")
    except OSError as exc:
        _exit_with_error(f"file error: {exc}")
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
