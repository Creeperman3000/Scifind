# Development

## Setup

```bash
git clone <repo>
cd Scifind
pip install -r requirements.txt
python scifind_cli.py init
```

The database is created at `scifind.db` in the project root (override with
`--db` or `SCIFIND_DB`).

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

A smoke test exercises the full public surface (DB, parser, renderer,
queries, export, all Flask routes). Run it with:

```bash
python tests/smoke.py
```

Or use Flask's test client for a quick spot-check:

```python
from webapp import app
app.config['TESTING'] = True
with app.test_client() as c:
    for route in ['/formulas', '/quantities', '/formula/circle_area', '/quantity/area', '/search?q=circle']:
        r = c.get(route)
        print(f'{route}: {"OK" if r.status_code == 200 else "FAIL"} ({r.status_code})')
```

## I18n

All user-facing text fields (`name`, `description`, `label`,
`symbol_overwrite`, `quantity_name_overwrite`) use JSON i18n:

```json
{"en-us": "...", "en-uk": "..."}
```

The `localise()` and `localise_english()` helpers handle both plain text and
JSON, falling back to `en-us` if the requested locale isn't present. Supported
locales: `en-us`, `en-uk`, `cs-cz`.

## Adding a Formula

Formulas are stored as RPN token streams. The easiest way to add a
new one is to write the tokens directly, then re-initialise the DB.

1. Insert a row into `formula` with a unique `id`, name, topic, and
   difficulty.
2. Insert one or more rows into `formula_token` for the formula, in
   `position` order. For each token, set:
   - `token_kind = 'quantity'` and `quantity_id = '…'`
   - `token_kind = 'constant'` and `constant_id = 'pi'` / `'euler_e'`
     / `'speed_of_light'` / etc.
   - `token_kind = 'number'` and `value = 0.5`
   - `token_kind = 'operator'` and `operator_id = 'add'` / `'mul'` /
     `'pow'` / `'div'` / `'eq'` / `'sin'` / etc.
3. The RPN expression for a one-product term with no sum is:
   ```
   <operands…> <binary-op> …  <eq>
   ```
   For `E_k = ½ m v²`:
   ```
   1: quantity energy     (label: "k")
   2: number 2
   3: number -1
   4: operator pow
   5: quantity mass
   6: operator mul
   7: quantity velocity
   8: number 2
   9: operator pow
   10: operator mul
   11: operator eq
   ```
4. Optional decorations: `label` (subscript, JSON i18n array),
   `symbol_overwrite` (override the quantity symbol, JSON i18n),
   `quantity_name_overwrite` (override the displayed quantity name).
5. Link related formulas via `formula_relation`.
6. Re-initialise the database: `python scifind_cli.py init --force`.

### Adding a New Operator

Add a row to `seed.sql` and re-initialise. For example, to add
`\arccos` (arity 1, prefix):

```sql
INSERT OR IGNORE INTO operator (id, symbol, math, arity, precedence, associativity, operator_type)
VALUES ('arccos', '\\arccos', 'math.acos(a)', 1, 30, 'right', 'prefix');
```

### Adding a New Constant

Add a row to `seed.sql` and re-initialise. For example, the
Planck constant:

```sql
INSERT OR IGNORE INTO constant (id, name, symbol, value, default_unit)
VALUES ('planck_constant', '{"en-us": "Planck constant"}', 'h', 6.62607015e-34,
        '[{"unit":"joule","exponent":1},{"unit":"second","exponent":1}]');
```

### Paren Wrapping and `paren_arg`

Paren wrapping is a property of the **operator**, not the formula
token. The `operator.paren_arg` column is a JSON array of length =
operator.arity; each entry is `1` (the renderer may wrap this operand in
`\left( ... \right)` based on precedence and source syntax) or `0`
(never wrap — the operator's macro syntax already scopes this operand).

| Operator                     | `paren_arg` | Why                                                                                                                                                         |
| ---------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `add`, `mul`, `eq`, `cdot`   | `[1,1]`     | both operands may be wrapped                                                                                                                                |
| `frac`                       | `[0,0]`     | both operands are inside `{...}` of the macro                                                                                                               |
| `pow`                        | `[1,0]`     | base takes the next token (may wrap), exponent is inside `^{...}`                                                                                           |
| `sin`, `cos`, `tan`           | `[1]`       | argument may wrap (`\sin{x+y}` reads ambiguously without scope)                                                                                             |
| `overl`, `Delta`, `nabla`    | `[1]`       | argument may wrap (macro is a letter / token, but user source can still chain via mul)                                                                      |
| `log`                        | `[0,0]`     | arity-2 infix `\log_{base}{arg}`; both operands are in macro scopes (base of `euler_e` emits `\ln{arg}`)                                                   |
| `sqrt`                       | `[0,0]`     | arity-2 infix `\sqrt{radicand}` (or `\sqrt[index]{radicand}`); both operands are in macro scopes (index is omitted when literal 2)                          |
| `sum`, `int`, `prod`, `oint` | `[0,0,0]`   | arity-3 infix `\sum_{from}^{to}{body}` / `\int_{from}^{to}{body}` / `\prod_{from}^{to}{body}` / `\oint_{from}^{to}{body}`; all operands are in macro scopes |
| `lim`                        | `[0,0,0]`   | arity-3 infix `\lim_{var \to val}{body}`; all operands are in macro scopes                                                                                  |

### Dropping operands with the `drop` quantity

The `drop` quantity is a sentinel with an empty symbol and zero
dimensions. Drop it into any operand slot to blank that slot out in
the rendered output. The operator arity is fixed — `drop` is just a
no-op operand. A `drop` on the left of `sub` is the unary minus (the
former `neg` operator): `drop x sub` renders as `-x`.

| Source                            | Renders as                |
| --------------------------------- | ------------------------- |
| `drop x sub`                      | `-x` (unary minus)        |
| `log drop x`                      | `\log{x}`                 |
| `log b drop`                      | `\log_{b}`                |
| `log b drop` (empty arg)          | (empty — guard in renderer) |
| `log euler_e x`                   | `\ln{x}` (implicit euler-omission) |
| `sqrt x 2`                        | `\sqrt{x}` (implicit 2-omission) |
| `sqrt x 3`                        | `\sqrt[3]{x}`             |
| `sqrt x drop`                     | `\sqrt{x}` (drop ≡ default 2) |
| `sum 1 drop x`                    | `\sum_{1}{x}`             |
| `sum drop 10 x`                   | `\sum^{10}{x}`            |
| `sum drop drop x`                 | `\sum{x}`                 |
| `sum 1 10 drop` (empty body)      | (empty — guard in renderer) |
| `int 1 drop x`                    | `\int_{1}{x}`             |
| `int drop 10 x`                   | `\int^{10}{x}`            |
| `int drop drop x`                 | `\int{x}`                 |
| `prod 1 drop x`                   | `\prod_{1}{x}`            |
| `prod drop drop x`                | `\prod{x}`                |
| `oint 1 10 x`                     | `\oint_{1}^{10}{x}`       |
| `oint drop drop x`                | `\oint{x}`                |
| `lim x drop body`                 | `\lim{body}` (one-sided limit — subscript dropped, not `\lim_{x \to}`) |
| `lim drop x body`                 | `\lim{body}` (no variable — subscript dropped) |
| `lim drop drop body`              | `\lim{body}`              |
| `lim x 0 drop` (empty body)       | (empty — guard in renderer) |

`drop` is filtered out of the variables list, the formula detail table,
and the dimensional analysis, so it never appears as a "real" variable
to the user.

User-explicit parens in source equations (`(mass + mass) ^ 2`) are
preserved end-to-end: the parser tags the operand that came from a
`(...)` group, and the renderer respects the `paren_arg` opt-out. So
`(m+m)^(m+m)` renders as `\left(m + m\right)^{m + m}` — the exponent
parens are dropped because `pow.paren_arg[1]=0`, regardless of what
the user wrote.

The renderer also has refined rules for the invisible `mul` operator
(no symbol). Implicit multiplication follows the standard LaTeX idiom:
`3x` (number × variable), `xy` (variable × variable), `3×4`
(number × number, `\times`), `3(x+1)` (number × expression),
`3\,\frac{x}{y}` (number × fraction), `2\pi` (number × constant),
`2\sin x` (number × function). Dot/cross products and scientific
notation are not auto-detected — use the explicit `cdot` and `times`
operators for those.

## Adding Seed Data

Edit `seed.sql`. Re-initialise with:

```bash
python scifind_cli.py init --force   # drops and recreates DB
```

## Export

```bash
python scifind_cli.py export --format csv --output formulas.csv
```

Supported formats: `csv`, `csvdir`, `xlsx`, `ods`, `sql`.

## Edge Cases

- **RPN underflow / over-render**: All formulas are checked for a
  complete reduction at the end of evaluation; an underflow means
  the data is malformed and the renderer raises an error.
- **Common reciprocals**: ½, ⅓, ¼, etc. render as `\frac{1}{N}` when
  they appear as a bare number.
- **Power `^(-1)`**: Renders as `\frac{1}{base}` for clean display.
- **Negation**: `-1 * x` renders as `-x`; `Q + (-W)` renders as
  `Q - W` (the `+` flips to `-`).
- **sqlite3.Row vs dict**: Access columns by `item["col"]` using
  `or ""` fallback (works with both).
