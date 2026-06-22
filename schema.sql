PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. formula
-- ============================================================
CREATE TABLE IF NOT EXISTS formula (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,       -- JSON i18n: {"en-us":"...","en-uk":"..."}
    science     TEXT,                -- JSON i18n
    branch      TEXT,                -- JSON i18n
    topic       TEXT,                -- JSON i18n
    difficulty  INTEGER CHECK (difficulty BETWEEN 1 AND 10),
    description TEXT,                -- JSON i18n
    links       TEXT,                -- JSON array: [{"label":{i18n},"url":"..."}]
    created     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    modified    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================
-- 2. formula_item
-- ============================================================
CREATE TABLE IF NOT EXISTS formula_item (
    formula_id       TEXT NOT NULL REFERENCES formula(id),
    term             INTEGER NOT NULL,
    is_primary       INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
    sort_order       INTEGER NOT NULL DEFAULT 0,
    coeff_value      REAL,
    coeff_special    TEXT,
    coeff_exponent   REAL DEFAULT 1,
    quantity_id      TEXT REFERENCES quantity(id),
    var_exponent     REAL DEFAULT 1,
    label            TEXT,
    latex_prefix     TEXT,
    latex_suffix     TEXT,
    symbol_overwrite TEXT,

    PRIMARY KEY (formula_id, term, is_primary, sort_order)
);

-- ============================================================
-- 3. condition
-- ============================================================
CREATE TABLE IF NOT EXISTS condition (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    name                   TEXT NOT NULL,       -- JSON i18n
    formula_id             TEXT NOT NULL REFERENCES formula(id),
    replacement_formula_id TEXT NOT NULL REFERENCES formula(id),
    default_on             INTEGER NOT NULL DEFAULT 1 CHECK (default_on IN (0,1)),
    sort_order             INTEGER NOT NULL DEFAULT 0,
    created                TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    modified               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================
-- 4. formula_relation
-- ============================================================
CREATE TABLE IF NOT EXISTS formula_relation (
    formula_id    TEXT NOT NULL REFERENCES formula(id),
    related_id    TEXT NOT NULL REFERENCES formula(id),
    relation_type TEXT NOT NULL CHECK (relation_type IN (
        'alternative', 'derivation', 'special_case', 'prerequisite', 'generalization'
    )),

    UNIQUE (formula_id, related_id)
);

-- ============================================================
-- 5. quantity
-- ============================================================
CREATE TABLE IF NOT EXISTS quantity (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,       -- JSON i18n
    symbol      TEXT NOT NULL,
    science     TEXT,                -- JSON i18n
    branch      TEXT,                -- JSON i18n
    topic       TEXT,                -- JSON i18n
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
-- 6. unit
-- ============================================================
CREATE TABLE IF NOT EXISTS unit (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,        -- JSON i18n: {"en-us":"Meter","en-uk":"Metre"}
    symbol       TEXT NOT NULL,
    quantity_id  TEXT NOT NULL REFERENCES quantity(id),
    default_unit INTEGER NOT NULL DEFAULT 0 CHECK (default_unit IN (0,1)),
    unit_system  TEXT CHECK (unit_system IN ('SI','CGS','Imperial') OR unit_system IS NULL),
    factor       REAL NOT NULL DEFAULT 1,
    offset       REAL NOT NULL DEFAULT 0
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_formula_item_quantity    ON formula_item(quantity_id);
CREATE INDEX IF NOT EXISTS idx_condition_formula        ON condition(formula_id);
CREATE INDEX IF NOT EXISTS idx_condition_replacement    ON condition(replacement_formula_id);
CREATE INDEX IF NOT EXISTS idx_formula_relation_formula ON formula_relation(formula_id);
CREATE INDEX IF NOT EXISTS idx_formula_relation_related ON formula_relation(related_id);
CREATE INDEX IF NOT EXISTS idx_unit_quantity            ON unit(quantity_id);

-- ============================================================
-- FTS5 full-text search
-- ============================================================
CREATE VIRTUAL TABLE IF NOT EXISTS formula_fts USING fts5(
    formula_id UNINDEXED,
    name,
    description,
    quantities    -- space-separated quantity names that appear in the formula
);

CREATE VIRTUAL TABLE IF NOT EXISTS quantity_fts USING fts5(
    quantity_id UNINDEXED,
    name,
    symbol
);

CREATE VIRTUAL TABLE IF NOT EXISTS unit_fts USING fts5(
    unit_id UNINDEXED,
    name,
    symbol
);
