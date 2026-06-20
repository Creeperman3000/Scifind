# Physics Cheat Sheet — Database Specification

## Idea

This project stores physics formulas and their variables in a structured SQL database. Each formula is broken down into terms, and each term is a product of coefficients and variables raised to exponents. A LaTeX compilation engine reads the structured data and renders display LaTeX.

There are 6 tables: `formulas`, `formula_items`, `conditions`, `formula_relations`, `variables`, `units`.

---

## 1. `formulas`

One row per equation.

| Column      | Type        | i18n | Notes                                    |
| ----------- | ----------- | ---- | ---------------------------------------- |
| id          | TEXT PK     |      | `newton_second_law_of_motion`            |
| name        | TEXT (JSON) | ✓    | `{"en":"Newton's second law of motion"}` |
| science     | TEXT (JSON) | ✓    | Physics                                  |
| branch      | TEXT (JSON) | ✓    | Classical mechanics                      |
| topic       | TEXT (JSON) | ✓    | Kinematics                               |
| difficulty  | INTEGER     |      | 1–10                                     |
| description | TEXT (JSON) | ✓    |                                          |
| links       | TEXT (JSON) | ✓    | `[{"label":{i18n},"url":"..."}]`         |
| created     | TEXT        |      |                                          |
| modified    | TEXT        |      |                                          |


| id                            | name (en)                     | branch              | topic              | difficulty |
| ----------------------------- | ----------------------------- | ------------------- | ------------------ | ---------- |
| `newton_second_law_of_motion` | Newton's second law of motion | Classical mechanics | Dynamics           | 2          |
| `suvat_v2`                    | SUVAT                         | Classical mechanics | Kinematics         | 3          |
| `ideal_gas_law`               | Ideal gas law                 | Thermodynamics      | Equations of state | 4          |

**Notes:**
- Related/alternative formulas are stored in `formula_relations`, not as JSON columns here.
- Condition-triggered alternatives are stored in `conditions`, not here.

---

## 2. `formula_items`

Breaks a formula into terms and their factors (products).

| Column         | Type       | Notes                                                                                       |
| -------------- | ---------- | ------------------------------------------------------------------------------------------- |
| id             | INTEGER PK |                                                                                             |
| formula_id     | TEXT FK    | `REFERENCES formulas(id)`                                                                   |
| term           | INTEGER    | groups factors that multiply together (same term = multiply, different term = add/subtract) |
| is_primary     | BOOLEAN    | 1 = primary variable (left of =), 0 = variable on the other side                            |
| sort_order     | INTEGER    | order within a term's product (left to right)                                               |
| coeff_value    | REAL       | NULL = 1                                                                                    |
| coeff_special  | TEXT       | `"pi"`, `"e"`                                                                               |
| coeff_exponent | REAL       | default 1                                                                                   |
| variable_id    | TEXT FK    | NULL = pure-coefficient row; `REFERENCES variables(id)`                                     |
| var_exponent   | REAL       | default 1                                                                                   |
| label          | TEXT       | subscript, e.g. `"1"`                                                                       |
| latex_prefix   | TEXT       | LaTeX wrapper before, e.g. `\overline{`, `\hat{`, `\left\lvert`                             |
| latex_suffix   | TEXT       | LaTeX wrapper after, e.g. `}`, `\right\rvert`                                               |

### How `term` and `is_primary` work

All items are stored as they would appear on the right side of `=`. The `is_primary` flag marks items that move to the left side for display ⇒ when they cross `=`, their exponent sign flips.

- different `term` = addition between them
- same `term` = multiplication
- `is_primary=1` → moves left of `=` → exponent sign flips (we are dividing by it)
- `is_primary=0` → stays right of `=` → exponent unchanged
- After flipping, items in the same `term` that were split across sides are multiplied together in the rendered equation.

**Example — F = ma stored as RHS:**

| Stored | is_primary | Stored exp | Display side | Display exp |
| ------ | ---------- | ---------- | ------------ | ----------- |
| force  | 1          | -1         | LHS          | 1           |
| mass   | 0          | 1          | RHS          | 1           |
| accel  | 0          | 1          | RHS          | 1           |

 `1 = F⁻¹·m¹·a¹` → F = ma

### Examples

**F = ma:**

| term | is_primary | sort_order | variable_id  | var_exponent |
| ---- | ---------- | ---------- | ------------ | ------------ |
| 1    | 1          | 0          | force        | -1           |
| 1    | 0          | 0          | mass         | 1            |
| 1    | 0          | 1          | acceleration | 1            |


**Ek = ½mv²:**

| term | is_primary | sort_order | coeff_value | coeff_exponent | variable_id | var_exponent | label |
| ---- | ---------- | ---------- | ----------- | -------------- | ----------- | ------------ | ----- |
| 1    | 1          | 0          |             |                | energy      | -1           | k     |
| 1    | 0          | 0          | 2           | -1             |             |              |       |
| 1    | 0          | 1          |             |                | mass        | 1            |       |
| 1    | 0          | 2          |             |                | velocity    | 2            |       |


**v² = u² + 2as:**

| term | is_primary | sort_order | coeff_value | variable_id  | var_exponent | label   |
| ---- | ---------- | ---------- | ----------- | ------------ | ------------ | ------- |
| 1    | 1          | 0          |             | velocity     | -2           | final   |
| 2    | 0          | 0          |             | velocity     | 2            | initial |
| 3    | 0          | 0          | 2           |              |              |         |
| 3    | 0          | 1          |             | acceleration | 1            |         |
| 3    | 0          | 2          |             | length       | 1            |         |


**ΔU = Q − W (work done by system):**

| term | is_primary | sort_order | coeff_value | coeff_exponent | variable_id            | var_exponent |
| ---- | ---------- | ---------- | ----------- | -------------- | ---------------------- | ------------ |
| 1    | 1          | 0          |             |                | internal_energy_change | -1           |
| 2    | 0          | 0          |             |                | heat                   | 1            |
| 3    | 0          | 0          | -1          | 1              |                        |              |
| 3    | 0          | 1          |             |                | work                   | 1            |


**m₁u₁ + m₂u₂ = m₁v₁ + m₂v₂ (conservation of momentum):**

| term | is_primary | sort_order | variable_id | var_exponent | label   |
| ---- | ---------- | ---------- | ----------- | ------------ | ------- |
| 1    | 1          | 0          | mass        | -1           | 1       |
| 1    | 1          | 1          | velocity    | -1           | initial |
| 2    | 1          | 0          | mass        | -1           | 2       |
| 2    | 1          | 1          | velocity    | -1           | initial |
| 3    | 0          | 0          | mass        | 1            | 1       |
| 3    | 0          | 1          | velocity    | 1            | final   |
| 4    | 0          | 0          | mass        | 1            | 2       |
| 4    | 0          | 1          | velocity    | 1            | final   |


**PV = nRT (Ideal Gas Law):**

| term | is_primary | sort_order | variable_id  | var_exponent |
| ---- | ---------- | ---------- | ------------ | ------------ |
| 1    | 1          | 0          | pressure     | -1           |
| 1    | 1          | 1          | volume       | -1           |
| 2    | 0          | 0          | amount       | 1            |
| 2    | 0          | 1          | gas_constant | 1            |
| 2    | 0          | 2          | temperature  | 1            |


**T² ∝ a³ (Kepler's Third Law) with coefficient 4π²:**

| term | is_primary | sort_order | coeff_value | coeff_special | coeff_exponent | variable_id            | var_exponent |
| ---- | ---------- | ---------- | ----------- | ------------- | -------------- | ---------------------- | ------------ |
| 1    | 1          | 0          |             |               |                | period                 | -2           |
| 2    | 0          | 0          | 4           |               | 1              |                        |              |
| 2    | 0          | 1          |             | pi            | 2              |                        |              |
| 2    | 0          | 2          |             |               |                | gravitational_constant | -1           |
| 2    | 0          | 3          |             |               |                | mass                   | -1           |
| 2    | 0          | 4          |             |               |                | length                 | 3            |


**1/R = 1/R₁ + 1/R₂ (parallel resistance):**

| term | is_primary | sort_order | variable_id | var_exponent | label |
| ---- | ---------- | ---------- | ----------- | ------------ | ----- |
| 1    | 1          | 0          | resistance  | 1            |       |
| 2    | 0          | 0          | resistance  | -1           | 1     |
| 3    | 0          | 0          | resistance  | -1           | 2     |


---

## 3. `conditions`

Togglable assumptions for a formula. Each condition has a default state. When toggled, the display swaps to an alternative formula.

| Column                 | Type        | i18n | Notes                                                                |
| ---------------------- | ----------- | ---- | -------------------------------------------------------------------- |
| id                     | INTEGER PK  |      |                                                                      |
| formula_id             | TEXT FK     |      | `REFERENCES formulas(id)`                                            |
| condition_text         | TEXT (JSON) | ✓    | `{"en":"Ideal gas assumption"}`                                      |
| default_on             | BOOLEAN     |      | 1 = on by default (hidden from user unless explicitly shown)         |
| alternative_formula_id | TEXT FK     |      | `REFERENCES formulas(id)` — shown when this condition is toggled OFF |
| sort_order             | INTEGER     |      |                                                                      |
| created                | TEXT        |      |                                                                      |
| modified               | TEXT        |      |                                                                      |

**Bidirectional linking:** Query forward with `conditions.formula_id` → `alternative_formula_id`. Query backward with `SELECT * FROM conditions WHERE alternative_formula_id = ?` to find all formulas that lead to this one.

| formula_id      | condition_text (en)    | default_on | alternative_formula_id |
| --------------- | ---------------------- | ---------- | ---------------------- |
| `ideal_gas_law` | Ideal gas assumption   | 1          | `van_der_waals`        |
| `boyles_law`    | Constant temperature   | 1          | `ideal_gas_law`        |
| `boyles_law`    | Constant amount of gas | 1          | `ideal_gas_law`        |

**Note:** In the UI, the user has an option below the equation to change the equation by toggling these assumptions.

---

## 4. `formula_relations`

Junction table for typed relationships between formulas. Replaces JSON array columns `alternative_formulas`, `related_formulas`, and `conditioned_formulas`.

```sql
-- Forward: what is this formula related to?
SELECT related_id FROM formula_relations WHERE formula_id = 'newton_second';

-- Backward: what formulas relate to this one?
SELECT formula_id FROM formula_relations WHERE related_id = 'newton_second';
```

| Column                         | Type    | Notes                                                                         |
| ------------------------------ | ------- | ----------------------------------------------------------------------------- |
| formula_id                     | TEXT FK | source formula; `REFERENCES formulas(id)`                                     |
| related_id                     | TEXT FK | target formula; `REFERENCES formulas(id)`                                     |
| relation_type                  | TEXT    | `alternative`, `derivation`, `special_case`, `prerequisite`, `generalization` |
| UNIQUE(formula_id, related_id) |         | prevents duplicate entries                                                    |


| formula_id       | related_id      | relation_type  |
| ---------------- | --------------- | -------------- |
| `kinetic_energy` | `work_energy`   | derivation     |
| `ideal_gas_law`  | `boyles_law`    | special_case   |
| `ideal_gas_law`  | `van_der_waals` | generalization |

---

## 5. `variables`

One row per physical quantity. Used as a dictionary for all symbols that can appear in formulas.

| Column      | Type        | i18n | Notes                                          |
| ----------- | ----------- | ---- | ---------------------------------------------- |
| id          | TEXT PK     |      | `force`                                        |
| name        | TEXT (JSON) | ✓    | `{"en":"Force"}`                               |
| latex       | TEXT        |      | `F`                                            |
| science     | TEXT (JSON) | ✓    |                                                |
| branch      | TEXT (JSON) | ✓    |                                                |
| topic       | TEXT (JSON) | ✓    |                                                |
| difficulty  | INTEGER     |      | 1–10                                           |
| description | TEXT (JSON) | ✓    |                                                |
| links       | TEXT (JSON) | ✓    |                                                |
| si_unit     | TEXT        |      | `newton`                                       |
| base_dims   | TEXT (JSON) |      | `{"M":1,"L":1,"T":-2,"I":0,"Θ":0,"N":0,"J":0}` |
| created     | TEXT        |      |                                                |
| modified    | TEXT        |      |                                                |

**Base dimension keys:** M (mass), L (length), T (time), I (electric current), Θ (temperature), N (amount of substance), J (luminous intensity).

---

## 6. `units`

Alternative units for each variable with conversion factors to SI.

| Column       | Type    | Notes                                                                |
| ------------ | ------- | -------------------------------------------------------------------- |
| id           | TEXT PK | `millimeter`, `degree_celsius`                                       |
| variable_id  | TEXT FK | `REFERENCES variables(id)`                                           |
| symbol       | TEXT    | LaTeX symbol: `mm`, `\text{\textdegree C}`                           |
| factor_to_si | REAL    | multiply by this to get SI (1 for SI itself)                         |
| offset       | REAL    | additive conversion (0 except for temperature)                       |
| si_unit      | BOOLEAN | 1 = default display unit                                             |
| unit_system  | TEXT    | `"SI"`, `"CGS"`, `"Imperial"`, NULL (NULL = available in any system) |

**Default behavior:** Every variable uses SI units by default. The `si_unit` flag marks which row in `units` is the SI default for that variable. When a user globally switches to CGS (or overrides an individual variable), the app applies the matching `unit_system` tag for base variables, then auto-computes derived variable units from their `base_dims`.

| id             | variable_id | symbol               | factor_to_si | offset | si_unit | unit_system |
| -------------- | ----------- | -------------------- | ------------ | ------ | ------- | ----------- |
| meter          | length      | m                    | 1            | 0      | 1       | SI          |
| centimeter     | length      | cm                   | 0.01         | 0      | 0       | CGS         |
| kelvin         | temperature | K                    | 1            | 0      | 1       | SI          |
| degree_celsius | temperature | \text{\textdegree C} | 1            | 273.15 | 0       | generic     |
| kilogram       | mass        | kg                   | 1            | 0      | 1       | SI          |
| gram           | mass        | g                    | 0.001        | 0      | 0       | CGS         |
| newton         | force       | N                    | 1            | 0      | 1       | SI          |
| dyne           | force       | dyn                  | 1e-5         | 0      | 0       | CGS         |


---

### What is **out of scope** for v1 (may be handled later)

- Variable-sized symbols with limits: `∑`, `∫`, `∏` with lower/upper bounds
- Matrices and determinants
- Cases/environments
- Arbitrary nested sub-expressions
- Multi-line equations
