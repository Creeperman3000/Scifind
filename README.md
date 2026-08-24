# Scifind

A physics formula database with a CLI tool and web app.

## Quick Start

```bash
git clone <your-scifind-repo-url>   # e.g. the GitHub mirror
cd Scifind
pip install -r requirements.txt
python webapp.py                    # start web app at http://localhost:5000
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
| `scifind_lib/` | Library package: DB, parser, renderer, i18n, export, … |
| `webapp.py` | Flask web application |
| `web/` | Browser-facing files: Jinja2 templates, CSS, and JS, all at the top level |
| `scifind.db` | Pre-built database (auto-regenerated on first run if missing) |
| `schema.sql` | Database schema (7 tables) |
| `seed.sql` | Core seed data (formulas, quantities, units) |
| `tree.json` | Science/branch/topic tree with translations |
| `locales/` | Locale JSON files |
| `wiki/` | Documentation |
| `requirements.txt` | Python dependencies |

## Docs

See the [wiki](wiki/Home.md) for detailed documentation on the CLI, web app, database schema, and development workflow.
