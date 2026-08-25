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

All user-facing DB fields (`name`, `description`, `label`,
`symbol_overwrite`, `quantity_name_overwrite`) are i18n JSON.

```json
{
  "en-us": "...",
  "en-uk": "..."
}
```

## Creating Formulas

### The easy way: `/create`

1. Open `/create` in the web app
2. Write the equation using quantity / constant / operator IDs (e.g. `force = mass mul acceleration`)
3. Set the topic, difficulty, description and links
4. Page generates ready-to-submit SQL (both the `formula` and all `formula_token`s.

### Manual SQL

1. Insert a row into `formula`.
2. Insert `formula_token` rows in `position` order. Each token is one of:
   - `token_kind='quantity'` + `quantity_id`
     - use the `drop` sentinel to blank an operand slot
     - use `dimensionless` with a `symbol_overwrite` for one-time coefficients
   - `token_kind='constant'` + `constant_id`
   - `token_kind='number'` + `value`
      - a numerical value
   - `token_kind='operator'` + `operator_id`
3. Optional decorations per token: `label`, `symbol_overwrite`, `quantity_name_overwrite`.
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

### Adding an Operator

Add a row to `seed.sql` and re-initialise.
Let's use `\cosh` as an example:

```sql
INSERT OR IGNORE INTO operator (id, symbol, math, arity, precedence, associativity, operator_type, paren_arg)
VALUES ('cosh', '\cosh', 'math.cosh(a)', 1, 30, 'right', 'prefix', '[1]');
```

### Adding a Constant

```sql
INSERT OR IGNORE INTO constant (id, name, symbol, value, default_unit)
VALUES ('electron_volt', '{"en-us": "Electronvolt"}', '\text{eV}', 1.602176634e-19,
        '[{"unit":"joule","exponent":1}]');
```

## Rendering Rules

Paren wrapping is a property of the **operator** via `operator.paren_arg`
(a JSON array where length = arity).
- `1` = the renderer may wrap that operand in parentheses
- `0` = never

| Operator                     | `paren_arg` | Notes                                                             |
| ---------------------------- | ----------- | ----------------------------------------------------------------- |
| `add`, `mul`, `eq`, `cdot`   | `[1,1]`     | both operands may wrap                                            |
| `frac`                       | `[0,0]`     | operands inside `{...}` of the macro                              |
| `pow`                        | `[1,0]`     | exponent lives inside `^{...}`                                    |
| `sin`, `cos`, `tan`, …       | `[1]`       | argument may wrap                                                 |
| `Delta`, `nabla`             | `[1]`       | argument may wrap                                                 |
| `overl`                      | `[0]`       | argument never wraps                                              |
| `log`                        | `[0,0]`     | arity-2 infix `\log_{base}{arg}`; base `euler_e` emits `\ln{arg}` |
| `sqrt`                       | `[0,0]`     | arity-2 infix `\sqrt{radicand}` or `\sqrt[index]{radicand}`       |
| `sum`, `int`, `prod`, `oint` | `[0,0,0]`   | arity-3 infix `\op_{from}^{to}{body}`                             |
| `lim`                        | `[0,0,0]`   | arity-3 infix `\lim_{var \to val}{body}`                          |

If you are using `create/`, you can force a change in the order of operations with parentheses:
`(m+m)^(m+m)` renders as `\left(m + m\right)^{m + m}` -> `(m+m)ᵐ⁺ᵐ`.
The parentheses in the exponent are dropped due to `paren_arg`.

### The `drop` sentinel

The `drop` quantity has an empty symbol and zero dimensions. Use it in
any operand slot to blank that slot out. It is invisible to the user in
variable lists, detail tables, and dimensional analysis.

| Source | Renders as |
|--------|------------|
| `drop x sub` | `-x` (unary minus) |
| `log drop x` | `\log{x}` |
| `log b drop` | `\log_{b}` |
| `log euler_e x` | `\ln{x}` |
| `sqrt x 2` / `sqrt x drop` | `\sqrt{x}` |
| `sqrt x 3` | `\sqrt[3]{x}` |
| `sum 1 drop x` | `\sum_{1}{x}` |
| `sum drop 10 x` | `\sum^{10}{x}` |
| `sum drop drop x` | `\sum{x}` |
| `lim x drop body` | `\lim{body}` |
