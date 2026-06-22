-- ============================================================
-- Views and queries for common access patterns
-- ============================================================

-- 1. Formula overview: one row per formula with summary counts
CREATE VIEW IF NOT EXISTS v_formula_summary AS
SELECT
    f.id,
    json_extract(f.name, '$.en-us') AS name_en,
    json_extract(f.science, '$.en-us') AS science_en,
    json_extract(f.branch, '$.en-us') AS branch_en,
    json_extract(f.topic, '$.en-us') AS topic_en,
    f.difficulty,
    (SELECT COUNT(*) FROM formula_items fi WHERE fi.formula_id = f.id) AS item_count,
    (SELECT COUNT(*) FROM formula_items fi WHERE fi.formula_id = f.id AND fi.is_primary = 1) AS primary_count,
    (SELECT COUNT(*) FROM conditions c WHERE c.formula_id = f.id) AS condition_count,
    (SELECT COUNT(*) FROM formula_relations fr WHERE fr.formula_id = f.id) AS relation_count
FROM formulas f
ORDER BY f.id;

-- 2. Expand a formula with items and variable details
CREATE VIEW IF NOT EXISTS v_formula_expanded AS
SELECT
    f.id AS formula_id,
    json_extract(f.name, '$.en-us') AS formula_name,
    fi.term,
    fi.is_primary,
    fi.sort_order,
    fi.coeff_value,
    fi.coeff_special,
    fi.coeff_exponent,
    fi.variable_id,
    fi.var_exponent,
    fi.label,
    fi.latex_prefix,
    fi.latex_suffix,
    v.latex AS var_latex,
    json_extract(v.name, '$.en-us') AS var_name_en,
    v.dim_M, v.dim_L, v.dim_T, v.dim_I, v.dim_Θ, v.dim_N, v.dim_J
FROM formulas f
JOIN formula_items fi ON fi.formula_id = f.id
LEFT JOIN variables v ON v.id = fi.variable_id
ORDER BY f.id, fi.term, fi.is_primary DESC, fi.sort_order;

-- 3. Variables used in a formula (distinct)
CREATE VIEW IF NOT EXISTS v_formula_variables AS
SELECT DISTINCT
    fi.formula_id,
    v.id AS variable_id,
    v.latex,
    json_extract(v.name, '$.en-us') AS name_en,
    v.si_unit,
    v.dim_M, v.dim_L, v.dim_T, v.dim_I, v.dim_Θ, v.dim_N, v.dim_J
FROM formula_items fi
JOIN variables v ON v.id = fi.variable_id
ORDER BY fi.formula_id, v.id;

-- 4. Formulas that use a given variable
CREATE VIEW IF NOT EXISTS v_variable_usage AS
SELECT
    v.id AS variable_id,
    v.latex,
    json_extract(v.name, '$.en-us') AS variable_name,
    f.id AS formula_id,
    json_extract(f.name, '$.en-us') AS formula_name,
    fi.term,
    fi.is_primary,
    fi.var_exponent,
    fi.label
FROM variables v
JOIN formula_items fi ON fi.variable_id = v.id
JOIN formulas f ON f.id = fi.formula_id
ORDER BY v.id, f.id, fi.term;

-- 5. Conditions with formula names
CREATE VIEW IF NOT EXISTS v_conditions AS
SELECT
    c.id AS condition_id,
    json_extract(c.name, '$.en-us') AS condition_name,
    f1.id AS formula_id,
    json_extract(f1.name, '$.en-us') AS formula_name,
    f2.id AS replacement_id,
    json_extract(f2.name, '$.en-us') AS replacement_name,
    c.default_on,
    c.sort_order
FROM conditions c
JOIN formulas f1 ON f1.id = c.formula_id
JOIN formulas f2 ON f2.id = c.replacement_formula_id
ORDER BY f1.id, c.sort_order;

-- 6. Formula relations with names
CREATE VIEW IF NOT EXISTS v_formula_relations AS
SELECT
    fr.relation_type,
    f1.id AS formula_id,
    json_extract(f1.name, '$.en-us') AS formula_name,
    f2.id AS related_id,
    json_extract(f2.name, '$.en-us') AS related_name
FROM formula_relations fr
JOIN formulas f1 ON f1.id = fr.formula_id
JOIN formulas f2 ON f2.id = fr.related_id
ORDER BY fr.relation_type, f1.id;

-- 7. Units for each variable
CREATE VIEW IF NOT EXISTS v_units AS
SELECT
    u.id AS unit_id,
    u.symbol,
    u.factor_to_si,
    u.offset,
    u.si_unit,
    u.unit_system,
    v.id AS variable_id,
    json_extract(v.name, '$.en-us') AS variable_name,
    v.latex AS variable_latex
FROM units u
JOIN variables v ON v.id = u.variable_id
ORDER BY v.id, u.si_unit DESC, u.id;

-- 8. All formulas in a topic
CREATE VIEW IF NOT EXISTS v_formulas_by_topic AS
SELECT
    json_extract(f.branch, '$.en-us') AS branch_en,
    json_extract(f.topic, '$.en-us') AS topic_en,
    f.difficulty,
    f.id AS formula_id,
    json_extract(f.name, '$.en-us') AS formula_name
FROM formulas f
ORDER BY branch_en, topic_en, f.difficulty, f.id;

-- ============================================================
-- Parameterised queries (use as prepared statements)
-- ============================================================

-- Get formula by ID with all items expanded:
--   SELECT * FROM v_formula_expanded WHERE formula_id = ?;

-- Get all formulas using a given variable:
--   SELECT formula_id, formula_name, term, is_primary, var_exponent, label
--   FROM v_variable_usage WHERE variable_id = ?;

-- List conditions for a formula:
--   SELECT * FROM v_conditions WHERE formula_id = ?;

-- Get related formulas (forward):
--   SELECT related_id, related_name, relation_type
--   FROM v_formula_relations WHERE formula_id = ?;

-- Get related formulas (backward):
--   SELECT formula_id, formula_name, relation_type
--   FROM v_formula_relations WHERE related_id = ?;

-- Find all SI units:
--   SELECT * FROM v_units WHERE si_unit = 1;

-- Convert a value between units (application-level math):
--   SELECT u.unit_id, u.symbol, u.factor_to_si, u.offset
--   FROM v_units u WHERE u.variable_id = ?;
