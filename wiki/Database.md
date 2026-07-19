# Database Specification

SQLite database with 7 tables. Formulas are stored as Reverse Polish
Notation (RPN) token streams that are evaluated into expression trees
at render time. Mathematical and physical constants, plus reusable
operators, live in their own tables.

## Schema (`schema.sql`)

### `formula`
One row per equation.

| Column        | Type    | Description                                    |
| ------------- | ------- | ---------------------------------------------- |
| `id`          | TEXT    | Primary key                                    |
| `name`        | TEXT    | JSON i18n (`{"en-us": "...","en-uk": "..."}`) |
| `topic`       | TEXT    | ID into `tree.json`                            |
| `difficulty`  | INTEGER | 1–10                                           |
| `description` | TEXT    | JSON i18n                                      |
| `links`       | TEXT    | JSON array: `[{...}]`                         |
| `created`     | TEXT    | Auto timestamp                                 |
| `modified`    | TEXT    | Auto timestamp                                 |

### `operator`
A reusable operator: arithmetic, function, decorator, or relational.

| Column          | Type    | Description                                                                |
| --------------- | ------- | -------------------------------------------------------------------------- |
| `id`            | TEXT    | Primary key                                                                |
| `symbol`        | TEXT    | LaTeX display (`\cdot`, `\sin`, `=`); NULL means invisible (e.g. `mul`)    |
| `math`          | TEXT    | Python expression for evaluation; NULL when not computable (`=`, `\propto`) |
| `arity`         | INTEGER | Number of operands                                                         |
| `precedence`    | INTEGER | Binding strength; higher binds tighter                                     |
| `associativity` | TEXT    | `left`, `right`, or `none`                                                 |
| `operator_type` | TEXT    | `infix`, `prefix`, `postfix`, or `relational`                              |

Functions are represented as arity-1 prefix operators with a
LaTeX-style symbol (e.g. `\sin`, `\cos`, `\sqrt`). The relational
operator `=` (and the rare `\propto`, `<`, `>`) is structurally special:
it always forms the root of a formula's expression tree.

### `constant`
A reusable named constant, mathematical or physical.

| Column         | Type    | Description                                                |
| -------------- | ------- | ---------------------------------------------------------- |
| `id`           | TEXT    | Primary key                                                |
| `name`         | TEXT    | JSON i18n                                                  |
| `symbol`       | TEXT    | LaTeX display (`\pi`, `c`)                                 |
| `value`        | REAL    | Numerical value (NULL for purely symbolic constants)       |
| `default_unit` | TEXT    | JSON array (only used for dimensional physical constants)   |

The `default_unit` field is the same shape as `quantity.default_unit`:
`[{"unit":"<id>","exponent":<n>},...]`. Dimensional physical constants
such as `gravitational_constant` use this; pure mathematical constants
(`pi`, `euler_e`) leave it NULL.

### `formula_token`
An RPN-encoded formula. Tokens are read in `position` order. Operands
push onto a stack; operators pop their arity-many operands and push
the result. After the last token, the stack should hold a single
node which is the expression tree root.

| Column                   | Type    | Description                                                          |
| ------------------------ | ------- | -------------------------------------------------------------------- |
| `formula_id`             | TEXT    | FK → formula.id                                                      |
| `position`               | INTEGER | Token order, starting at 1                                           |
| `token_kind`             | TEXT    | `quantity`, `constant`, `number`, or `operator`                      |
| `quantity_id`            | TEXT    | FK → quantity.id (when `token_kind='quantity'`)                       |
| `constant_id`            | TEXT    | FK → constant.id (when `token_kind='constant'`)                       |
| `operator_id`            | TEXT    | FK → operator.id (when `token_kind='operator'`)                       |
| `value`                  | REAL    | Numeric value (when `token_kind='number'`)                            |
| `label`                  | TEXT    | JSON i18n array of subscript parts (`["1","2"]` → `_{12}`)            |
| `symbol_overwrite`       | TEXT    | JSON i18n override of the quantity/constant symbol                    |
| `quantity_name_overwrite`| TEXT    | JSON i18n override of the quantity name for this token                 |

Exactly one of `quantity_id`, `constant_id`, `operator_id`, or `value`
is non-NULL per row (enforced by a CHECK constraint).

A row's `label`, `symbol_overwrite`, and `quantity_name_overwrite` are
decorations attached to the operand or to the operator result.

### `formula_relation`
Typed relationships between formulas.

| Column          | Type | Description                                                                              |
| --------------- | ---- | ---------------------------------------------------------------------------------------- |
| `formula_id`    | TEXT | FK → formula.id                                                                          |
| `related_id`    | TEXT | FK → formula.id                                                                          |
| `relation_type` | TEXT | `alternative`, `derivation`, `special_case`, `generalization`, `condition`, `assumption` |
| `description`   | TEXT | JSON i18n                                                                                |

### `quantity`
Physical quantities. The seven `dim_*` columns are populated directly
in the seed for the seven base dimensions (M, L, T, I, Θ, N, J).

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

The `dim_*` column order is fixed at M, L, T, I, Θ, N, J. To add a new
base dimension you would alter the table to add the column; the
canonical list in `scifind_lib._BASE_DIMENSION_ORDER` must be updated
in lockstep.

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

A single `seed.sql` file plus two helper files contain the initial data:

- `seed.sql` — quantities, units, formulas, formula tokens, formula
  relations.
- `operators.sql` — the operator catalogue (reusable across formulas).
- `constants.sql` — the constant catalogue (reusable across formulas).

Run `python scifind_cli.py init` (or `init --force` to wipe) after
editing the schema or seed data.

## Conversion

The conversion script lives in `tools/convert_formulas.py`. It reads a
legacy `seed.sql.old` (with `formula_item` rows) and emits equivalent
`formula_token` rows. It is a one-off migration tool kept for reference
and re-runs; it is not part of the runtime. The current `seed.sql`
already contains the converted `formula_token` INSERTs; the script is
only needed if you have new legacy data to migrate.

The script encapsulates every quirk of the legacy encoding (implicit
`c²`, implicit `pi`, missing `\cos` in the work formula, etc.).

## Rendering

`scifind_lib.render_formula` reads ordered `formula_token` rows for one
formula, evaluates them onto a stack to build an expression tree, and
renders the tree as LaTeX with the minimum required parentheses. The
renderer recognises a few display idioms:

- The `frac` operator renders as `\frac{a}{b}`.
- The `pow` operator renders as `a^{b}`.
- Implicit multiplication (the `mul` operator with no symbol) is
  rendered as `\cdot` between two numbers, plain concatenation when
  either side is a number, and a single space otherwise.

## Conventions

- **i18n JSON**: All user-facing text fields (`name`, `description`,
  `symbol_overwrite`, `quantity_name_overwrite`, `label`) are stored
  as JSON i18n (`{"en-us": "text"}`). Plain text is treated as
  already-localised.
- **Operators are shared**: A new operator (say `\arccos`) goes into
  `operators.sql` once; every formula can reference it by id.
- **Constants are shared**: A new constant (say `\hbar`) goes into
  `constants.sql` once.
- **Similar quantities**: Quantities with identical dimensions
  (e.g. `potential_energy`, `rotational_energy`) are merged into a
  single `energy` quantity with `label` and `quantity_name_overwrite`
  to differentiate.
