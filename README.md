# Physics Cheat Sheet — Database Specification

## Idea

This project stores physics formulas and their variables in a structured SQL database. Each formula is broken down into terms (summands), and each term is a product of coefficients and variables raised to exponents. A LaTeX compilation engine reads the structured data and renders display LaTeX.

There are 6 tables: `formulas`, `formula_items`, `formula_conditions`, `formula_relations`, `variables`, `variable_units`.

---

## 1. `formulas`

One row per equation.

| Column | Type | i18n | Notes |
|--------|------|------|-------|
| id | TEXT PK | | slug, e.g. `newton_second` |
| name | TEXT (JSON) | ✓ | `{"en":"Newton's Second Law"}` |
| science | TEXT (JSON) | ✓ | Physics (might expand) |
| branch | TEXT (JSON) | ✓ | Classical Mechanics |
| topic | TEXT (JSON) | ✓ | Kinematics |
| difficulty | INTEGER | | 1–10 |
| description | TEXT (JSON) | ✓ | |
| links | TEXT (JSON) | ✓ | `[{"label":{i18n},"url":"..."}]` |
| created_at | TEXT | | |
| updated_at | TEXT | | |

| id | name (en) | branch | topic | difficulty |
|----|-----------|--------|-------|------------|
| `newton_second` | Newton's Second Law | Classical Mechanics | Dynamics | 2 |
| `suvat_v2` | SUVAT v² = u² + 2as | Classical Mechanics | Kinematics | 3 |
| `ideal_gas_law` | Ideal Gas Law | Thermodynamics | Equations of State | 4 |

**Notes:**
- Related/alternative formulas are stored in `formula_relations`, not as JSON columns here.
- Condition-triggered alternatives are stored in `formula_conditions`, not here.

---

## 2. `formula_items`

Breaks a formula into summands (terms) and their factors (products). Every row represents one factor in the product that makes up one summand.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| formula_id | TEXT FK | `REFERENCES formulas(id)` |
| term | INTEGER | groups factors that **multiply** together (same term = multiply, different term = add/subtract) |
| is_primary | BOOLEAN | 1 = left side of `=`, 0 = right side of `=` |
| sort_order | INTEGER | order within a term's product (left to right) |
| coeff_value | REAL | NULL = implied 1 |
| coeff_special | TEXT | `"pi"`, `"e"` |
| coeff_exponent | REAL | default 1 |
| variable_id | TEXT FK | NULL = pure-coefficient row; `REFERENCES variables(id)` |
| var_exponent | REAL | default 1 |
| label | TEXT | subscript, e.g. `"1"`, `"initial"`, `"total"` |
| latex_prefix | TEXT | LaTeX wrapper before this factor, e.g. `\overline{`, `\hat{`, `\left\|` |
| latex_suffix | TEXT | LaTeX wrapper after this factor, e.g. `}`, `\right\|` |

### How `term` and `is_primary` work

```
                     ┌───── term 1 (is_primary=1) ─────┐
                     │  sort=0         sort=1           │
                     │ velocity²       label="final"    │
                     └──────────────────────────────────┘
                =     
 ┌─ term 2 (is_primary=0) ─┐   ┌─ term 3 (is_primary=0) ──────────┐
 │  sort=0                  │   │  sort=0       sort=1     sort=2  │
 │  velocity²  label="init" │   │  coeff=2     accel¹    length¹  │
 └──────────────────────────┘   └──────────────────────────────────┘
```

Different `term` = addition between them. Same `term` = multiplication.

The `is_primary` flag determines which side of `=` each term goes to. This works the same for conservation laws (multiple terms on both sides) and simple equations (one term on the left).

### Examples

**F = ma:**

| term | is_primary | sort_order | variable_id | var_exponent |
|------|------------|-----------|-------------|--------------|
| 1 | 1 | 0 | force | 1 |
| 1 | 0 | 0 | mass | 1 |
| 1 | 0 | 1 | acceleration | 1 |

**KE = ½mv²:**

| term | is_primary | sort_order | coeff_value | coeff_exponent | variable_id | var_exponent |
|------|------------|-----------|-------------|----------------|-------------|--------------|
| 1 | 1 | 0 | | | energy | 1 |
| 1 | 0 | 0 | 2 | -1 | | |
| 1 | 0 | 1 | | | mass | 1 |
| 1 | 0 | 2 | | | velocity | 2 |

**v² = u² + 2as:**

| term | is_primary | sort_order | coeff_value | variable_id | var_exponent | label |
|------|------------|-----------|-------------|-------------|--------------|-------|
| 1 | 1 | 0 | | velocity | 2 | final |
| 2 | 0 | 0 | | velocity | 2 | initial |
| 3 | 0 | 0 | 2 | | | |
| 3 | 0 | 1 | | acceleration | 1 | |
| 3 | 0 | 2 | | length | 1 | |

**ΔU = Q − W (work done by system):**

| term | is_primary | sort_order | coeff_value | coeff_exponent | variable_id | var_exponent |
|------|------------|-----------|-------------|----------------|-------------|--------------|
| 1 | 1 | 0 | | | internal_energy_change | 1 |
| 2 | 0 | 0 | | | heat | 1 |
| 3 | 0 | 0 | -1 | 1 | | |
| 3 | 0 | 1 | | | work | 1 |

**m₁u₁ + m₂u₂ = m₁v₁ + m₂v₂ (conservation of momentum):**

| term | is_primary | sort_order | variable_id | var_exponent | label |
|------|------------|-----------|-------------|--------------|-------|
| 1 | 1 | 0 | mass | 1 | 1 |
| 1 | 1 | 1 | velocity | 1 | initial |
| 2 | 1 | 0 | mass | 1 | 2 |
| 2 | 1 | 1 | velocity | 1 | initial |
| 3 | 0 | 0 | mass | 1 | 1 |
| 3 | 0 | 1 | velocity | 1 | final |
| 4 | 0 | 0 | mass | 1 | 2 |
| 4 | 0 | 1 | velocity | 1 | final |

**PV = nRT (Ideal Gas Law):**

| term | is_primary | sort_order | variable_id | var_exponent |
|------|------------|-----------|-------------|--------------|
| 1 | 1 | 0 | pressure | 1 |
| 1 | 1 | 1 | volume | 1 |
| 2 | 0 | 0 | amount | 1 |
| 2 | 0 | 1 | gas_constant | 1 |
| 2 | 0 | 2 | temperature | 1 |

**T² ∝ a³ (Kepler's Third Law) with coefficient 4π²:**

| term | is_primary | sort_order | coeff_value | coeff_special | coeff_exponent | variable_id | var_exponent |
|------|------------|-----------|-------------|--------------|----------------|-------------|--------------|
| 1 | 1 | 0 | | | | period | 2 |
| 2 | 0 | 0 | 4 | | 1 | | |
| 2 | 0 | 1 | | pi | 2 | | |
| 2 | 0 | 2 | | | | gravitational_constant | -1 |
| 2 | 0 | 3 | | | | mass | -1 |
| 2 | 0 | 4 | | | | length | 3 |

**1/R = 1/R₁ + 1/R₂ (parallel resistance):**

| term | is_primary | sort_order | variable_id | var_exponent | label |
|------|------------|-----------|-------------|--------------|-------|
| 1 | 1 | 0 | resistance | -1 | |
| 2 | 0 | 0 | resistance | -1 | 1 |
| 3 | 0 | 0 | resistance | -1 | 2 |

---

## 3. `formula_conditions`

Togglable assumptions for a formula. Each condition has a default state. When toggled off, the display swaps to an alternative formula.

| Column | Type | i18n | Notes |
|--------|------|------|-------|
| id | INTEGER PK | | |
| formula_id | TEXT FK | | `REFERENCES formulas(id)` |
| condition_text | TEXT (JSON) | ✓ | `{"en":"Ideal gas assumption"}` |
| default_on | BOOLEAN | | 1 = on by default (hidden from user unless explicitly shown) |
| alternative_formula_id | TEXT FK | | `REFERENCES formulas(id)` — shown when this condition is toggled OFF |
| sort_order | INTEGER | | |

**Bidirectional linking:** Query forward with `formula_conditions.formula_id` → `alternative_formula_id`. Query backward with `SELECT * FROM formula_conditions WHERE alternative_formula_id = ?` to find all formulas that lead to this one.

| formula_id | condition_text (en) | default_on | alternative_formula_id |
|------------|---------------------|------------|----------------------|
| `ideal_gas_law` | Ideal gas assumption | 1 | `van_der_waals` |
| `boyles_law` | Constant temperature | 1 | `ideal_gas_law` |
| `boyles_law` | Constant amount of gas | 1 | `ideal_gas_law` |

**Note:** By default, conditions are not displayed as a module in the UI. They are hidden unless the user expands them.

---

## 4. `formula_relations`

Junction table for typed relationships between formulas. Replaces JSON array columns `alternative_formulas`, `related_formulas`, and `conditioned_formulas`.

### Why junction tables instead of JSON arrays?

> JSON arrays in a column are like writing related formula IDs on a sticky note and sticking it to the formula. If you rename a formula, you must find and update every sticky note that mentions it — easy to miss one. A junction table is like a proper filing cabinet: each relationship is its own row with database-enforced links. Rename a formula, and the database automatically updates or refuses the change. You can also ask "what does this formula relate to?" AND "what relates to this formula?" with equal ease.

```sql
-- Forward: what is this formula related to?
SELECT related_id FROM formula_relations WHERE formula_id = 'newton_second';

-- Backward: what formulas relate to this one?
SELECT formula_id FROM formula_relations WHERE related_id = 'newton_second';
```

| Column | Type | Notes |
|--------|------|-------|
| formula_id | TEXT FK | source formula; `REFERENCES formulas(id)` |
| related_id | TEXT FK | target formula; `REFERENCES formulas(id)` |
| relation_type | TEXT | `alternative`, `derivation`, `special_case`, `prerequisite`, `generalization` |
| UNIQUE(formula_id, related_id) | | prevents duplicate entries |

| formula_id | related_id | relation_type |
|------------|-----------|---------------|
| `kinetic_energy` | `work_energy` | derivation |
| `ideal_gas_law` | `boyles_law` | special_case |
| `ideal_gas_law` | `van_der_waals` | generalization |

---

## 5. `variables`

One row per physical quantity. Used as a dictionary for all symbols that can appear in formulas.

| Column | Type | i18n | Notes |
|--------|------|------|-------|
| id | TEXT PK | | slug, e.g. `force` |
| name | TEXT (JSON) | ✓ | `{"en":"Force"}` |
| science | TEXT (JSON) | ✓ | |
| branch | TEXT (JSON) | ✓ | |
| topic | TEXT (JSON) | ✓ | |
| difficulty | INTEGER | | 1–10 |
| description | TEXT (JSON) | ✓ | |
| links | TEXT (JSON) | ✓ | |
| si_unit | TEXT | | `newton` |
| latex | TEXT | | LaTeX symbol: `\theta`, `\sin`, `\infty`, `\Delta`; NULL → auto-generate from id |
| base_dims | TEXT (JSON) | | `{"M":1,"L":1,"T":-2,"I":0,"Θ":0,"N":0,"J":0}` |
| created_at | TEXT | | |
| updated_at | TEXT | | |

**Base dimension keys:** M (mass), L (length), T (time), I (electric current), Θ (temperature), N (amount of substance), J (luminous intensity).

**`latex` column** handles all special LaTeX symbol rendering:

| Kind | variable_id | latex value | Renders as |
|------|-------------|-------------|------------|
| Greek letter | theta | `\theta` | θ |
| Capital Greek | delta | `\Delta` | Δ |
| Standard function | sin | `\sin` | sin |
| Constant | pi | `\pi` | π |
| Infinity | infty | `\infty` | ∞ |
| Arrow | to | `\to` | → |
| Relation | proportional | `\propto` | ∝ |
| Accent | hbar | `\hbar` | ℏ |
| Vector operator | nabla | `\nabla` | ∇ |
| Partial derivative | partial | `\partial` | ∂ |

When `latex` is NULL, the engine auto-generates a LaTeX variable name from the `id` (e.g., `velocity` → `v`, `mass` → `m`). Override it when the auto-generated name doesn't match physics conventions.

| id | name (en) | latex | si_unit | base_dims |
|----|-----------|-------|---------|-----------|
| force | Force | `F` | N | `{"M":1,"L":1,"T":-2}` |
| velocity | Velocity | `v` | m·s⁻¹ | `{"L":1,"T":-1}` |
| theta | Angle | `\theta` | rad | `{}` |
| gas_constant | Gas constant | `R` | J·mol⁻¹·K⁻¹ | `{"M":1,"L":2,"T":-2,"N":-1,"Θ":-1}` |
| infinity | Infinity | `\infty` | | `{}` |

---

## 6. `variable_units`

Alternative units for each variable with conversion factors to SI.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| variable_id | TEXT FK | `REFERENCES variables(id)` |
| unit | TEXT | display label: `cm`, `°C` |
| symbol | TEXT | LaTeX symbol: `cm`, `\text{\textdegree C}` |
| factor_to_si | REAL | multiply by this to get SI (1 for SI itself) |
| offset | REAL | additive conversion (0 except for temperature: °C→K = 273.15) |
| is_default | BOOLEAN | 1 = default display unit (the SI unit for this variable) |
| unit_system | TEXT | `"SI"`, `"CGS"`, `"Imperial"`, NULL (NULL = available in any system) |

**Default behavior:** Every variable uses SI units by default. The `is_default` flag marks which row in `variable_units` is the SI default for that variable. When a user globally switches to CGS (or overrides an individual variable), the app applies the matching `unit_system` tag for base variables, then auto-computes derived variable units from their `base_dims`.

| variable_id | unit | symbol | factor_to_si | offset | is_default | unit_system |
|-------------|------|--------|-------------|--------|------------|-------------|
| length | m | m | 1 | 0 | 1 | SI |
| length | cm | cm | 0.01 | 0 | 0 | CGS |
| temperature | K | K | 1 | 0 | 1 | SI |
| temperature | °C | \text{\textdegree C} | 1 | 273.15 | 0 | generic |
| mass | kg | kg | 1 | 0 | 1 | SI |
| mass | g | g | 0.001 | 0 | 0 | CGS |
| force | N | N | 1 | 0 | 1 | SI |
| force | dyn | dyn | 1e-5 | 0 | 0 | CGS |

**Auto-conversion of derived units:** When the user switches `length→cm` (factor 0.01) and `mass→g` (factor 0.001), the app looks up each variable's `base_dims` and computes the combined conversion factor:

| Variable | base_dims | Computed factor | Composed unit symbol |
|----------|-----------|----------------|---------------------|
| force (M¹·L¹·T⁻²) | M:1, L:1, T:-2 | 0.001¹ × 0.01¹ × 1⁻² = 10⁻⁵ | g·cm·s⁻² (= dyn) |
| energy (M¹·L²·T⁻²) | M:1, L:2, T:-2 | 0.001¹ × 0.01² × 1⁻² = 10⁻⁷ | g·cm²·s⁻² (= erg) |

The app can either match the result against `variable_units` (e.g., find `dyn` for force) or compose the unit label from the base symbols.

---

## Rendering

### Structural rendering rule

```
terms_is_primary = filter(formula_items, is_primary=1)
terms_not_primary = filter(formula_items, is_primary=0)

render_side(terms):
  for each unique term value (sorted ascending):
    items = filter(terms, same term) sorted by sort_order
    rendered = join items (multiplied together)
  return join rendered terms with " + "

result = render_side(terms_is_primary) + " = " + render_side(terms_not_primary)
```

**Sign convention:** A term with `coeff_value=-1` and no variable renders as the minus sign. When the first item in a term has `coeff_value` negative, the "+" between terms is rendered as "-".

### LaTeX compilation engine

The structural data from `formula_items` is fed to a LaTeX compilation engine that produces the final display LaTeX. The engine handles all typographic details:

| What | How | Source |
|------|-----|--------|
| Variable symbol | `\theta`, `\sin`, `v` | `variables.latex` (auto-generated from id if NULL) |
| Subscript label | `_{1}`, `_{\text{initial}}` | `label` column (numeric → bare subscript, text → `\text{}`) |
| Exponent | `^{2}`, `^{-1}` | `var_exponent`, `coeff_exponent` |
| Fraction | `\frac{1}{2}` | Negative `coeff_exponent` of a pure coefficient |
| Special constant | `\pi`, `e` | `coeff_special` |
| Accent/overline | `\overline{v}`, `\hat{F}` | `latex_prefix` / `latex_suffix` wrapping the factor |
| Delimiters | `\left| x \right|`, `\langle \psi \rangle` | `latex_prefix` / `latex_suffix` |
| Negation | `- W` | `coeff_value=-1` without coefficient display |
| Greek letters | `\Delta`, `\theta`, `\mu` | `variables.latex` |
| Standard functions | `\sin`, `\cos`, `\lim`, `\det` | `variables.latex` |
| Named operators | `\nabla`, `\partial`, `\Box` | `variables.latex` |
| Relation symbols | `\propto`, `\approx`, `\neq` | `variables.latex` |
| Arrows | `\to`, `\Rightarrow` | `variables.latex` |
| Infinity | `\infty` | `variables.latex` |

### What is OUT OF SCOPE for v1 (may be handled later)

- Variable-sized symbols with limits: `∑`, `∫`, `∏` with lower/upper bounds
- Matrices and determinants
- Cases/environments
- Arbitrary nested sub-expressions
- Multi-line equations

---

## Table relationships diagram

```
formulas ──1:N──→ formula_items
formulas ──1:N──→ formula_conditions
formulas ──1:N──→ formula_relations   (as source)
formulas ──1:N──→ formula_relations   (as target via related_id)
formula_items ──N:1──→ variables
formula_conditions ──N:1──→ formulas (via alternative_formula_id)
variable_units ──N:1──→ variables
```

---

## Constraints and integrity

- All foreign keys use `REFERENCES` for referential integrity.
- `formula_relations` has `UNIQUE(formula_id, related_id)` — no duplicate relationships.
- `formula_items` has `UNIQUE(formula_id, term, sort_order)` — no conflicting item orderings.
- `term` values on one formula need not be contiguous or start at 1. They just need to be consistent for grouping.
- The `conditioned_formulas`, `alternative_formulas`, and `related_formulas` JSON arrays have been removed from `formulas` — all relationships go through `formula_relations` and `formula_conditions`.
- The `formulas` JSON array has been removed from `variables` — formula membership is derived from `SELECT DISTINCT formula_id FROM formula_items WHERE variable_id = ?`.
