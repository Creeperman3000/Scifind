# CLI Tool

Entry point: `python scifind_cli.py`.
The general layout of a command is as follows:

```
python scifind_cli.py [--db <path>] <command> [options]
```

`--db <path>` overrides the database location (default is `scifind.db`)

## Commands

```
init          # Seed database from schema.sql and seed.sql (use --force to rebuild)
  --force

list          # List all formulas by topic with difficulty stars
  -t, --topic     <id>
  -d, --difficulty N|N-M

show          # Show formula with LaTeX, variables, description, related formulas
  <formula_id>

search        # Substring search across names, symbols, and IDs (excludes hidden quantities)
  <query>
  -l, --limit     <n>                    default: 20

quantities    # List quantities with dimensions and default units
  --formula       <id>

quantity      # Show dimensions, compatible units, and containing formulas
  <quantity_id>

units         # List units with symbols, systems, and SI conversion factors
  -q, --quantity  <id>

browse        # Tree view of all formulas grouped by topic

export        # Export entire database
  -f, --format    csv|csvdir|xlsx|ods|sql
  -o, --output    <path>
```
