# Database Specification

SQLite database with 5 tables. The dimension columns on `quantity` mirror the
`formula_item` rows where `formula_id = 'dimensions'`, which is the single
source of truth for the SI base dimension order.

## Schema (`schema.sql`)

### `formula`
One row per equation.

| Column        | Type    | Description                                    |
| ------------- | ------- | ---------------------------------------------- |
| `id`          | TEXT    | Primary key                                    |
| `name`        | TEXT    | JSON i18n (`{"en-us": "...", "en-uk": "..."}`) |
| `topic`       | TEXT    | ID into `tree.json`                            |
| `difficulty`  | INTEGER | 1–10                                           |
| `description` | TEXT    | JSON i18n                                      |
| `links`       | TEXT    | Optional reference links                       |
| `created`     | TEXT    | Auto timestamp                                 |
| `modified`    | TEXT    | Auto timestamp                                 |

### `formula_item`
A formula broken into terms (one equation side each), each term split into
primary and non-primary factors. The `formula_id = 'dimensions'` rows define
the SI base dimensions and their order.

| Column                    | Type    | Description                                       |
| ------------------------- | ------- | ------------------------------------------------- |
| `formula_id`              | TEXT    | FK → formula.id                                   |
| `term`                    | INTEGER | Which side of the equation                        |
| `is_primary`              | INTEGER | 1 = LHS, 0 = RHS                                  |
| `sort_order`              | INTEGER | Display ordering                                  |
| `coeff_value`             | REAL    | Numeric coefficient                               |
| `latex_coef`              | TEXT    | LaTeX coefficient (`\pi`, `e`)                    |
| `coeff_exponent`          | REAL    | Coefficient exponent                              |
| `quantity_id`             | TEXT    | FK → quantity.id                                  |
| `var_exponent`            | REAL    | Variable exponent                                 |
| `label`                   | TEXT    | Subscript text (JSON i18n)                        |
| `symbol_overwrite`        | TEXT    | Override quantity symbol (JSON i18n)              |
| `quantity_name_overwrite` | TEXT    | JSON i18n override of quantity name for this item |
| `latex_prefix`            | TEXT    | LaTeX prefix (e.g. `\Delta{}`)                    |
| `latex_suffix`            | TEXT    | LaTeX suffix                                      |

### `formula_relation`
Typed relationships between formulas.

| Column          | Type | Description                                                                              |
| --------------- | ---- | ---------------------------------------------------------------------------------------- |
| `formula_id`    | TEXT | FK → formula.id                                                                          |
| `related_id`    | TEXT | FK → formula.id                                                                          |
| `relation_type` | TEXT | `alternative`, `derivation`, `special_case`, `generalization`, `condition`, `assumption` |
| `description`   | TEXT | JSON i18n                                                                                |

### `quantity`
Physical quantities. The `dim_*` columns are populated from the `dimensions`
formula_item rows; new base dimensions are added by inserting new rows there.

| Column             | Type    | Description                                                 |
| ------------------ | ------- | ----------------------------------------------------------- |
| `id`               | TEXT    | Primary key                                                 |
| `name`             | TEXT    | JSON i18n                                                   |
| `symbol`           | TEXT    | LaTeX symbol                                                |
| `symbol_overwrite` | TEXT    | JSON i18n override of quantity symbol                       |
| `topic`            | TEXT    | ID into `tree.json`                                         |
| `difficulty`       | INTEGER | 1–10                                                        |
| `description`      | TEXT    | JSON i18n                                                   |
| `links`            | TEXT    | JSON array                                                  |
| `default_unit`     | TEXT    | JSON array: `[{"unit":"<id>","exponent":<n>},...]`          |
| `dim_M` … `dim_J`  | REAL    | SI base dimension exponents (one column per base dimension) |
| `created`          | TEXT    | Auto timestamp                                              |
| `modified`         | TEXT    | Auto timestamp                                              |

### `unit`
Units with conversion factors.

| Column         | Type    | Description                                       |
| -------------- | ------- | ------------------------------------------------- |
| `id`           | TEXT    | Primary key                                       |
| `name`         | TEXT    | JSON i18n                                         |
| `symbol`       | TEXT    | LaTeX symbol                                      |
| `quantity_id`  | TEXT    | FK → quantity.id                                  |
| `default_unit` | INTEGER | Primary unit for the quantity                     |
| `unit_system`  | TEXT    | SI / CGS / Imperial                               |
| `factor`       | REAL    | Conversion factor to SI                           |
| `latex_factor` | TEXT    | LaTeX display for factor (e.g. `\frac{180}{\pi}`) |
| `offset`       | REAL    | Conversion offset                                 |

## Seed Data

A single `seed.sql` file contains the initial formulas, quantities, and units.

Run `scifind_cli.py init` after editing the schema or seed data.

## Conventions

- **i18n JSON**: All user-facing text fields (`name`, `description`, `label`,
  `symbol_overwrite`, `quantity_name_overwrite`) are stored as JSON i18n
  (`{"en-us": "text"}`). Plain text is treated as already-localised.
- **Column order**: `symbol_overwrite` follows `symbol` in `quantity`;
  `latex_factor` follows `factor` in `unit`; `quantity_name_overwrite` follows
  `symbol_overwrite` in `formula_item`.
- **Similar quantities**: Quantities with identical dimensions (e.g.
  `potential_energy`, `rotational_energy`) are merged into a single `energy`
  quantity with `label` and `quantity_name_overwrite` to differentiate.
- **LaTeX coefficients**: Store raw LaTeX (e.g. `\pi`, `e`) directly in
  `latex_coef` rather than plain text identifiers.
