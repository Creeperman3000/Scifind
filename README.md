# Physics cheat sheet database schema

## Idea

This is a project for a list of physics formulas. The tables show how each database is structured.

## Database Spec — Physics Cheat Sheets

### `formulas`

| Column | Type | i18n | Notes |
|--------|------|------|-------|
| id | TEXT PK | | slug, e.g. `newton_second` |
| name | TEXT (JSON) | ✓ | `{"en":"Newton's Second Law"}` |
| science | TEXT (JSON) | ✓ | Physics (might expand) |
| branch | TEXT (JSON) | ✓ | Classical Mechanics|
| topic | TEXT (JSON) | ✓ | Kinematics |
| difficulty | INTEGER | | 1–10 |
| description | TEXT (JSON) | ✓ | |
| links | TEXT (JSON) | ✓ | `[{"label":{i18n},"url":"..."}]` |
| alternative_formulas | TEXT (JSON) | | IDs of formulas sharing the same primary quantity |
| related_formulas | TEXT (JSON) | | IDs of conceptually related formulas |
| conditioned_formulas | TEXT (JSON) | | IDs of formulas where a certain condition is met |
| created_at | TEXT | | |
| updated_at | TEXT | | |


| id | name (en) | branch | topic | difficulty |
|----|-----------|--------|-------|------------|
| `newton_second` | Newton's Second Law | Classical Mechanics | Dynamics | 2 |
| `suvat_v2` | SUVAT v² = u² + 2as | Classical Mechanics | Kinematics | 3 |
| `ideal_gas_law` | Ideal Gas Law | Thermodynamics | Equations of State | 4 |

---

### `formula_items`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| formula_id | TEXT FK | |
| term | INTEGER | groups factors that multiply; different term = added |
| is_primary | BOOLEAN | 1 = left of `=`, 0 = right of `=` |
| sort_order | INTEGER | ordering within a term's product |
| coeff_value | REAL | NULL = implied 1 |
| coeff_special | TEXT | `"pi"`, `"e"` |
| coeff_exponent | REAL | default 1 |
| variable_id | TEXT FK | NULL = pure-coefficient row |
| var_exponent | REAL | default 1 |
| label | TEXT | subscript, e.g. `"1"`, `"initial"`, `"total"` |

**F = ma:**

| term | is_primary | sort | variable_id | var_exp |
|------|------------|------|-------------|---------|
| 1 | 1 | 0 | force | 1 |
| 1 | 0 | 0 | mass | 1 |
| 1 | 0 | 1 | acceleration | 1 |

**v² = u² + 2as:**

| term | is_primary | sort | coeff_value | variable_id | var_exp | label |
|------|------------|------|-------------|-------------|---------|-------|
| 1 | 1 | 0 | | velocity | 2 | final |
| 2 | 0 | 0 | | velocity | 2 | initial |
| 3 | 0 | 0 | 2 | | | |
| 3 | 0 | 1 | | acceleration | 1 | |
| 3 | 0 | 2 | | length | 1 | |

**m₁u₁ + m₂u₂ = m₁v₁ + m₂v₂:**

| term | is_primary | sort | variable_id | var_exp | label |
|------|------------|------|-------------|---------|-------|
| 1 | 1 | 0 | mass | 1 | 1 |
| 1 | 1 | 1 | velocity | 1 | initial |
| 2 | 1 | 0 | mass | 1 | 2 |
| 2 | 1 | 1 | velocity | 1 | initial |
| 3 | 0 | 0 | mass | 1 | 1 |
| 3 | 0 | 1 | velocity | 1 | final |
| 4 | 0 | 0 | mass | 1 | 2 |
| 4 | 0 | 1 | velocity | 1 | final |

---

### `formula_conditions`

| Column | Type | i18n | Notes |
|--------|------|------|-------|
| id | INTEGER PK | | |
| formula_id | TEXT FK | | |
| condition_text | TEXT (JSON) | ✓ | `{"en":"Ideal gas"}` |
| default_on | BOOLEAN | | 0 = off by default |
| alternative_formula_id | TEXT FK | | shown when toggled off |
| sort_order | INTEGER | | |


| formula_id | condition_text (en) | default_on | alternative_formula_id |
|------------|---------------------|------------|----------------------|
| `ideal_gas_law` | Ideal gas assumption | 1 | `van_der_waals` |
| `boyles_law` | Constant temperature | 1 | `ideal_gas_law` |
| `boyles_law` | Constant amount of gas | 1 | `ideal_gas_law` |

---

### `variables`

| Column | Type | i18n | Notes |
|--------|------|------|-------|
| id | TEXT PK | | slug, e.g. `force` |
| name | TEXT (JSON) | ✓ | |
| science | TEXT (JSON) | ✓ | |
| branch | TEXT (JSON) | ✓ | |
| topic | TEXT (JSON) | ✓ | |
| difficulty | INTEGER | | 1–10 |
| description | TEXT (JSON) | ✓ | |
| links | TEXT (JSON) | ✓ | |
| si_unit | TEXT | | `newton` |
| base_dims | TEXT (JSON) | | `{"M":1,"L":1,"T":-2,"I":0,"Θ":0,"N":0,"J":0}` |
| formulas | TEXT (JSON) | | IDs where this variable appears |
| created_at | TEXT | | |
| updated_at | TEXT | | |


| id | name (en) | si_unit | base_dims |
|----|-----------|---------|-----------|
| force | Force | N | `{"M":1,"L":1,"T":-2}` |
| velocity | Velocity | m·s⁻¹ | `{"L":1,"T":-1}` |
| gas_constant | Gas constant | J·mol⁻¹·K⁻¹ | `{"M":1,"L":2,"T":-2,"N":-1,"Θ":-1}` |

---

### `variable_units`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | centimeter |
| variable_id | TEXT FK | length |
| unit | TEXT | display label: `cm`, `°C` |
| symbol | TEXT | LaTeX: `cm`, `\text{\textdegree C}` |
| factor_to_si | REAL | multiply by this to get SI |
| offset | REAL | additive (0 except °C) |
| is_default | BOOLEAN | 1 = default SI display |
| unit_system | TEXT | `"SI"`, `"CGS"`, `"Imperial"`, NULL |


| variable_id | unit | symbol | factor_to_si | offset | is_default | unit_system |
|-------------|------|--------|-------------|--------|------------|-------------|
| length | m | m | 1 | 0 | 1 | SI |
| length | cm | cm | 0.01 | 0 | 0 | CGS |
| temperature | °C | \text{\textdegree C} | 1 | 273.15 | 0 | generic |

---

### Rendering rule

```
terms_is_primary = filter(terms, is_primary=1)
terms_not_primary = filter(terms, is_primary=0)

render_side(terms):
  for each unique term value:
    items = sorted by sort_order
    rendered = join items (multiply)
  return join rendered terms with " + "

result = render_side(terms_is_primary) + " = " + render_side(terms_not_primary)
```

A term with `coeff_value=-1` and no variables renders as the minus sign. A term with `coeff_value=negative` renders the "+" between terms as "-".

---

