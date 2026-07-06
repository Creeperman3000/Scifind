# Development

## Setup

```bash
git clone <repo>
cd Scifind
pip install -r requirements.txt
python scifind_cli.py init
```

The database is created at `~/.local/share/scifind/scifind.db` (override with `--db` or `SCIFIND_DB`).

## Running

**Web app:**
```bash
python webapp.py
```

**CLI:**
```bash
python scifind_cli.py list
python scifind_cli.py show kinetic_energy
python scifind_cli.py search "force"
```

## Tests

```bash
python3 -c "
from webapp import app
app.config['TESTING'] = True
with app.test_client() as c:
    for route in ['/formulas', '/quantities', '/formula/circle_area', '/quantity/area', '/search?q=circle']:
        r = c.get(route)
        print(f'{route}: {\"OK\" if r.status_code == 200 else \"FAIL\"} ({r.status_code})')
"
```

## I18n

All user-facing text fields (`name`, `description`, `label`, `symbol_overwrite`, `quantity_name_overwrite`) use JSON i18n:
```json
{"en-us": "...", "en-uk": "..."}
```

The `localise()` and `localise_english()` helpers handle both plain text and JSON, falling back to `en-us` if the requested locale isn't present. Supported locales: `en-us`, `en-uk`.

## Adding a Formula

1. Insert a row into `formula` with a unique `id`, name, science/branch/topic, and difficulty.
2. Insert rows into `formula_item` for each variable — LHS items (`is_primary=1`) and RHS items (`is_primary=0`).
3. If the formula uses a quantity with the same dimensions as another (e.g., rotational energy uses `energy` with a subscript), set `label` (JSON i18n) and `quantity_name_overwrite` (JSON i18n) on the LHS item.
4. If the formula has assumptions, add `condition` rows linking to replacement formulas.
5. Link related formulas via `formula_relation`.
6. Rebuild FTS: `python scifind_cli.py init` or call `scifind_lib.rebuild_search_indexes()`.

## Adding Seed Data

Edit `seed.sql`, `seed_units.sql`, and/or `seed_formulas.sql`. Re-initialize with:
```bash
python scifind_cli.py init  # drops and recreates DB
```

## Export

```bash
python scifind_cli.py export --format csv --output formulas.csv
```

Supported formats: `csv`, `csvdir`, `xlsx`, `ods`.

## Edge Cases

- **LaTeX command-letter collision**: `\pir` → `\pi{}r`. The `_join_latex_parts()` function inserts `{}` between a command and a following letter.
- **symbol_overwrite empty/null**: Falls back to the quantity's default symbol, then to the quantity ID.
- **label empty/null**: No subscript is rendered.
- **quantity_name_overwrite**: Overrides the displayed quantity name in formula detail views; falls back to quantity `name` if not set.
- **sqlite3.Row vs dict**: Access columns by `item["col"]` using `or ""` fallback (works with both).
- **Composite unit IDs**: Units with `_per_`, `square_`, `cubic_`, or `reciprocal_` prefixes are decomposed into base components for display.
