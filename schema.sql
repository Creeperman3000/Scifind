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
    -- No stored id: the slug is computed via compound_unit_slug(); value derives from `unit` parts.
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

-- Slug overrides for single-part compound slugs with irregular names
-- (hectare/are/litre family): (unit_id, prefix, exponent) -> slug base.
CREATE TABLE IF NOT EXISTS slug_override (
    unit_id  TEXT NOT NULL,
    prefix   INTEGER,
    exponent INTEGER NOT NULL,
    slug     TEXT NOT NULL,
    PRIMARY KEY (unit_id, prefix, exponent)
);

-- Relational operators backing the dimension search filter (?M_eq=1, ...).
CREATE TABLE IF NOT EXISTS dimension_filter_operator (
    operator_id TEXT PRIMARY KEY REFERENCES operator(id),
    position    INTEGER NOT NULL
);

-- Small UI policy values (e.g. key 'si_visible_exponents' -> JSON array).
CREATE TABLE IF NOT EXISTS app_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
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
-- Full-text search over entity names/symbols/ids (FTS5, maintained by triggers).
CREATE VIRTUAL TABLE IF NOT EXISTS entity_fts USING fts5(
    kind, id UNINDEXED, name_en, name_cs, name_uk, symbol, entity_id UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 1'
);
CREATE TRIGGER IF NOT EXISTS trg_fts_formula_ai AFTER INSERT ON formula BEGIN
    INSERT INTO entity_fts(kind, id, name_en, name_cs, name_uk, symbol, entity_id)
    VALUES ('formula', new.id, coalesce(json_extract(new.name, '$.en-us'), ''), coalesce(json_extract(new.name, '$.cs-cz'), ''), coalesce(json_extract(new.name, '$.en-uk'), ''), '', new.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_fts_formula_ad AFTER DELETE ON formula BEGIN
    DELETE FROM entity_fts WHERE kind = 'formula' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_fts_formula_au AFTER UPDATE ON formula BEGIN
    DELETE FROM entity_fts WHERE kind = 'formula' AND entity_id = old.id;
    INSERT INTO entity_fts(kind, id, name_en, name_cs, name_uk, symbol, entity_id)
    VALUES ('formula', new.id, coalesce(json_extract(new.name, '$.en-us'), ''), coalesce(json_extract(new.name, '$.cs-cz'), ''), coalesce(json_extract(new.name, '$.en-uk'), ''), '', new.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_fts_quantity_ai AFTER INSERT ON quantity BEGIN
    INSERT INTO entity_fts(kind, id, name_en, name_cs, name_uk, symbol, entity_id)
    VALUES ('quantity', new.id, coalesce(json_extract(new.name, '$.en-us'), ''), coalesce(json_extract(new.name, '$.cs-cz'), ''), coalesce(json_extract(new.name, '$.en-uk'), ''), coalesce(new.symbol, ''), new.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_fts_quantity_ad AFTER DELETE ON quantity BEGIN
    DELETE FROM entity_fts WHERE kind = 'quantity' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_fts_quantity_au AFTER UPDATE ON quantity BEGIN
    DELETE FROM entity_fts WHERE kind = 'quantity' AND entity_id = old.id;
    INSERT INTO entity_fts(kind, id, name_en, name_cs, name_uk, symbol, entity_id)
    VALUES ('quantity', new.id, coalesce(json_extract(new.name, '$.en-us'), ''), coalesce(json_extract(new.name, '$.cs-cz'), ''), coalesce(json_extract(new.name, '$.en-uk'), ''), coalesce(new.symbol, ''), new.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_fts_unit_ai AFTER INSERT ON unit BEGIN
    INSERT INTO entity_fts(kind, id, name_en, name_cs, name_uk, symbol, entity_id)
    VALUES ('unit', new.id, coalesce(json_extract(new.name, '$.en-us'), ''), coalesce(json_extract(new.name, '$.cs-cz'), ''), coalesce(json_extract(new.name, '$.en-uk'), ''), coalesce(new.symbol, ''), new.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_fts_unit_ad AFTER DELETE ON unit BEGIN
    DELETE FROM entity_fts WHERE kind = 'unit' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_fts_unit_au AFTER UPDATE ON unit BEGIN
    DELETE FROM entity_fts WHERE kind = 'unit' AND entity_id = old.id;
    INSERT INTO entity_fts(kind, id, name_en, name_cs, name_uk, symbol, entity_id)
    VALUES ('unit', new.id, coalesce(json_extract(new.name, '$.en-us'), ''), coalesce(json_extract(new.name, '$.cs-cz'), ''), coalesce(json_extract(new.name, '$.en-uk'), ''), coalesce(new.symbol, ''), new.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_fts_constant_ai AFTER INSERT ON constant BEGIN
    INSERT INTO entity_fts(kind, id, name_en, name_cs, name_uk, symbol, entity_id)
    VALUES ('constant', new.id, coalesce(json_extract(new.name, '$.en-us'), ''), coalesce(json_extract(new.name, '$.cs-cz'), ''), coalesce(json_extract(new.name, '$.en-uk'), ''), coalesce(new.symbol, ''), new.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_fts_constant_ad AFTER DELETE ON constant BEGIN
    DELETE FROM entity_fts WHERE kind = 'constant' AND entity_id = old.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_fts_constant_au AFTER UPDATE ON constant BEGIN
    DELETE FROM entity_fts WHERE kind = 'constant' AND entity_id = old.id;
    INSERT INTO entity_fts(kind, id, name_en, name_cs, name_uk, symbol, entity_id)
    VALUES ('constant', new.id, coalesce(json_extract(new.name, '$.en-us'), ''), coalesce(json_extract(new.name, '$.cs-cz'), ''), coalesce(json_extract(new.name, '$.en-uk'), ''), coalesce(new.symbol, ''), new.id);
END;
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
