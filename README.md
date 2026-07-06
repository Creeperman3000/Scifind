# Scifind

A physics formula database with a CLI tool and web app.

## Quick Start

```bash
git clone <repo>
cd Scifind
pip install -r requirements.txt
python webapp.py          # start web app at http://localhost:5000
```

A populated `scifind.db` is included in the repo. The webapp auto-creates
and seeds the database on first run if it is missing or empty. For the CLI:

```bash
python scifind_cli.py init --force  # rebuild the database from scratch
python scifind_cli.py list          # browse formulas
```

## Project Structure

| Path | Purpose |
| ---- | ------- |
| `scifind_cli.py` | CLI entry point |
| `scifind_lib.py` | Database, rendering, i18n, export |
| `webapp.py` | Flask web application |
| `scifind.db` | Pre-built database (auto-regenerated on first run if missing) |
| `schema.sql` | Database schema (6 tables, 3 FTS5 indexes) |
| `seed.sql` | Core seed data (formulas, quantities, units) |
| `seed_units.sql` | Additional SI and non-SI units |
| `seed_formulas.sql` | Extended formulas across sciences |
| `tree.json` | Science/branch/topic tree with translations |
| `templates/` | Jinja2 templates |
| `wiki/` | Documentation |
| `requirements.txt` | Python dependencies |

## requirements

```
flask>=3.0
markupsafe>=2.1
openpyxl>=3.1
odfpy>=1.4
```

## Docs

See the [wiki](wiki/Home.md) for detailed documentation on the CLI, web app, database schema, and development workflow.
