# Database Specification

SQLite database with 10 tables. Formulas are stored as [Reverse Polish
Notation (RPN)](https://en.wikipedia.org/wiki/Reverse_Polish_notation) token streams that are evaluated into expression trees at
render time. Operators and constants live in their own tables.

## `topic`

The science/branch/topic tree (replaces `tree.json`). `position` is the
depth-first order over the tree (e.g. `kinematics` is `2` under
`classical_mechanics`); `parent_id` is NULL for the root sciences.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key (e.g. `kinematics`) |
| `parent_id` | TEXT | FK → topic.id; NULL for roots |
| `name` | TEXT | JSON i18n: `{"en-us": "Kinematics", "cs-cz": "Kinematika"}` |
| `name_genative` | TEXT | JSON i18n genitive: `{"cs-cz": "Kinematiky"}` |
| `position` | INTEGER | Depth-first order (e.g. `2`) |

## `formula`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `name` | TEXT | JSON i18n: `{"en-us": "...", "en-uk": "..."}` |
| `topic_id` | TEXT | FK → topic.id |
| `difficulty` | INTEGER | 1–10 |
| `description` | TEXT | JSON i18n |
| `links` | TEXT | JSON array of URLs: `["https://...", ...]` |
| `created` / `modified` | TEXT | Auto timestamps |

## `operator`

Operators are fully data-driven: the parser, renderer and dimension
checker read everything from these columns, so no operator id or symbol
appears in code branches. Special cases are stored in the rows
themselves (see [Development](Development)) — never as extra operators
or code paths.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `symbol` | TEXT | LaTeX display (`\cdot`, `\sin`, `=`); NULL = juxtaposition (e.g. `mul`) |
| `aliases` | TEXT | JSON array of surface match strings — the id spelling and/or LaTeX symbol (e.g. `["sin", "\\sin"]`); drives the tokeniser's longest-match scan |
| `arity` | INTEGER | Number of operands (> 0) |
| `precedence` | INTEGER | Binding strength; higher binds tighter |
| `associativity` | TEXT | `left`, `right`, or `none` (CHECK) |
| `type` | TEXT | `infix`, `prefix`, `postfix`, or `relational` (CHECK); `relational` = non-associative comparison, and `a op b op c` folds into one n-ary node |
| `latex_template` | TEXT | `[[0]]`…`[[n]]` operand slots, `[[i!]]` for template-grouped slots (skip precedence parens), `[[i?then:else]]` emptiness conditionals, `[[i=matcher?then:else]]` value tests (`num:<float>`, `const:<id>`, `qty:<id>`) |
| `dim_spec` | TEXT | Readable dimension math, evaluated by one uniform engine: `;`-separated clauses with exactly one `result` clause — `drop(0)` (blank operands dropped first), `require same(all)` (operands must agree; result is the common vector), `require dimless(0, 1)` (operands must be dimensionless), `result same` / `result zero` / `result any` (relational only) / `result dims(0)+dims(1)` / `result dims(0)-dims(1)` / `result dims(0)*value(1)` / `result dims(0)/value(1)` |

Parentheses are `paren` tokens handled by the parser, not operator rows.
Prefix sums/integrals (`sum`, `prod`, `oint`, `lim`, `int`) take
lower/upper/body operands; blank `drop` bounds render via template
conditionals. Unary minus is `sub` with a blank left operand (its own
template renders `-x`); natural log is `log` with an `euler_e` base
(a value matcher renders `\ln`); square root is binary `sqrt` whose
index `2` is omitted by a value matcher.

The relational `=` (and `\propto`, `<`, `>`, …)
always forms the root of an expression tree; dimensions are read off
its left-hand side.

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
| `name_overwrite` | TEXT | JSON i18n name override for this token |

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
Base dimensions are marked per row: `dim_symbol` holds the symbol
(e.g. `M` for `mass`) and `dim_position` its order (e.g. `0`);
the exponent column name derives as `'dim_' + dim_symbol`
(e.g. `dim_M`). Derived quantities leave both NULL.

| Column                 | Type    | Description                                       |
| ---------------------- | ------- | ------------------------------------------------- |
| `id`                   | TEXT    | Primary key                                       |
| `name`                 | TEXT    | JSON i18n                                         |
| `symbol`               | TEXT    | LaTeX symbol                                      |
| `symbol_overwrite`     | TEXT    | JSON i18n symbol override                         |
| `topic_id`             | TEXT    | FK → topic.id                                     |
| `difficulty`           | INTEGER | 1–10                                              |
| `description`          | TEXT    | JSON i18n                                         |
| `links`                | TEXT    | JSON array of URLs                                |
| `default_unit`         | TEXT    | JSON array `[{"unit":"<id>","exponent":<n>},...]` |
| `dim_symbol`           | TEXT    | Base-dimension symbol, NULL for derived rows      |
| `dim_position`         | INTEGER | Order among base dimensions                       |
| `dim_*`                | REAL    | Base dimension exponents (NOT NULL, default 0)    |
| `created` / `modified` | TEXT    | Auto timestamps                                   |

## `unit`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Primary key |
| `name` | TEXT | JSON i18n |
| `symbol` | TEXT | LaTeX symbol |
| `quantity_id` | TEXT | FK → quantity.id |
| `system` | TEXT | `SI`, `CGS`, `Imperial`, or NULL (= any) |
| `is_base` | INTEGER | 1 marks the quantity's primary unit (or one of them per system) |
| `reference_unit_id` | TEXT | ID into `unit`, or a `compound_unit` slug (no DB-level constraint; `validate_graph` in `conversion.py` checks reachability at runtime), NULL = root |
| `factor_numerator` | REAL | Numerator of the scaling factor; NULL means 1 |
| `factor_denominator` | REAL | Denominator of the scaling factor; NULL means 1 (e.g. `1 inch = 1/12 ft` stores denominator `12`) |
| `constant_id` | TEXT | FK → constant.id; the constant scales the factor (`constant_power` ±1) or offsets the reference value (`constant_shift` ±1; used for temperature absolute zero) |
| `constant_power` | REAL | Exponent applied to the constant in the scale term (`1` = multiply, `-1` = divide, `0` = ignore) |
| `constant_shift` | REAL | Coefficient of the constant in the shift term (`1` = add, `-1` = subtract, `0` = none) |
| `offset` | REAL | Additive offset (default 0) |

The reference graph is affine:

```
F    = factor_numerator / factor_denominator (NULL = 1 on both sides)
x_ref = F * C^constant_power * (x_row + offset) + constant_shift * C
```

where `C` is the constant value (terms vanish when `constant_id` is
NULL), e.g. `1 °F`: numerator 5, denominator 9, power 0, shift −1,
offset 459.67 → `x_C = (5/9)(x_F + 459.67) − 273.15`.
Stored fractions render literally (`5/9`, `101325/760` for torr), so no
temperature factor is hard-coded as a decimal.

## `compound_unit`

Some values like `id` and `name` of `compound_unit` values are derived from `unit`.

| Column             | Type    | Description                                                                                      |
| ------------------ | ------- | ------------------------------------------------------------------------------------------------ |
| `quantity_id`      | TEXT    | FK → quantity.id; first half of the primary key                                                  |
| `name_overwrite`   | TEXT    | JSON i18n override of the auto-derived name                                                      |
| `symbol_overwrite` | TEXT    | LaTeX override; NULL means derive from the `unit` parts                                          |
| `unit`             | TEXT    | JSON array `[{"unit":"<id>","prefix":<int>,"exponent":<n>},...]`; second half of the primary key |
| `system`           | TEXT    | `SI`, `CGS`, `Imperial`, or NULL (= any)                                                         |
| `is_base`          | INTEGER | 1 marks the quantity's primary compound (or one of them per system)                              |

A compound's value derives from its `unit` parts.

## `si_prefix`

| Column     | Type    | Description                                        |
| ---------- | ------- | -------------------------------------------------- |
| `id`       | TEXT    | Primary key (`k`, `M`, `\mu`, ...)                 |
| `symbol`   | TEXT    | LaTeX display prefix, prepended to the unit symbol |
| `name`     | TEXT    | JSON i18n prefix name, prepended to the unit name  |
| `exponent` | INTEGER | Power of ten: kilo=3, centi=-2                     |

## Seed Data

`seed.sql` contains all initial data: operators, constants,
quantities, units, formulas, tokens, and relations.
After editing schema or seed data, run:

```bash
python scifind_cli.py init --force
```
