# CLI Tool

Entry point: `python scifind_cli.py` or `./scifind_cli.py`

## Usage

```
python scifind_cli.py <command> [options]
```

## Commands

### `init`
Initialize the database — runs `schema.sql` and `seed.sql`.

```bash
python scifind_cli.py init [--db <path>] [--force]
```

### `list`
List all formulas with topic.

```bash
python scifind_cli.py list [--topic <name>] [--difficulty <min-max>]
```

### `show <formula_id>`
Display a formula with its variables, description, and related formulas.

```bash
python scifind_cli.py show kinetic_energy
```

### `search <query>`
Substring search across formula, quantity, and unit names, symbols, and IDs.

```bash
python scifind_cli.py search "kinetic energy"
```

### `quantities`
List all quantities (optionally filtered by formula).

```bash
python scifind_cli.py quantities [--formula <id>]
```

### `quantity <quantity_id>`
Show quantity details including dimensions and compatible units.

```bash
python scifind_cli.py quantity length
```

### `units`
List all units with their symbols and conversion factors.

```bash
python scifind_cli.py units [--quantity <id>]
```

### `browse`
Tree browser for exploring formulas by topic.

### `export`
Export the entire database.

```bash
python scifind_cli.py export --format csv|csvdir|xlsx|ods [--output <path>]
```

## Options

| Flag                   | Description                            |
| ---------------------- | -------------------------------------- |
| `--db <path>`          | Override database path                 |
| `--format <fmt>`       | Export format (csv, csvdir, xlsx, ods) |
| `--output <path>`      | Export output path                     |
| `--topic <name>`       | Filter by topic                        |
| `--difficulty <range>` | Difficulty range: N or N-M             |
| `--formula <id>`       | Filter by formula ID                   |
| `--quantity <id>`      | Filter by quantity ID                  |

Default database path: `scifind.db` in the project root, overridable via
`SCIFIND_DB` env var.
