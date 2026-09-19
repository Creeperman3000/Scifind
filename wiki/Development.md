# Development

## Setup

```bash
git clone https://github.com/Creeperman3000/Scifind.git
cd Scifind
pip install -r requirements.txt
python scifind_cli.py init        # for CLI only
python webapp.py                  # for webapp too
```

See [Web App](Web-App) for more.

## I18n

Most user-facing DB fields (`name`, `description`, `label`,
`symbol_overwrite`, `name_overwrite`) are i18n JSON.

```json
{
  "en-us": "...",
  "en-uk": "..."
}
```

## Creating Formulas

### 1. The easy way: `/create`

1. Open `/create` in the web app
2. Write the equation using quantity / constant / operator IDs (e.g. `force = mass mul acceleration`)
3. Set the topic, difficulty, description and links
4. Page generates SQL (both the `formula` and all `formula_token`s.

### 2. Manual SQL

1. Insert a row into `formula`.
2. Insert `formula_token` rows in `position` order. Each token is one of:
   - `token_kind='quantity'` + `quantity_id`
     - use the `drop` sentinel to blank an operand slot
     - use `dimensionless` with a `symbol_overwrite` for one-time coefficients
   - `token_kind='constant'` + `constant_id`
   - `token_kind='number'` + `value`
      - a numerical value
   - `token_kind='operator'` + `operator_id`
3. Optional decorations per token: `label`, `symbol_overwrite`, `name_overwrite`.
4. Link related formulas via `formula_relation`.
5. Rebuild: `python scifind_cli.py init --force`.

For example, `E_k = ½ m v²` (`kinetic_energy_formula` in the seed) is:

| Pos | Token    | ID / value      |
| --- | -------- | --------------- |
| 1   | quantity | `energy`        |
| 2   | number   | `1`             |
| 3   | number   | `2` |
| 4   | operator | `frac`          |
| 5   | quantity | `mass`          |
| 6   | operator | `mul`           |
| 7   | quantity | `velocity`      |
| 8   | number   | `2`             |
| 9   | operator | `pow`           |
| 10  | operator | `mul`           |
| 11  | operator | `eq`            |

### 3. Via Scifind-formulas

```bash
git clone https://github.com/Creeperman3000/Scifind-formulas.git
```

Modify, add or remove formulas in the `formulas/` directory.

### Adding an Operator

Add a row to `seed.sql` and re-initialise — no code changes needed.
The parser, renderer and dimension checker all read their behaviour
from the row. Let's use `\cosh` as an example:

```sql
INSERT OR IGNORE INTO operator
  (id, symbol, aliases, arity, precedence, associativity, type,
   latex_template, dim_spec)
VALUES ('cosh', '\cosh', '["cosh", "\\cosh"]', 1, 30, 'right', 'prefix',
        '\cosh{[[0!]]}', 'require dimless(all); result zero');
```

- `type` is `infix`, `prefix`, `postfix` or `relational`;
  `associativity` is `left`, `right` or `none`. Comparisons are
  `relational` (non-associative), and `a op b op c` folds into one
  n-ary node.
- `latex_template` places operands via `[[0]]`…`[[n]]`. `[[i!]]` skips
  precedence parens where the template already groups the slot (inside
  `{...}`). `[[i?then:else]]` renders `then` only when operand *i*
  renders non-empty (a blank `drop` slot renders empty, so e.g. `sub`
  uses `[[0?[[0]] - [[1]]:-[[1]]]]` for unary minus).
  `[[i=matcher?then:else]]` tests operand *values*: `num:<float>`,
  `const:<id>` or `qty:<id>` — e.g. `log` renders `\ln` when its base
  is `euler_e`, `sqrt` omits the index when it is `2`. Branches may
  nest; everything else (including `{`/`}`) is literal text.
- `dim_spec` is readable operand math, evaluated by one uniform engine (no
  per-operator branches): `;`-separated clauses with exactly one `result`
  clause — `drop(0)` (blank `drop` operands dropped before evaluation —
  `sub` declares it so a blank left operand leaves the right side's
  dimensions), `require same(all)` or `require same(0, 1)` (those operands
  must agree; the result is their common vector, returned via
  `result same`), `require dimless(all)` or `require dimless(1)` (those
  operands must be dimensionless), and one of `result same`
  (`add`, `sub`), `result zero` (`sin`, `log`), `result any`
  (`relational` comparisons only) or a linear combination such as
  `result dims(0)+dims(1)` (`mul`), `result dims(0)-dims(1)` (`div`),
  `result dims(2)` (`sum` bounds ignored), `result dims(0)*value(1)`
  (`pow`: scale by another operand's numeric value) or
  `result dims(0)/value(1)` (`sqrt`).
- Surface spellings (id and/or LaTeX symbol) go in the `aliases`
  JSON array; parentheses are `paren` tokens handled by the parser,
  not operator rows.

### Adding a Constant

```sql
INSERT OR IGNORE INTO constant (id, name, symbol, value, default_unit)
VALUES ('electron_volt', '{"en-us": "Electronvolt"}', '\text{eV}', 1.602176634e-19,
        '[{"unit":"joule","exponent":1}]');
```

## Rendering Rules

Parentheses are decided generically from precedence and associativity:
a child binding looser than its parent wraps, equal precedence wraps per
associativity (left-associative wraps the right operand and vice versa,
non-associative always wraps), and a postfix parent wraps an
equal-precedence child (so `(m^2)!` keeps its parens — `m^{2}!` would
attach `!` to `2`). Template slots written `[[i!]]` skip the precedence
parens because the template already groups them (e.g. inside
`\frac{...}{...}`); self-delimited children (`frac` blocks, `prefix`
functions like `\sin{...}`, `abs` delimiters) never wrap either.
Redundant source parentheses are normalised away — a child wraps only
when dropping the parens would change the meaning — so `m+(a·t)`
renders as `m + a t`.

If you are using `create/`, you can force a change in the order of operations with parentheses:
`(m+m)^(m+m)` renders as `\left(m + m\right)^{m + m}` -> `(m+m)ᵐ⁺ᵐ`.
The exponent needs no parens (it lives inside `^{...}`).

### Placeholders and value-dependent rendering

The `drop` backing quantity (empty symbol, hidden, zero dimensions)
marks a blank operand slot. It renders empty like any empty-symbol
quantity, so template conditionals (`[[i?then:else]]`) omit its
wrappers accordingly and juxtaposition drops its side; no code names
it. Special cases live in the operator rows as template data:

| Source | Renders as |
|--------|------------|
| `drop sub x` | `-x` (unary minus, via `sub`'s own template) |
| `log euler_e x` | `\ln{x}` (value matcher on the base) |
| `log b x` | `\log_{b}{x}` |
| `sqrt x 2` | `\sqrt{x}` (value matcher on the index) |
| `sqrt x 3` | `\sqrt[3]{x}` |
| `sum 1 drop x` | `\sum_{1}{x}` |
| `sum drop 10 x` | `\sum^{10}{x}` |
| `sum drop drop x` | `\sum{x}` |
| `lim x drop body` | `\lim{body}` |

Dimensions treat blank slots generically too: each operator's
`dim_spec` may declare `drop(...)` indexes dropped before evaluation
(`sub` declares `drop(0)`), while a real empty-symbol operand such as
`dimensionless` keeps its normal zero-dimension meaning everywhere
else.
