#!/usr/bin/env python3
"""Scifind CLI — explore and manage the formula database from the terminal.

Usage:
    scifind_cli init                            Create and seed the database
    scifind_cli list [options]                  List formulas
    scifind_cli show <id>                       Show formula details
    scifind_cli search <query>                  Full-text search
    scifind_cli quantities [--formula F] [--system SYS]  List quantities
    scifind_cli quantity <id> [--system SYS]    Show quantity details
    scifind_cli units [--quantity Q]            List units
    scifind_cli browse                          Browse branch/topic tree
    scifind_cli export [options]                Export all tables
"""

import argparse
import json
import os
import sqlite3
import sys
import textwrap
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from scifind_lib import (
    database_connection, database_path, database_has_formula_table,
    initialize_database, render_formula_latex, format_dimensions_plain,
    dimension_symbols, dimensions_from_row, search_entities,
    difficulty_to_stars, localise, fetch_formula,
    fetch_formula_relations, fetch_formula_quantities, fetch_quantity,
    fetch_quantity_units, fetch_quantity_formulas, fetch_all_quantities,
    fetch_formulas_filtered, fetch_units_with_quantity,
    export_to_csv_directory, export_to_xlsx, export_to_ods,
    select_base_unit_with_fallback, load_tree, topic_name,
    format_unit_symbol_plain, group_by_topic,
)


def _err(message, code=1):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


_USE_COLOUR = sys.stdout.isatty()
_CODES = {"bold": 1, "dim": 2, "yellow": 33, "cyan": 36}


def _st(style, text):
    return f"\033[{_CODES[style]}m{text}\033[0m" if _USE_COLOUR else text


def _wrap(text):
    return textwrap.fill(text, width=72, initial_indent="  ", subsequent_indent="  ")


def _header(title, qualifier=None):
    heading = f"\n  {_st('bold', title)}"
    if qualifier:
        heading += f" for {_st('yellow', qualifier)}"
    print(heading + "\n")


def _unit_row(unit):
    mark = "✓" if unit["is_base"] else " "
    print(f"  [{mark}] ${unit['symbol']}$  {_st('bold', unit['id'])}  "
          f"[{unit['system'] or 'any'}]")


def _base_unit_str(conn, qid, system="SI"):
    base = select_base_unit_with_fallback(conn, qid, system)
    if base is None:
        return ""
    unit_json = base["unit"] if base["kind"] == "compound_unit" \
        else json.dumps([{"unit": base["id"], "exponent": 1}])
    from scifind_lib import fetch_si_prefix_map
    try:
        # Prefix *names* join uid-based plain units as real words
        # (kilogram, centimetre), mirroring the web HTML renderer.
        prefixes = {e: str(n).lower()
                    for e, n in fetch_si_prefix_map(conn, "name").items()}
    except Exception:
        prefixes = None
    return format_unit_symbol_plain(unit_json, prefixes)


def _dims(conn, qty, system="SI"):
    return (format_dimensions_plain(*dimensions_from_row(qty, conn),
                                    symbols=dimension_symbols(conn)),
            _base_unit_str(conn, qty["id"], system))


def command_init(args):
    if not args.force:
        with database_connection() as existing:
            if database_has_formula_table(existing):
                _err("database already initialised. Pass --force to re-initialise "
                     "(this will wipe existing data).", code=2)
    try:
        if args.force:
            os.environ["SCIFIND_ALLOW_FORCE_INIT"] = "1"
        count = initialize_database(force=args.force)
    except (sqlite3.Error, OSError) as exc:
        _err(f"initialisation failed: {exc}")
    print(f"Database initialised at {database_path()}")
    print(f"  {count} SQL statements executed.")


def _diff_range(raw):
    try:
        lo, *hi = (int(p) for p in raw.split("-"))
        return (lo, hi[0]) if hi else (lo, lo)
    except ValueError:
        pass
    _err(f"invalid difficulty range {raw!r} (expected N or N-M)")


def _list_formulas(topic=None, difficulty=None, id_width=40,
                   row_indent="    ", topic_suffix=":"):
    lo = hi = None
    if difficulty:
        lo, hi = _diff_range(difficulty)
    with database_connection() as conn:
        rows = fetch_formulas_filtered(conn, topic=topic, diff_min=lo, diff_max=hi)
        tree = load_tree(conn)
    if not rows:
        print("No formulas found.")
        return
    for topic_label, formulas in group_by_topic(rows, tree).items():
        print(f"\n  {_st('yellow', topic_label)}{topic_suffix}")
        for formula in formulas:
            print(f"{row_indent}{formula['id']:{id_width}s} "
                  f"{difficulty_to_stars(formula['difficulty'])}  {formula['name_en']}")
    print()


def command_list(args):
    _list_formulas(topic=args.topic, difficulty=args.difficulty)


def command_browse(args):
    _list_formulas(id_width=38, row_indent="      ", topic_suffix="")


def command_show(args):
    with database_connection() as conn:
        row = fetch_formula(conn, args.id)
        if not row:
            _err(f"Formula '{args.id}' not found.")
        related = fetch_formula_relations(conn, args.id)
        quantities = fetch_formula_quantities(conn, args.id)
        latex = render_formula_latex(conn, args.id, locale="en-us")
        tree = load_tree(conn)
    print(f"\n  {_st('bold', localise(row['name'], 'en-us'))}  "
          f"{difficulty_to_stars(row['difficulty'])}")
    if (topic := topic_name(row["topic_id"], tree)):
        print(f"  {_st('cyan', topic)}  (difficulty {row['difficulty']}/10)")
    if latex:
        print(f"\n  $$\n  {latex}\n  $$")
    if (desc := localise(row["description"], 'en-us')):
        print(f"\n  {_st('dim', _wrap(desc))}")
    if quantities:
        print(f"\n  {_st('bold', 'Quantities:')}")
        for q in quantities:
            print(f"    ${q['symbol']}$  {q['name_en']}  ({_st('dim', q['id'])})")
    if related:
        print(f"\n  {_st('bold', 'Related:')}")
        for r in related:
            print(f"    {_st('dim', r['relation_type'])} → "
                  f"{r['related_id']}  ({r['related_name']})")
    print()


def command_search(args):
    with database_connection() as conn:
        rows = search_entities(conn, args.query, args.limit)
    if not rows:
        print("No results.")
        return
    print(f"\n  {_st('bold', f'{len(rows)} result(s)')} "
          f"for {_st('yellow', repr(args.query))}\n")
    for kind, id_, name_en in rows:
        print(f"  [{kind}] {name_en}  ({id_})")
    print()


def command_quantities(args):
    system = getattr(args, "system", None) or "SI"
    with database_connection() as conn:
        rows = (fetch_formula_quantities(conn, args.formula) if args.formula
                else fetch_all_quantities(conn))
        if not rows:
            print("No quantities found.")
            return
        _header("Quantities", args.formula)
        for q in rows:
            dims, unit = _dims(conn, q, system)
            print(f"  ${q['symbol']}$  {_st('bold', q['name_en'])}  "
                  f"({_st('dim', q['id'])})")
            suffix = f"  default unit: {unit}" if unit else ""
            print(f"      Dimensions: {_st('dim', dims)}{suffix}")
    print()


def command_quantity(args):
    system = getattr(args, "system", None) or "SI"
    with database_connection() as conn:
        qty = fetch_quantity(conn, args.id)
        if not qty:
            _err(f"Quantity '{args.id}' not found.")
        units = fetch_quantity_units(conn, args.id)
        formulas = fetch_quantity_formulas(conn, args.id)
        dims, unit = _dims(conn, qty, system)
        name, desc = localise(qty["name"], 'en-us'), localise(qty["description"], 'en-us')
    label = f"${qty['symbol']}$ — {name}"
    print(f"\n  {_st('bold', label)}  "
          f"({_st('dim', qty['id'])})")
    if dims:
        print(f"  Dimensions: {_st('dim', dims)}")
    if unit:
        print(f"  Default unit: {unit}")
    if desc:
        print(f"\n  {_st('dim', _wrap(desc))}")
    if units:
        print(f"\n  {_st('bold', 'Units:')}")
        for u in units:
            _unit_row(u)
    if formulas:
        print(f"\n  {_st('bold', 'Appears in formulas:')}")
        for f in formulas:
            print(f"    {f['id']:40s} {difficulty_to_stars(f['difficulty'])}  {f['name_en']}")
    print()


def command_units(args):
    with database_connection() as conn:
        rows = fetch_units_with_quantity(conn, args.quantity)
    if not rows:
        print("No units found.")
        return
    _header("Units", args.quantity)
    last_qid = None
    for u in rows:
        if not args.quantity and u["quantity_id"] != last_qid:
            last_qid = u["quantity_id"]
            print(f"  {_st('yellow', u['quantity_id'])} — {u['quantity_name']}")
        _unit_row(u)
    print()


def command_export(args):
    fmt = (args.format or "csv").lower()
    with database_connection() as conn:
        if fmt == "csvdir":
            target = args.output or "."
            export_to_csv_directory(conn, target)
            print(f"Exported per-table CSV files to {target}/")
            return
        if fmt in ("xlsx", "ods"):
            output = args.output or f"scifind.{fmt}"
            (export_to_xlsx if fmt == "xlsx" else export_to_ods)(conn, output)
            print(f"Exported to {output}")
            return
        from scifind_lib.export import export_payload
        payload, _, filename = export_payload(conn, fmt)
        output = args.output or ("scifind.sql" if fmt == "sql" else None)
        if output:
            Path(output).write_bytes(payload)
            print(f"Exported to {output}")
        else:
            sys.stdout.write(payload.decode("utf-8"))


_SUBCOMMANDS = [
    ("init", "Create and seed the database",
     [(("--force",), {"action": "store_true",
                      "help": "Re-initialise even if database already exists (wipes existing data)."})]),
    ("list", "List formulas",
     [(("--topic", "-t"), {"help": "Filter by topic"}),
      (("--difficulty", "-d"), {"help": "Difficulty range: N or N-M"})]),
    ("show", "Show formula", [(("id",), {"help": "Formula ID"})]),
    ("search", "Full-text search",
     [(("query",), {"help": "Search terms"}),
      (("--limit", "-l"), {"type": int, "default": 20, "help": "Max results"})]),
    ("quantities", "List quantities",
     [(("--formula",), {"help": "Filter by formula ID"}),
      (("--system", "-s"), {"choices": ["SI", "CGS", "Imperial"],
                            "default": "SI", "help": "Unit system for default unit (default: SI)"})]),
    ("quantity", "Show quantity details",
     [(("id",), {"help": "Quantity ID"}),
      (("--system", "-s"), {"choices": ["SI", "CGS", "Imperial"],
                            "default": "SI", "help": "Unit system for default unit (default: SI)"})]),
    ("units", "List units",
     [(("--quantity", "-q"), {"help": "Filter by quantity ID"})]),
    ("browse", "Browse by branch/topic", []),
    ("export", "Export all tables",
     [(("--format", "-f"), {"choices": ["csv", "csvdir", "xlsx", "ods", "sql"],
                            "default": "csv", "help": "Output format (default: csv)"}),
      (("--output", "-o"), {"help": "Output file or directory"})]),
]


def main():
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
    parser.add_argument("--db", help=f"Database path (default: {database_path()})")
    subs = parser.add_subparsers(dest="command", required=True)
    for name, help_text, arguments in _SUBCOMMANDS:
        sub = subs.add_parser(name, help=help_text)
        for flags, kwargs in arguments:
            sub.add_argument(*flags, **kwargs)
    args = parser.parse_args()
    if args.db:
        os.environ["SCIFIND_DB"] = args.db
    try:
        globals()[f"command_{args.command}"](args)
    except sqlite3.Error as exc:
        _err(f"database error: {exc}")
    except OSError as exc:
        _err(f"file error: {exc}")
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
