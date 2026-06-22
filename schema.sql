PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. formulas
-- ============================================================
CREATE TABLE IF NOT EXISTS formulas (
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
-- 2. formula_items
-- ============================================================
CREATE TABLE IF NOT EXISTS formula_items (
    formula_id     TEXT NOT NULL REFERENCES formulas(id),
    term           INTEGER NOT NULL,
    is_primary     INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
    sort_order     INTEGER NOT NULL DEFAULT 0,
    coeff_value    REAL,
    coeff_special  TEXT,
    coeff_exponent REAL DEFAULT 1,
    variable_id    TEXT REFERENCES variables(id),
    var_exponent   REAL DEFAULT 1,
    label          TEXT,
    latex_prefix   TEXT,
    latex_suffix   TEXT,
    latex_override TEXT,

    PRIMARY KEY (formula_id, term, is_primary, sort_order)
);

-- ============================================================
-- 3. conditions
-- ============================================================
CREATE TABLE IF NOT EXISTS conditions (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    name                   TEXT NOT NULL,       -- JSON i18n
    formula_id             TEXT NOT NULL REFERENCES formulas(id),
    replacement_formula_id TEXT NOT NULL REFERENCES formulas(id),
    default_on             INTEGER NOT NULL DEFAULT 1 CHECK (default_on IN (0,1)),
    sort_order             INTEGER NOT NULL DEFAULT 0,
    created                TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    modified               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================
-- 4. formula_relations
-- ============================================================
CREATE TABLE IF NOT EXISTS formula_relations (
    formula_id    TEXT NOT NULL REFERENCES formulas(id),
    related_id    TEXT NOT NULL REFERENCES formulas(id),
    relation_type TEXT NOT NULL CHECK (relation_type IN (
        'alternative', 'derivation', 'special_case', 'prerequisite', 'generalization'
    )),

    UNIQUE (formula_id, related_id)
);

-- ============================================================
-- 5. variables
-- ============================================================
CREATE TABLE IF NOT EXISTS variables (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,       -- JSON i18n
    latex       TEXT NOT NULL,
    science     TEXT,                -- JSON i18n
    branch      TEXT,                -- JSON i18n
    topic       TEXT,                -- JSON i18n
    difficulty  INTEGER CHECK (difficulty BETWEEN 1 AND 10),
    description TEXT,                -- JSON i18n
    links       TEXT,                -- JSON array
    si_unit     TEXT,                -- JSON array: [{"unit":"<id>","exponent":<n>},...]
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
-- 6. units
-- ============================================================
CREATE TABLE IF NOT EXISTS units (
    id           TEXT PRIMARY KEY,
    variable_id  TEXT NOT NULL REFERENCES variables(id),
    symbol       TEXT NOT NULL,
    name         TEXT NOT NULL,        -- JSON i18n: {"en-us":"Meter","en-uk":"Metre"}
    factor_to_si REAL NOT NULL DEFAULT 1,
    offset       REAL NOT NULL DEFAULT 0,
    si_unit      INTEGER NOT NULL DEFAULT 0 CHECK (si_unit IN (0,1)),
    unit_system  TEXT CHECK (unit_system IN ('SI','CGS','Imperial') OR unit_system IS NULL)
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_formula_items_variable    ON formula_items(variable_id);
CREATE INDEX IF NOT EXISTS idx_conditions_formula        ON conditions(formula_id);
CREATE INDEX IF NOT EXISTS idx_conditions_replacement    ON conditions(replacement_formula_id);
CREATE INDEX IF NOT EXISTS idx_formula_relations_formula ON formula_relations(formula_id);
CREATE INDEX IF NOT EXISTS idx_formula_relations_related ON formula_relations(related_id);
CREATE INDEX IF NOT EXISTS idx_units_variable            ON units(variable_id);

-- ============================================================
-- FTS5 full-text search
-- ============================================================
CREATE VIRTUAL TABLE IF NOT EXISTS formula_fts USING fts5(
    formula_id UNINDEXED,
    name,
    description,
    variables    -- space-separated variable names that appear in the formula
);

CREATE VIRTUAL TABLE IF NOT EXISTS variable_fts USING fts5(
    variable_id UNINDEXED,
    name,
    latex
);

CREATE VIRTUAL TABLE IF NOT EXISTS unit_fts USING fts5(
    unit_id UNINDEXED,
    name,
    symbol
);
