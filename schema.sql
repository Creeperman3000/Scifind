PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS formula (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,       -- JSON i18n: {"en-us":"...","en-uk":"..."}
    topic       TEXT,                -- ID into tree.json
    difficulty  INTEGER CHECK (difficulty BETWEEN 1 AND 10),
    description TEXT,                -- JSON i18n
    links       TEXT,                -- JSON array of URL strings: ["https://...", ...]
    CHECK (json_valid(name)),
    CHECK (description IS NULL OR json_valid(description)),
    CHECK (links IS NULL OR json_valid(links))
);

CREATE TABLE IF NOT EXISTS formula_relation (
    formula_id    TEXT NOT NULL REFERENCES formula(id),
    related_id    TEXT NOT NULL REFERENCES formula(id),
    relation_type TEXT NOT NULL CHECK (relation_type IN (
        'alternative', 'derivation', 'special_case',
        'generalization', 'condition', 'assumption'
    )),
    description   TEXT,                -- JSON i18n

    UNIQUE (formula_id, related_id),

    CHECK (description IS NULL OR json_valid(description))
);

CREATE TABLE IF NOT EXISTS quantity (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,       -- JSON i18n
    symbol           TEXT NOT NULL,
    symbol_overwrite TEXT,                -- JSON i18n override of quantity symbol
    topic            TEXT,                -- ID into tree.json
    difficulty       INTEGER CHECK (difficulty BETWEEN 1 AND 10),
    hidden           BOOLEAN NOT NULL DEFAULT 0 CHECK (hidden IN (0,1)),
    description      TEXT,                -- JSON i18n
    links            TEXT,                -- JSON array of URL strings: ["https://...", ...]
    dim_M            REAL NOT NULL DEFAULT 0,
    dim_L            REAL NOT NULL DEFAULT 0,
    dim_T            REAL NOT NULL DEFAULT 0,
    dim_I            REAL NOT NULL DEFAULT 0,
    dim_Θ            REAL NOT NULL DEFAULT 0,
    dim_N            REAL NOT NULL DEFAULT 0,
    dim_J            REAL NOT NULL DEFAULT 0,
    CHECK (json_valid(name)),
    CHECK (symbol_overwrite IS NULL OR json_valid(symbol_overwrite)),
    CHECK (description IS NULL OR json_valid(description)),
    CHECK (links IS NULL OR json_valid(links))
);

CREATE TABLE IF NOT EXISTS unit (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,        -- JSON i18n: {"en-us":"Meter","en-uk":"Metre"}
    symbol       TEXT NOT NULL,
    quantity_id  TEXT NOT NULL REFERENCES quantity(id),
    system       TEXT CHECK (system IN ('SI','CGS','Imperial') OR system IS NULL),
    is_base      INTEGER NOT NULL DEFAULT 0 CHECK (is_base IN (0,1)),
    -- Reference graph (NULL = root). Points to unit rows or compound_unit rows
    -- (no FK declared: SQLite can't model a union; the wiki documents the
    -- cross-table semantics and `validate_graph` in conversion.py checks it
    -- at runtime).
    reference_unit_id    TEXT,
    factor               REAL NOT NULL DEFAULT 1,
    is_factor_reciprocal INTEGER NOT NULL DEFAULT 0 CHECK (is_factor_reciprocal IN (0,1)),
    constant_id          TEXT REFERENCES constant(id),
    constant_operator_id TEXT NOT NULL DEFAULT 'mul' CHECK (constant_operator_id IN ('mul', 'div', 'add', 'sub')),
    offset               REAL NOT NULL DEFAULT 0,
    CHECK (json_valid(name))
);

CREATE TABLE IF NOT EXISTS compound_unit (
    quantity_id      TEXT NOT NULL REFERENCES quantity(id),
    name_overwrite   TEXT,
    symbol_overwrite TEXT,
    unit             TEXT NOT NULL,      -- JSON array [{"unit":"<id>","exponent":<n>},...]
    system           TEXT CHECK (system IN ('SI','CGS','Imperial') OR system IS NULL),
    is_base          INTEGER NOT NULL DEFAULT 0 CHECK (is_base IN (0,1)),
    -- No stored id: the row's slug is computed on the fly via
    -- scifind_lib.units.compound_unit_slug(quantity_id, unit).
    -- Value derives from the `unit` parts (see compound_parts_value).
    PRIMARY KEY (quantity_id, unit),
    CHECK (json_valid(unit))
);

CREATE TABLE IF NOT EXISTS constant (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,      -- JSON i18n: {"en-us": "Pi"}
    symbol       TEXT NOT NULL,      -- LaTeX display: \pi
    difficulty   INTEGER CHECK (difficulty BETWEEN 1 AND 10),
    description  TEXT,               -- JSON i18n
    links        TEXT,               -- JSON array of URL strings: ["https://...", ...]
    value        REAL,               -- numerical value; NULL for symbolic constants
    quantity_id  TEXT REFERENCES quantity(id),       -- quantity whose name applies
    unit_id      TEXT REFERENCES unit(id),           -- constant's preferred unit (a named unit row), or NULL
    compound_unit_id TEXT, -- slug into compound_unit, computed via compound_unit_slug (no FK: id is not stored; resolved at runtime), or NULL
    CHECK (json_valid(name)),
    CHECK (description IS NULL OR json_valid(description)),
    CHECK (links IS NULL OR json_valid(links))
);

CREATE TABLE IF NOT EXISTS si_prefix (
    id       TEXT PRIMARY KEY,           -- exponent as a string: "3" for kilo, "-3" for milli
    name     TEXT NOT NULL,              -- JSON i18n: {"en-us":"Kilo","cs-cz":"Kilo"}
    symbol   TEXT NOT NULL,              -- JSON i18n: {"en-us":"k","cs-cz":"k"}; LaTeX-safe raw symbols
    CHECK (json_valid(name)),
    CHECK (json_valid(symbol))
);

CREATE TABLE IF NOT EXISTS formula_token (
    formula_id               TEXT NOT NULL REFERENCES formula(id) ON DELETE CASCADE,
    position                 INTEGER NOT NULL,
    token_kind               TEXT NOT NULL CHECK (token_kind IN ('quantity', 'constant', 'number', 'operator')),
    quantity_id              TEXT REFERENCES quantity(id),
    constant_id              TEXT REFERENCES constant(id),
    operator_id              TEXT REFERENCES operator(id),
    value                    REAL,
    symbol_overwrite         TEXT,        -- JSON i18n, applies to quantity/constant tokens
    name_overwrite           TEXT,        -- JSON i18n, applies to quantity tokens

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
    ),
    CHECK (symbol_overwrite IS NULL OR json_valid(symbol_overwrite)),
    CHECK (name_overwrite IS NULL OR json_valid(name_overwrite))
);

CREATE TABLE IF NOT EXISTS operator (
    id            TEXT PRIMARY KEY,
    symbol        TEXT,               -- LaTeX display; NULL means invisible
    arity         INTEGER NOT NULL CHECK (arity > 0),
    precedence    INTEGER NOT NULL,
    associativity TEXT NOT NULL CHECK (associativity IN ('left', 'right', 'none')),
    operator_type TEXT NOT NULL CHECK (operator_type IN ('infix', 'prefix', 'postfix', 'relational')),
    paren_arg     TEXT NOT NULL DEFAULT '[1]' CHECK (paren_arg LIKE '[%' AND json_valid(paren_arg))
);

CREATE INDEX IF NOT EXISTS idx_formula_token_formula  ON formula_token(formula_id);
CREATE INDEX IF NOT EXISTS idx_formula_token_quantity ON formula_token(quantity_id);
CREATE INDEX IF NOT EXISTS idx_formula_token_constant ON formula_token(constant_id);
CREATE INDEX IF NOT EXISTS idx_formula_token_operator ON formula_token(operator_id);
CREATE INDEX IF NOT EXISTS idx_formula_relation_formula ON formula_relation(formula_id);
CREATE INDEX IF NOT EXISTS idx_formula_relation_related ON formula_relation(related_id);
CREATE INDEX IF NOT EXISTS idx_formula_relation_type    ON formula_relation(relation_type);
CREATE INDEX IF NOT EXISTS idx_unit_quantity            ON unit(quantity_id);
CREATE INDEX IF NOT EXISTS idx_compound_unit_quantity   ON compound_unit(quantity_id);
