PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS topic (
    id            TEXT PRIMARY KEY,
    parent_id     TEXT REFERENCES topic(id),
    name          TEXT NOT NULL,       -- JSON i18n: {"en-us":"...","cs-cz":"..."}
    name_genative TEXT,                -- JSON i18n: {"cs-cz":"..."}
    position      INTEGER NOT NULL DEFAULT 0,  -- depth-first order over the tree
    CHECK (json_valid(name)),
    CHECK (name_genative IS NULL OR json_valid(name_genative))
);

CREATE TABLE IF NOT EXISTS formula (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,       -- JSON i18n: {"en-us":"...","en-uk":"..."}
    topic_id    TEXT REFERENCES topic(id),
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
    topic_id         TEXT REFERENCES topic(id),
    difficulty       INTEGER CHECK (difficulty BETWEEN 1 AND 10),
    hidden           BOOLEAN NOT NULL DEFAULT 0 CHECK (hidden IN (0,1)),
    description      TEXT,                -- JSON i18n
    links            TEXT,                -- JSON array of URL strings: ["https://...", ...]
    per_overwrite    TEXT,                -- JSON i18n denominator preposition, e.g. time {"cs-cz":"za"}
    dim_symbol       TEXT,                -- base-dimension symbol (e.g. 'M'); NULL = derived quantity
    dim_position     INTEGER,             -- order among base dimensions; column is 'dim_' || dim_symbol
    dim_M            REAL NOT NULL DEFAULT 0,
    dim_L            REAL NOT NULL DEFAULT 0,
    dim_T            REAL NOT NULL DEFAULT 0,
    dim_I            REAL NOT NULL DEFAULT 0,
    dim_Θ            REAL NOT NULL DEFAULT 0,
    dim_N            REAL NOT NULL DEFAULT 0,
    dim_J            REAL NOT NULL DEFAULT 0,
    CHECK (json_valid(name)),
    CHECK (symbol_overwrite IS NULL OR json_valid(symbol_overwrite)),
    CHECK (per_overwrite IS NULL OR json_valid(per_overwrite)),
    CHECK (description IS NULL OR json_valid(description)),
    CHECK (links IS NULL OR json_valid(links))
);

CREATE TABLE IF NOT EXISTS unit (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,        -- JSON i18n: {"en-us":"Meter","en-uk":"Metre"}
    name_accusative TEXT,              -- JSON i18n declined name, e.g. second {"cs-cz":"sekundu"}
    symbol       TEXT NOT NULL,
    quantity_id  TEXT NOT NULL REFERENCES quantity(id),
    system       TEXT CHECK (system IN ('SI','CGS','Imperial') OR system IS NULL),
    is_base      INTEGER NOT NULL DEFAULT 0 CHECK (is_base IN (0,1)),
    -- Reference graph (NULL = root) into unit or compound_unit rows (no FK:
    -- SQLite can't model a union; `validate_graph` in conversion.py checks it).
    reference_unit_id    TEXT,
    factor_numerator     REAL,              -- NULL means 1
    factor_denominator   REAL,              -- NULL means 1
    constant_id          TEXT REFERENCES constant(id),
    -- x_ref = F * C^constant_power * (x_row + offset) + constant_shift * C
    -- (F = factor ratio, NULL = 1; C = constant value).
    constant_power       REAL NOT NULL DEFAULT 1,
    constant_shift       REAL NOT NULL DEFAULT 0,
    offset               REAL NOT NULL DEFAULT 0,
    CHECK (json_valid(name)),
    CHECK (name_accusative IS NULL OR json_valid(name_accusative)),
    CHECK (factor_numerator IS NULL OR factor_numerator != 0),
    CHECK (factor_denominator IS NULL OR factor_denominator != 0)
);

CREATE TABLE IF NOT EXISTS compound_unit (
    quantity_id      TEXT NOT NULL REFERENCES quantity(id),
    name_overwrite   TEXT,
    symbol_overwrite TEXT,
    unit             TEXT NOT NULL,      -- JSON array [{"unit":"<id>","exponent":<n>},...]
    system           TEXT CHECK (system IN ('SI','CGS','Imperial') OR system IS NULL),
    is_base          INTEGER NOT NULL DEFAULT 0 CHECK (is_base IN (0,1)),
    -- No stored id: the id is derived on the fly via compound_unit_slug()
    -- (pure function of quantity_id + parts, locale-free), so recomputing
    -- can never drift from the parts. Friendly names like hectare/are/litre
    -- live in name_overwrite/symbol_overwrite, not in the id.
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
    quantity_id  TEXT REFERENCES quantity(id),       -- quantity whose base unit applies; NULL = no quantity link
    unit         TEXT,               -- JSON array like compound_unit.unit, explicit unit when it differs from the quantity base; NULL = use quantity's base unit (or no units when quantity_id is also NULL)
    CHECK (json_valid(name)),
    CHECK (description IS NULL OR json_valid(description)),
    CHECK (links IS NULL OR json_valid(links)),
    CHECK (unit IS NULL OR json_valid(unit))
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
    -- Fully data-driven: adding an operator is an INSERT, never a code change.
    id             TEXT PRIMARY KEY,
    symbol         TEXT,               -- LaTeX display; NULL means juxtaposition
    aliases        TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(aliases)),
                                      -- JSON array of surface match strings: id spelling and/or LaTeX symbol
    arity          INTEGER NOT NULL CHECK (arity > 0),
    precedence     INTEGER NOT NULL,   -- binding strength; higher binds tighter
    associativity  TEXT NOT NULL CHECK (associativity IN ('left', 'right', 'none')),
    type           TEXT NOT NULL CHECK (type IN ('infix', 'prefix', 'postfix', 'relational')),
                                      -- 'relational' = non-associative comparison;
                                      -- `a op b op c` folds into one n-ary node
    latex_template TEXT NOT NULL,      -- `[[i]]` slots, `[[i!]]` grouped, `[[i?..]]` conditionals
                                       -- (full syntax: see operators.py `render_template`)
    dim_spec       TEXT NOT NULL DEFAULT ''
                                       -- `;`-separated clauses with one `result` clause
                                       -- (full syntax: see operators.py `parse_dim_spec`)
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
-- Composite/covering indexes for list, filter, and detail queries (no per-row scans).
CREATE INDEX IF NOT EXISTS idx_formula_token_qty_kind_fid ON formula_token(quantity_id, token_kind, formula_id);
CREATE INDEX IF NOT EXISTS idx_formula_token_kind_const ON formula_token(token_kind, constant_id);
CREATE INDEX IF NOT EXISTS idx_formula_token_fid_pos ON formula_token(formula_id, position);
CREATE INDEX IF NOT EXISTS idx_unit_qty_sys_base ON unit(quantity_id, system, is_base);
CREATE INDEX IF NOT EXISTS idx_unit_sys_base ON unit(system, is_base);
CREATE INDEX IF NOT EXISTS idx_quantity_topic_diff ON quantity(topic_id, difficulty);
CREATE INDEX IF NOT EXISTS idx_formula_topic_diff ON formula(topic_id, difficulty);
CREATE INDEX IF NOT EXISTS idx_quantity_hidden ON quantity(hidden);
CREATE INDEX IF NOT EXISTS idx_constant_quantity ON constant(quantity_id);
CREATE INDEX IF NOT EXISTS idx_quantity_dim_symbol ON quantity(dim_symbol);
