# Physics Cheat Sheet

## Idea

This project stores physics formulas and their variables in a structured SQL database. Each formula is broken down into terms, and each term is a product of coefficients and variables raised to exponents. A LaTeX compilation engine reads the structured data and renders display LaTeX.

There are 6 tables: `formulas`, `formula_items`, `conditions`, `formula_relations`, `variables`, `units`.

## CLI Tool

`formula.py` — command-line interface for the database.

| Command       | Description                                      |
| ------------- | ------------------------------------------------ |
| `init`        | Create and seed the database                     |
| `list`        | List formulas (filter by `--branch`, `--difficulty`) |
| `show <id>`   | Show formula details with rendered LaTeX         |
| `search <q>`  | Full-text search                                 |
| `variables`   | List all variables                               |
| `variable <id>` | Show variable details with dimensions and SI unit |
| `units`       | List units (filter by `--variable`)              |
| `browse`      | Browse branch/topic tree                         |
| `export`      | Export all tables in various formats             |
| `import <file>` | Import tables from file or directory          |

### Export/Import

The tool supports multiple formats for data portability:

| Format | Output                           | Input auto-detected |
| ------ | -------------------------------- | ------------------- |
| `csv`  | Per-table CSV files in a directory | CSV files (single file with `=== tablename ===` headers) or directory of per-table CSVs |
| `xlsx` | Single XLSX workbook, one sheet per table | `.xlsx` files |
| `ods`  | Single ODS spreadsheet, one sheet per table | `.ods` files |

**Usage examples:**
```
formula export --format csv -o ./backup          # per-table CSV files
formula export --format xlsx -o formulas.xlsx    # Excel workbook
formula export --format ods -o formulas.ods      # OpenDocument spreadsheet
formula import ./backup                          # directory of per-table CSVs
formula import formulas.xlsx                     # Excel workbook
formula import data.csv                          # single CSV with === headers
```

## Web Application

`webapp.py` — Flask app with browse, search, export/import, and locale support.

- Browse formulas by branch/topic tree
- View formula details with rendered KaTeX LaTeX
- View variable details with base dimensions and SI unit decomposition
- Full-text search
- **Locale toggle**: en-US / en-UK (via `Accept-Language`, `?lang=` query param, or session cookie)
- **Dimension mode toggle**: switch between variable symbols (M, L, T…) and unit symbols (kg, m, s…) in dimension display
- **Copy formula**: dropdown with LaTeX code, Unicode (via `unicodeit`), or clipboard image (via `html-to-image`)
- **Natural language exponents**: "squared", "cubed", "to the Nth" in unit decomposition
- **Download data** as ZIP of per-table CSVs, XLSX, or ODS (via navbar export button)
- **Import data** by uploading CSV, XLSX, or ODS files (via navbar file input, auto-submits)

## Database Specification

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
| formula_id     | TEXT FK    | `REFERENCES formulas(id)`                                                                   |
| term           | INTEGER    | groups factors that multiply together (same term = multiply, different term = add/subtract) |
| is_primary     | BOOLEAN    | 1 = primary variable (left of =), 0 = variable on the other side                            |
| sort_order     | INTEGER    | order within a term's side of the product (sorted per `(term, is_primary)` group)           |
| coeff_value    | REAL       | NULL = 1                                                                                    |
| coeff_special  | TEXT       | `"pi"`, `"e"`                                                                               |
| coeff_exponent | REAL       | default 1                                                                                   |
| variable_id    | TEXT FK    | NULL = pure-coefficient row; `REFERENCES variables(id)`                                     |
| var_exponent   | REAL       | default 1                                                                                   |
| label          | TEXT       | subscript, e.g. `"1"`                                                                       |
| latex_prefix   | TEXT       | LaTeX wrapper before, e.g. `\overline{`, `\hat{`, `\left\lvert`                             |
| latex_suffix   | TEXT       | LaTeX wrapper after, e.g. `}`, `\right\rvert`                                               |
| latex_override | TEXT       | overrides `variables.latex` for this item, e.g. `r` instead of `s`, `u` instead of `v`      |

**PK:** `(formula_id, term, is_primary, sort_order)`. Items on opposite sides of `=` (different `is_primary`) within the same `term` have independent sort orders starting from 0.

**Note:** `coeff_special`, `latex`, `latex_prefix`, `latex_suffix`, `latex_override` are simple strings. The rendering engine does not parse or interpret them.

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

Togglable assumptions for a formula. Each condition has a default state. When toggled, the display swaps the formula for a different one (e.g. `ΔU = Q − W` → `ΔU = −W`).

| Column                 | Type        | i18n | Notes                                  |
| ---------------------- | ----------- | ---- | -------------------------------------- |
| id                     | INTEGER PK  |      | `ideal_gas_assumption`                 |
| name                   | TEXT (JSON) | ✓    | `{"en":"Ideal gas assumption"}`        |
| formula_id             | TEXT FK     |      | `REFERENCES formulas(id)`              |
| replacement_formula_id | TEXT FK     |      | `REFERENCES formulas(id)`              |
| default_on             | BOOLEAN     |      | 1 = assumption is by default performed |
| sort_order             | INTEGER     |      |                                        |
| created                | TEXT        |      |                                        |
| modified               | TEXT        |      |                                        |

**Bidirectional linking:** Query forward with `conditions.formula_id` → `replacement_formula_id`. Query backward with `SELECT * FROM conditions WHERE replacement_formula_id = ?` to find all formulas that lead to this one.

| id                | name (en)              | formula_id      | replacement_formula_id | default_on |
| ----------------- | ---------------------- | --------------- | ---------------------- | ---------- |
| `ideal_gas_swap`  | Ideal gas assumption   | `ideal_gas_law` | `van_der_waals`        | 1          |
| `boyles_isotherm` | Constant temperature   | `boyles_law`    | `ideal_gas_law`        | 1          |
| `boyles_fixed_n`  | Constant amount of gas | `boyles_law`    | `ideal_gas_law`        | 1          |

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

| Column      | Type    | i18n | Notes                                          |
| ----------- | ------- | ---- | ---------------------------------------------- |
| id          | TEXT PK |      | `force`                                        |
| name        | TEXT (JSON) | ✓ | `{"en":"Force"}`                               |
| latex       | TEXT    |      | `F`                                            |
| science     | TEXT (JSON) | ✓ |                                                |
| branch      | TEXT (JSON) | ✓ |                                                |
| topic       | TEXT (JSON) | ✓ |                                                |
| difficulty  | INTEGER |      | 1–10                                           |
| description | TEXT (JSON) | ✓ |                                                |
| links       | TEXT (JSON) | ✓ |                                                |
| si_unit     | TEXT (JSON) |      | `[{"unit":"meter","exponent":3}]`               |
| dim_M       | INTEGER |      | Mass exponent                                  |
| dim_L       | INTEGER |      | Length exponent                                |
| dim_T       | INTEGER |      | Time exponent                                  |
| dim_I       | INTEGER |      | Electric current exponent                      |
| dim_Θ       | INTEGER |      | Temperature exponent                           |
| dim_N       | INTEGER |      | Amount of substance exponent                   |
| dim_J       | INTEGER |      | Luminous intensity exponent                    |
| created     | TEXT    |      |                                                |
| modified    | TEXT    |      |                                                |

**`si_unit` JSON format:** array of `{"unit": "<unit_id>", "exponent": <number>}` objects. The `unit` references `units.id`.

**Base dimension columns:** M (mass), L (length), T (time), I (electric current), Θ (temperature), N (amount of substance), J (luminous intensity). Each is an integer exponent (default 0).

---

## 6. `units`

Alternative units for each variable with conversion factors to SI.

| Column       | Type       | i18n | Notes                                                                |
| ------------ | ---------- | ---- | -------------------------------------------------------------------- |
| id           | TEXT PK    |      | `millimeter`, `degree_celsius`                                       |
| variable_id  | TEXT FK    |      | `REFERENCES variables(id)`                                           |
| symbol       | TEXT       |      | LaTeX/siunitx symbol: `\meter`, `\ohm`, `\degreeCelsius`             |
| name         | TEXT (JSON)| ✓    | `{"en":"Ohm"}`                                                       |
| factor_to_si | REAL       |      | multiply by this to get SI (1 for SI itself)                         |
| offset       | REAL       |      | additive conversion (0 except for temperature)                       |
| si_unit      | BOOLEAN    |      | 1 = default display unit                                             |
| unit_system  | TEXT       |      | `"SI"`, `"CGS"`, `"Imperial"`, NULL (NULL = available in any system) |

**Note:** Symbols support both siunitx commands (e.g. `\meter`, `\ohm`, `\newton`) and plain LaTeX (e.g. `\mathrm{m}`, `\mathrm{kg}`). The webapp converts them to `\mathrm{...}` LaTeX for KaTeX rendering via a lookup table.

**Default behavior:** Every variable uses SI units by default. The `si_unit` flag marks which row in `units` is the SI default for that variable. When a user globally switches to CGS (or overrides an individual variable), the app applies the matching `unit_system` tag for base variables, then auto-computes derived variable units from their `base_dims`.

| id             | variable_id | symbol           | name                | factor_to_si | offset | si_unit | unit_system |
| -------------- | ----------- | ---------------- | ------------------- | ------------ | ------ | ------- | ----------- |
| meter          | length      | `\meter`         | Meter               | 1            | 0      | 1       | SI          |
| centimeter     | length      | `cm`             | Centimeter          | 0.01         | 0      | 0       | CGS         |
| kelvin         | temperature | `K`              | Kelvin              | 1            | 0      | 1       | SI          |
| degree_celsius | temperature | `\degreeCelsius` | Degree Celsius      | 1            | 273.15 | 0       | generic     |
| kilogram       | mass        | `kg`             | Kilogram            | 1            | 0      | 1       | SI          |
| gram           | mass        | `g`              | Gram                | 0.001        | 0      | 0       | CGS         |
| newton         | force       | `\newton`        | Newton              | 1            | 0      | 1       | SI          |
| dyne           | force       | `dyn`            | Dyne                | 1e-5         | 0      | 0       | CGS         |


---

### What is **out of scope** for v1 (may be handled later)

- Variable-sized symbols with limits: `∑`, `∫`, `∏` with lower/upper bounds
- Matrices and determinants
- Cases/environments
- Arbitrary nested sub-expressions
- Multi-line equations
