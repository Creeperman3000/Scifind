# Database Specification

SQLite database with 6 core tables, 8 views, and 3 FTS5 virtual tables.

## Schema (`schema.sql`)

### `formula`
One row per equation.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `name` | TEXT | JSON i18n (`{"en-us": "...", "en-uk": "..."}`) |
| `science` | TEXT | Science tree ID |
| `branch` | TEXT | Branch tree ID |
| `subbranch` | TEXT | Subbranch tree ID (optional) |
| `topic` | TEXT | Topic tree ID |
| `difficulty` | INTEGER | 1–10 |
| `description` | TEXT | JSON i18n |
| `links` | TEXT | Optional reference links |
| `created` | TEXT | Auto timestamp |
| `modified` | TEXT | Auto timestamp |

### `formula_item`
Breaks each formula into terms/factors/variables.

| Column | Type | Description |
|--------|------|-------------|
| `formula_id` | TEXT | FK → formula.id |
| `term` | INTEGER | Which side of equation |
| `is_primary` | INTEGER | 1 = LHS, 0 = RHS |
| `sort_order` | INTEGER | Display ordering |
| `coeff_value` | REAL | Numeric coefficient |
| `latex_coef` | TEXT | LaTeX coefficient (`\pi`, `e`) |
| `coeff_exponent` | REAL | Coefficient exponent |
| `quantity_id` | TEXT | FK → quantity.id |
| `var_exponent` | REAL | Variable exponent |
| `label` | TEXT | Subscript text (JSON i18n, e.g. `{"en-us": "k"}`) |
| `symbol_overwrite` | TEXT | Override quantity symbol (JSON i18n, e.g. `{"en-us": "g"}`) |
| `quantity_name_overwrite` | TEXT | JSON i18n override of quantity name for this item (e.g. `{"en-us": "Potential Energy"}`) |
| `latex_prefix` | TEXT | LaTeX prefix (e.g. `\Delta{}`) |
| `latex_suffix` | TEXT | LaTeX suffix (e.g. `{}`) |

### `condition`
Togglable assumptions that modify a formula.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto) |
| `name` | TEXT | JSON i18n |
| `formula_id` | TEXT | FK → formula.id |
| `replacement_formula_id` | TEXT | FK → formula.id |
| `default_on` | INTEGER | Toggled by default |
| `sort_order` | INTEGER | Display ordering |
| `created` | TEXT | Auto timestamp |
| `modified` | TEXT | Auto timestamp |

### `formula_relation`
Typed relationships between formulas.

| Column | Type | Description |
|--------|------|-------------|
| `formula_id` | TEXT | FK → formula.id |
| `related_id` | TEXT | FK → formula.id |
| `relation_type` | TEXT | alternative/derivation/special_case/prerequisite/generalization |

### `quantity`
Physical quantities.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `name` | TEXT | JSON i18n |
| `symbol` | TEXT | LaTeX symbol |
| `symbol_overwrite` | TEXT | JSON i18n override of quantity symbol |
| `science` | TEXT | Science tree ID |
| `branch` | TEXT | Branch tree ID |
| `subbranch` | TEXT | Subbranch tree ID (optional) |
| `topic` | TEXT | Topic tree ID |
| `difficulty` | INTEGER | 1–10 |
| `description` | TEXT | JSON i18n |
| `links` | TEXT | JSON array |
| *(removed)* | | Base dimensions are now identified via `formula_item` rows with `formula_id='dimensions'` |
| `default_unit` | TEXT | JSON array: `[{"unit":"<id>","exponent":<n>},...]` |
| `dim_*` | REAL | One column per base dimension (from formula_item) |
| `created` | TEXT | Auto timestamp |
| `modified` | TEXT | Auto timestamp |

### `unit`
Units with conversion factors.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `name` | TEXT | JSON i18n |
| `symbol` | TEXT | LaTeX symbol |
| `quantity_id` | TEXT | FK → quantity.id |
| `default_unit` | INTEGER | Primary unit for the quantity |
| `unit_system` | TEXT | SI/CGS/Imperial |
| `factor` | REAL | Conversion factor (to SI) |
| `latex_factor` | TEXT | LaTeX display for factor (e.g. `\frac{180}{\pi}`) |
| `offset` | REAL | Conversion offset |

## FTS5 Indexes

- `formula_fts` — search by formula name, description, quantities
- `quantity_fts` — search by quantity name, symbol
- `unit_fts` — search by unit name, symbol

## Seed Data

Data is loaded from three seed files:

| File | Contents |
|------|----------|
| `seed.sql` | Core formulas, quantities, units, conditions, relations |
| `seed_units.sql` | Additional SI/non-SI units, derived quantities, unit conversion factors |
| `seed_formulas.sql` | Extended formulas and quantities across physics, chemistry, mathematics |

Run `scifind_cli.py init` after editing the schema or these files.

## Conventions

- **i18n JSON**: All user-facing text fields (`name`, `description`, `label`, `symbol_overwrite`, `quantity_name_overwrite`) are stored as JSON i18n (`{"en-us": "text"}`). Plain text is deprecated.
- **Column order**: `symbol_overwrite` follows `symbol` in `quantity`; `latex_factor` follows `factor` in `unit`; `quantity_name_overwrite` follows `symbol_overwrite` in `formula_item`.
- **Similar quantities**: Quantities with identical dimensions (e.g. `potential_energy`, `rotational_energy`) are merged into a single `energy` quantity with `label` and `quantity_name_overwrite` to differentiate.
- **LaTeX coefficients**: Store raw LaTeX (e.g. `\pi`, `e`) directly in `latex_coef` rather than plain text identifiers.
