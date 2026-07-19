PRAGMA journal_mode = WAL;

-- ============================================================
-- 1. formula
-- ============================================================
CREATE TABLE IF NOT EXISTS formula (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,       -- JSON i18n: {"en-us":"...","en-uk":"..."}
    topic       TEXT,                -- ID into tree.json
    difficulty  INTEGER CHECK (difficulty BETWEEN 1 AND 10),
    description TEXT,                -- JSON i18n
    links       TEXT,                -- JSON array: [{"label":{i18n},"url":"..."}]
    created     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    modified    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================
-- 2. operator
-- ============================================================
-- Operators are reusable building blocks. Each has an arity, precedence,
-- and associativity. symbol is the LaTeX display form (e.g. \cdot, \sin, =).
-- math is a Python expression template (e.g. "a+b", "math.sin(a)", NULL if
-- the operator is not numerically computable, e.g. =, \propto).
--
-- operator_type:
--   infix       binary or n-ary: a OP b OP c         (+, -, *, /, =)
--   prefix      function-style:  OP a                 (\sin, \cos, \sqrt, \Delta)
--   postfix                       a OP                (n!)
--   relational  forms an equation: a = b, a ∝ b       (=, \approx, \propto, <, >)
CREATE TABLE IF NOT EXISTS operator (
    id            TEXT PRIMARY KEY,
    symbol        TEXT,               -- LaTeX display; NULL means invisible
    math          TEXT,               -- Python expression using operand names; NULL if not computable
    arity         INTEGER NOT NULL CHECK (arity > 0),
    precedence    INTEGER NOT NULL,
    associativity TEXT NOT NULL CHECK (associativity IN ('left', 'right', 'none')),
    operator_type TEXT NOT NULL CHECK (operator_type IN ('infix', 'prefix', 'postfix', 'relational'))
);

-- ============================================================
-- 3. constant
-- ============================================================
-- Dimensionless or constant-valued symbols like pi, e, Euler's gamma.
-- default_unit follows the same JSON array shape as quantity.default_unit
-- (used for dimensional constants like gravitational_constant, gas_constant
-- which are physical constants rather than pure numbers).
CREATE TABLE IF NOT EXISTS constant (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,      -- JSON i18n: {"en-us": "Pi"}
    symbol       TEXT NOT NULL,      -- LaTeX display: \pi
    value        REAL,               -- numerical value; NULL for symbolic constants
    default_unit TEXT                -- JSON array: [{"unit":"<id>","exponent":<n>},...]
);

-- ============================================================
-- 4. formula_token
-- ============================================================
-- An RPN-encoded formula. Tokens are read in `position` order, evaluated
-- onto a stack: operands push, operators pop their arity-many operands and
-- push a result. After the last token, the stack should hold a single node
-- which is the expression tree root.
--
-- token_kind:
--   quantity    operand; quantity_id is set
--   constant    operand; constant_id is set
--   number      operand; value is set
--   operator    arity-many operands are popped, the operator is applied
--
-- label is a JSON i18n array used for composite subscripts (e.g. ["1","2"]
-- -> v_{12}). symbol_overwrite and quantity_name_overwrite override the
-- referenced quantity's defaults for display only.
CREATE TABLE IF NOT EXISTS formula_token (
    formula_id               TEXT NOT NULL REFERENCES formula(id) ON DELETE CASCADE,
    position                 INTEGER NOT NULL,
    token_kind               TEXT NOT NULL CHECK (token_kind IN ('quantity', 'constant', 'number', 'operator')),
    quantity_id              TEXT REFERENCES quantity(id),
    constant_id              TEXT REFERENCES constant(id),
    operator_id              TEXT REFERENCES operator(id),
    value                    REAL,
    label                    TEXT,        -- JSON i18n array
    symbol_overwrite         TEXT,        -- JSON i18n, applies to quantity/constant tokens
    quantity_name_overwrite  TEXT,        -- JSON i18n, applies to quantity tokens

    PRIMARY KEY (formula_id, position),

    CHECK (
        (token_kind = 'quantity' AND quantity_id IS NOT NULL
            AND constant_id IS NULL AND operator_id IS NULL AND value IS NULL)
        OR (token_kind = 'constant' AND constant_id IS NOT NULL
            AND quantity_id IS NULL AND operator_id IS NULL AND value IS NULL)
        OR (token_kind = 'number' AND value IS NOT NULL
            AND quantity_id IS NULL AND constant_id IS NULL AND operator_id IS NULL)
        OR (token_kind = 'operator' AND operator_id IS NOT NULL
            AND quantity_id IS NULL AND constant_id IS NULL AND value IS NULL)
    )
);

-- ============================================================
-- 5. formula_relation (includes conditions)
-- ============================================================
CREATE TABLE IF NOT EXISTS formula_relation (
    formula_id    TEXT NOT NULL REFERENCES formula(id),
    related_id    TEXT NOT NULL REFERENCES formula(id),
    relation_type TEXT NOT NULL CHECK (relation_type IN (
        'alternative', 'derivation', 'special_case',
        'generalization', 'condition', 'assumption'
    )),
    description   TEXT,                -- JSON i18n

    UNIQUE (formula_id, related_id)
);

-- ============================================================
-- 6. quantity
-- ============================================================
CREATE TABLE IF NOT EXISTS quantity (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,       -- JSON i18n
    symbol      TEXT NOT NULL,
    symbol_overwrite TEXT,           -- JSON i18n override of quantity symbol
    topic       TEXT,                -- ID into tree.json
    difficulty  INTEGER CHECK (difficulty BETWEEN 1 AND 10),
    description TEXT,                -- JSON i18n
    links       TEXT,                -- JSON array
    default_unit TEXT,               -- JSON array: [{"unit":"<id>","exponent":<n>},...]
    dim_M       REAL NOT NULL DEFAULT 0,
    dim_L       REAL NOT NULL DEFAULT 0,
    dim_T       REAL NOT NULL DEFAULT 0,
    dim_I       REAL NOT NULL DEFAULT 0,
    dim_Θ       REAL NOT NULL DEFAULT 0,
    dim_N       REAL NOT NULL DEFAULT 0,
    dim_J       REAL NOT NULL DEFAULT 0,
    created     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    modified    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================
-- 7. unit
-- ============================================================
CREATE TABLE IF NOT EXISTS unit (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,        -- JSON i18n: {"en-us":"Meter","en-uk":"Metre"}
    symbol       TEXT NOT NULL,
    quantity_id  TEXT NOT NULL REFERENCES quantity(id),
    default_unit INTEGER NOT NULL DEFAULT 0 CHECK (default_unit IN (0,1)),
    unit_system  TEXT CHECK (unit_system IN ('SI','CGS','Imperial') OR unit_system IS NULL),
    factor       REAL NOT NULL DEFAULT 1,
    latex_factor TEXT,               -- LaTeX display for factor (e.g. "\frac{180}{\pi}")
    offset       REAL NOT NULL DEFAULT 0
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_formula_token_formula  ON formula_token(formula_id);
CREATE INDEX IF NOT EXISTS idx_formula_token_quantity ON formula_token(quantity_id);
CREATE INDEX IF NOT EXISTS idx_formula_token_constant ON formula_token(constant_id);
CREATE INDEX IF NOT EXISTS idx_formula_token_operator ON formula_token(operator_id);
CREATE INDEX IF NOT EXISTS idx_formula_relation_formula ON formula_relation(formula_id);
CREATE INDEX IF NOT EXISTS idx_formula_relation_related ON formula_relation(related_id);
CREATE INDEX IF NOT EXISTS idx_formula_relation_type    ON formula_relation(relation_type);
CREATE INDEX IF NOT EXISTS idx_unit_quantity            ON unit(quantity_id);
