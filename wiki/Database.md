# Database Specification

SQLite database with 8 tables. Formulas are stored as [Reverse Polish
Notation (RPN)](https://en.wikipedia.org/wiki/Reverse_Polish_notation) token streams that are evaluated into expression trees at
render time. Operators and constants live in their own tables.

## `formula`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `name` | TEXT | JSON i18n: `{"en-us": "...", "en-uk": "..."}` |
| `topic` | TEXT | ID into `tree.json` |
| `difficulty` | INTEGER | 1–10 |
| `description` | TEXT | JSON i18n |
| `links` | TEXT | JSON array of URLs: `["https://...", ...]` |
| `created` / `modified` | TEXT | Auto timestamps |

## `operator`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `symbol` | TEXT | LaTeX display (`\cdot`, `\sin`, `=`); NULL = invisible (e.g. `mul`) |
| `math` | TEXT | Python expression for numeric evaluation; NULL when not computable (`=`, `\propto`) |
| `arity` | INTEGER | Number of operands (> 0) |
| `precedence` | INTEGER | Binding strength; higher binds tighter |
| `associativity` | TEXT | `left`, `right`, or `none` |
| `operator_type` | TEXT | `infix`, `prefix`, `postfix`, or `relational` |
| `paren_arg` | TEXT | JSON array of 0/1, length = arity; NOT NULL, default `[1]` |

Functions are arity-1 prefix operators.
The relational `=` (and `\propto`, `<`, `>`)
always forms the root of an expression tree.

`paren_arg` controls wrapping of operands in parentheses:
- `1` = the renderer may wrap that operand
- `0` = never

## `constant`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `name` | TEXT | JSON i18n |
| `symbol` | TEXT | LaTeX display (`\pi`, `c`) |
| `difficulty` | INTEGER | 1–10 |
| `description` | TEXT | JSON i18n |
| `links` | TEXT | JSON array of URLs |
| `value` | REAL | Numerical value; NULL for purely symbolic constants |
| `default_unit` | TEXT | JSON array `[{"unit":"<id>","exponent":<n>},...]`; only for dimensional constants |
| `quantity_id` | TEXT | FK → quantity.id; quantity whose name/unit applies (same dimensions); NULL = unlisted on quantity pages |

## `formula_token`
The RPN encoding of one formula. Primary key `(formula_id, position)`;
tokens are read in `position` order starting at 1. Operands push onto a
stack, operators pop their arity-many operands.

| Column | Type | Description |
|--------|------|-------------|
| `formula_id` | TEXT | FK → formula.id |
| `position` | INTEGER | Token order, starting at 1 |
| `token_kind` | TEXT | `quantity`, `constant`, `number`, or `operator` |
| `quantity_id` | TEXT | FK → quantity.id (when kind = quantity) |
| `constant_id` | TEXT | FK → constant.id (when kind = constant) |
| `operator_id` | TEXT | FK → operator.id (when kind = operator) |
| `value` | REAL | Numeric value (when kind = number) |
| `label` | TEXT | JSON i18n array of subscript parts |
| `symbol_overwrite` | TEXT | JSON i18n symbol override for this token |
| `quantity_name_overwrite` | TEXT | JSON i18n name override for this token |

A CHECK constraint enforces that exactly one of `quantity_id`,
`constant_id`, `operator_id`, or `value` is non-NULL per row.

## `formula_relation`
Relationships between formulas. Can be viewed in `quantity/<formula_relation.formula_id>`

| Column | Type | Description |
|--------|------|-------------|
| `formula_id` | TEXT | FK → formula.id |
| `related_id` | TEXT | FK → formula.id |
| `relation_type` | TEXT | `alternative`, `derivation`, `special_case`, `generalization`, `condition`, or `assumption` |
| `description` | TEXT | JSON i18n |

## `quantity`
The seven `dim_*` columns hold SI base dimension
exponents in fixed order M, L, T, I, Θ, N, J.

| Column                 | Type    | Description                                       |
| ---------------------- | ------- | ------------------------------------------------- |
| `id`                   | TEXT    | Primary key                                       |
| `name`                 | TEXT    | JSON i18n                                         |
| `symbol`               | TEXT    | LaTeX symbol                                      |
| `symbol_overwrite`     | TEXT    | JSON i18n symbol override                         |
| `topic`                | TEXT    | ID into `tree.json`                               |
| `difficulty`           | INTEGER | 1–10                                              |
| `description`          | TEXT    | JSON i18n                                         |
| `links`                | TEXT    | JSON array of URLs                                |
| `default_unit`         | TEXT    | JSON array `[{"unit":"<id>","exponent":<n>},...]` |
| `dim_*`                | REAL    | Base dimension exponents (NOT NULL, default 0)    |
| `created` / `modified` | TEXT    | Auto timestamps                                   |

## `unit`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `name` | TEXT | JSON i18n |
| `symbol` | TEXT | LaTeX symbol |
| `quantity_id` | TEXT | FK → quantity.id |
| `default_unit` | INTEGER | 1 marks the quantity's primary unit |
| `unit_system` | TEXT | `SI`, `CGS`, `Imperial`, or NULL (= any) |
| `factor` | REAL | Conversion factor to SI |
| `latex_factor` | TEXT | LaTeX display for the factor (e.g. `\frac{180}{\pi}`) |
| `offset` | REAL | Conversion offset |

## `si_prefix`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key (`k`, `M`, `\mu`, ...) |
| `symbol` | TEXT | LaTeX display prefix, prepended to the unit symbol |
| `name` | TEXT | JSON i18n prefix name, prepended to the unit name |
| `exponent` | INTEGER | Power of ten: kilo=3, centi=-2 |

## Seed Data

`seed.sql` contains all initial data: operators, constants,
quantities, units, formulas, tokens, and relations.
After editing schema or seed data, run:

```bash
python scifind_cli.py init --force
```
