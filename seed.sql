-- ============================================================
-- Seed data: quantities, units, formulas, items, conditions, relations
-- ============================================================

-- --------------------------------------------------
-- Quantities (dim columns: M L T I Θ N J)
-- --------------------------------------------------
INSERT INTO quantity (id, name, symbol, science, branch, topic, difficulty, default_unit, dim_M, dim_L, dim_T, dim_I, dim_Θ, dim_N, dim_J) VALUES
  ('force',                '{"en-us": "Force"}',                'F', '{"en-us": "Physics"}', '{"en-us": "Classical mechanics"}', '{"en-us": "Dynamics"}',           2, '[{"unit": "newton", "exponent": 1}]',                         1,  1, -2, 0, 0, 0, 0),
  ('mass',                 '{"en-us": "Mass"}',                 'm', '{"en-us": "Physics"}', '{"en-us": "Classical mechanics"}', '{"en-us": "Dynamics"}',           1, '[{"unit": "kilogram", "exponent": 1}]',                       1,  0,  0, 0, 0, 0, 0),
  ('acceleration',         '{"en-us": "Acceleration"}',         'a', '{"en-us": "Physics"}', '{"en-us": "Classical mechanics"}', '{"en-us": "Kinematics"}',         2, NULL,                                                         0,  1, -2, 0, 0, 0, 0),
  ('energy',               '{"en-us": "Energy"}',               'E', '{"en-us": "Physics"}', '{"en-us": "Classical mechanics"}', '{"en-us": "Energy"}',             2, NULL,                                                         1,  2, -2, 0, 0, 0, 0),
  ('velocity',             '{"en-us": "Velocity"}',             'v', '{"en-us": "Physics"}', '{"en-us": "Classical mechanics"}', '{"en-us": "Kinematics"}',         2, NULL,                                                         0,  1, -1, 0, 0, 0, 0),
  ('length',               '{"en-us": "Length"}',               's', '{"en-us": "Physics"}', '{"en-us": "Classical mechanics"}', '{"en-us": "Kinematics"}',         1, '[{"unit": "metre", "exponent": 1}]',                          1,  0,  0, 0, 0, 0, 0),
  ('internal_energy',      '{"en-us": "Internal energy"}',      'U', '{"en-us": "Physics"}', '{"en-us": "Thermodynamics"}',      '{"en-us": "First law"}',          3, NULL,                                                         1,  2, -2, 0, 0, 0, 0),
  ('heat',                 '{"en-us": "Heat"}',                 'Q', '{"en-us": "Physics"}', '{"en-us": "Thermodynamics"}',      '{"en-us": "First law"}',          3, NULL,                                                         1,  2, -2, 0, 0, 0, 0),
  ('work',                 '{"en-us": "Work"}',                 'W', '{"en-us": "Physics"}', '{"en-us": "Classical mechanics"}', '{"en-us": "Energy"}',             2, NULL,                                                         1,  2, -2, 0, 0, 0, 0),
  ('pressure',             '{"en-us": "Pressure"}',             'P', '{"en-us": "Physics"}', '{"en-us": "Thermodynamics"}',      '{"en-us": "Equations of state"}', 3, NULL,                                                         1, -1, -2, 0, 0, 0, 0),
  ('volume',               '{"en-us": "Volume"}',               'V', '{"en-us": "Physics"}', '{"en-us": "Thermodynamics"}',      '{"en-us": "Equations of state"}', 2, NULL,                                                         0,  3,  0, 0, 0, 0, 0),
  ('amount',               '{"en-us": "Amount of substance"}',  'n', '{"en-us": "Physics"}', '{"en-us": "Thermodynamics"}',      '{"en-us": "Equations of state"}', 3, NULL,                                                         0,  0,  0, 0, 0, 1, 0),
  ('gas_constant',         '{"en-us": "Gas constant"}',         'R', '{"en-us": "Physics"}', '{"en-us": "Thermodynamics"}',      '{"en-us": "Equations of state"}', 4, NULL,                                                         1,  2, -2, 0, 0, -1, 0),
  ('temperature',          '{"en-us": "Temperature"}',          'T', '{"en-us": "Physics"}', '{"en-us": "Thermodynamics"}',      '{"en-us": "Equations of state"}', 2, '[{"unit": "kelvin", "exponent": 1}]',                         0,  0,  0, 0, 1, 0, 0),
  ('period',               '{"en-us": "Period"}',               'T', '{"en-us": "Physics"}', '{"en-us": "Classical mechanics"}', '{"en-us": "Orbital mechanics"}',   4, '[{"unit": "second", "exponent": 1}]',                         0,  0,  1, 0, 0, 0, 0),
  ('gravitational_constant','{"en-us": "Gravitational constant"}','G','{"en-us": "Physics"}','{"en-us": "Classical mechanics"}', '{"en-us": "Gravitation"}',        4, '[{"unit": "metre", "exponent": 3}, {"unit": "kilogram", "exponent": -1}, {"unit": "second", "exponent": -2}]', -1, 3, -2, 0, 0, 0, 0),
  ('resistance',           '{"en-us": "Resistance"}',           'R', '{"en-us": "Physics"}', '{"en-us": "Electromagnetism"}',    '{"en-us": "Circuits"}',           3, '[{"unit": "ohm", "exponent": 1}]',                            1,  2, -3, -2, 0, 0, 0),
  ('momentum',             '{"en-us": "Momentum"}',             'p', '{"en-us": "Physics"}', '{"en-us": "Classical mechanics"}', '{"en-us": "Dynamics"}',           2, NULL,                                                         1,  1, -1, 0, 0, 0, 0);

-- --------------------------------------------------
-- Units
-- --------------------------------------------------
INSERT INTO unit (id, name, symbol, quantity_id, default_unit, unit_system, factor, offset) VALUES
  ('metre',          '{"en-us": "Meter", "en-uk": "Metre"}',               'm',                'length',       1, 'SI',  1,      0),
  ('centimetre',     '{"en-us": "Centimeter", "en-uk": "Centimetre"}',     'cm',               'length',       0, 'CGS', 0.01,   0),
  ('kilogram',       '{"en-us": "Kilogram"}',                              'kg',               'mass',         1, 'SI',  1,      0),
  ('gram',           '{"en-us": "Gram"}',                                  'g',                'mass',         0, 'CGS', 0.001,  0),
  ('kelvin',         '{"en-us": "Kelvin"}',                                'K',                'temperature',  1, 'SI',  1,      0),
  ('degree_celsius', '{"en-us": "Degree Celsius"}',                        '\\degreeCelsius',  'temperature',  0, NULL, 1,     273.15),
  ('newton',         '{"en-us": "Newton"}',                                '\\newton',         'force',        1, 'SI',  1,      0),
  ('dyne',           '{"en-us": "Dyne"}',                                  'dyn',              'force',        0, 'CGS', 0.00001,0),
  ('ohm',            '{"en-us": "Ohm"}',                                   '\\ohm',            'resistance',   1, 'SI',  1,      0),
  ('second',         '{"en-us": "Second"}',                                's',                'period',       1, 'SI',  1,      0);

-- --------------------------------------------------
-- Formulas
-- --------------------------------------------------
INSERT INTO formula (id, name, science, branch, topic, difficulty, description) VALUES
  ('newton_second_law_of_motion',
   '{"en-us": "Newton''s second law of motion"}',
   '{"en-us": "Physics"}',
   '{"en-us": "Classical mechanics"}',
   '{"en-us": "Dynamics"}',
   2,
   '{"en-us": "The net force on a body is equal to its mass times its acceleration."}'),

  ('kinetic_energy',
   '{"en-us": "Kinetic energy"}',
   '{"en-us": "Physics"}',
   '{"en-us": "Classical mechanics"}',
   '{"en-us": "Energy"}',
   2,
   '{"en-us": "The kinetic energy of a body is half its mass times the square of its velocity."}'),

  ('suvat_v2',
   '{"en-us": "SUVAT: v² = u² + 2as"}',
   '{"en-us": "Physics"}',
   '{"en-us": "Classical mechanics"}',
   '{"en-us": "Kinematics"}',
   3,
   '{"en-us": "Final velocity squared equals initial velocity squared plus twice acceleration times displacement."}'),

  ('first_law_thermodynamics',
   '{"en-us": "First law of thermodynamics"}',
   '{"en-us": "Physics"}',
   '{"en-us": "Thermodynamics"}',
   '{"en-us": "First law"}',
   3,
   '{"en-us": "The change in internal energy of a system equals heat added to the system minus work done by the system."}'),

  ('conservation_of_momentum',
   '{"en-us": "Conservation of momentum"}',
   '{"en-us": "Physics"}',
   '{"en-us": "Classical mechanics"}',
   '{"en-us": "Dynamics"}',
   2,
   '{"en-us": "In a closed system, total momentum before a collision equals total momentum after."}'),

  ('ideal_gas_law',
   '{"en-us": "Ideal gas law"}',
   '{"en-us": "Physics"}',
   '{"en-us": "Thermodynamics"}',
   '{"en-us": "Equations of state"}',
   3,
   '{"en-us": "The pressure of an ideal gas times its volume equals the amount of gas times the gas constant times temperature."}'),

  ('keplers_third_law',
   '{"en-us": "Kepler''s third law"}',
   '{"en-us": "Physics"}',
   '{"en-us": "Classical mechanics"}',
   '{"en-us": "Orbital mechanics"}',
   4,
   '{"en-us": "The square of a planet''s orbital period is proportional to the cube of its semi-major axis."}'),

  ('parallel_resistance',
   '{"en-us": "Parallel resistance"}',
   '{"en-us": "Physics"}',
   '{"en-us": "Electromagnetism"}',
   '{"en-us": "Circuits"}',
   3,
   '{"en-us": "The reciprocal of total resistance in parallel equals the sum of the reciprocals of individual resistances."}');

-- --------------------------------------------------
-- Formula items
-- --------------------------------------------------

-- F = ma
-- 1 = F⁻¹ · m¹ · a¹
INSERT INTO formula_item (formula_id, term, is_primary, sort_order, quantity_id, var_exponent) VALUES
  ('newton_second_law_of_motion', 1, 1, 0, 'force',        -1),
  ('newton_second_law_of_motion', 1, 0, 0, 'mass',          1),
  ('newton_second_law_of_motion', 1, 0, 1, 'acceleration',  1);

-- Ek = ½mv²
-- 1 = Ek⁻¹ · 2⁻¹ · m¹ · v²
INSERT INTO formula_item (formula_id, term, is_primary, sort_order, coeff_value, coeff_exponent, quantity_id, var_exponent, label) VALUES
  ('kinetic_energy', 1, 1, 0, NULL, NULL, 'energy', -1, 'k'),
  ('kinetic_energy', 1, 0, 0, 2,     -1,   NULL,    NULL, NULL),
  ('kinetic_energy', 1, 0, 1, NULL, NULL, 'mass',   1,    NULL),
  ('kinetic_energy', 1, 0, 2, NULL, NULL, 'velocity', 2,  NULL);

-- v² = u² + 2ar  (v=final, u=initial) — symbol_overwrite: s→r, v→u for initial velocity
-- 1 = v_final⁻² · u_initial² · 2 · a¹ · r¹
INSERT INTO formula_item (formula_id, term, is_primary, sort_order, coeff_value, quantity_id, var_exponent, label, symbol_overwrite) VALUES
  ('suvat_v2', 1, 1, 0, NULL, 'velocity',    -2, 'final',   NULL),
  ('suvat_v2', 2, 0, 0, NULL, 'velocity',     2,  'initial', 'u'),
  ('suvat_v2', 3, 0, 0, 2,    NULL,          NULL, NULL,     NULL),
  ('suvat_v2', 3, 0, 1, NULL, 'acceleration', 1,   NULL,     NULL),
  ('suvat_v2', 3, 0, 2, NULL, 'length',       1,   NULL,     'r');

-- ΔU = Q − W
-- 1 = ΔU⁻¹ · Q¹ · (−1 · W¹)
INSERT INTO formula_item (formula_id, term, is_primary, sort_order, coeff_value, coeff_exponent, quantity_id, var_exponent, latex_prefix, latex_suffix) VALUES
  ('first_law_thermodynamics', 1, 1, 0, NULL, NULL, 'internal_energy', -1, '\Delta{', '}'),
  ('first_law_thermodynamics', 2, 0, 0, NULL, NULL, 'heat',            1,  NULL,       NULL),
  ('first_law_thermodynamics', 3, 0, 0, -1,   1,    NULL,              NULL, NULL,       NULL),
  ('first_law_thermodynamics', 3, 0, 1, NULL, NULL, 'work',            1,   NULL,       NULL);

-- m₁u₁ + m₂u₂ = m₁v₁ + m₂v₂
INSERT INTO formula_item (formula_id, term, is_primary, sort_order, quantity_id, var_exponent, label) VALUES
  ('conservation_of_momentum', 1, 1, 0, 'mass',     -1, '1'),
  ('conservation_of_momentum', 1, 1, 1, 'velocity', -1, 'initial'),
  ('conservation_of_momentum', 2, 1, 0, 'mass',     -1, '2'),
  ('conservation_of_momentum', 2, 1, 1, 'velocity', -1, 'initial'),
  ('conservation_of_momentum', 3, 0, 0, 'mass',     1,  '1'),
  ('conservation_of_momentum', 3, 0, 1, 'velocity', 1,  'final'),
  ('conservation_of_momentum', 4, 0, 0, 'mass',     1,  '2'),
  ('conservation_of_momentum', 4, 0, 1, 'velocity', 1,  'final');

-- PV = nRT
INSERT INTO formula_item (formula_id, term, is_primary, sort_order, quantity_id, var_exponent) VALUES
  ('ideal_gas_law', 1, 1, 0, 'pressure',     -1),
  ('ideal_gas_law', 1, 1, 1, 'volume',       -1),
  ('ideal_gas_law', 2, 0, 0, 'amount',        1),
  ('ideal_gas_law', 2, 0, 1, 'gas_constant',  1),
  ('ideal_gas_law', 2, 0, 2, 'temperature',   1);

-- T² = (4π²/GM) · a³
INSERT INTO formula_item (formula_id, term, is_primary, sort_order, coeff_value, coeff_special, coeff_exponent, quantity_id, var_exponent) VALUES
  ('keplers_third_law', 1, 1, 0, NULL, NULL, NULL, 'period',                -2),
  ('keplers_third_law', 2, 0, 0, 4,    NULL, 1,    NULL,                   NULL),
  ('keplers_third_law', 2, 0, 1, NULL, 'pi', 2,    NULL,                   NULL),
  ('keplers_third_law', 2, 0, 2, NULL, NULL, NULL, 'gravitational_constant', -1),
  ('keplers_third_law', 2, 0, 3, NULL, NULL, NULL, 'mass',                   -1),
  ('keplers_third_law', 2, 0, 4, NULL, NULL, NULL, 'length',                  3);

-- 1/R = 1/R₁ + 1/R₂
INSERT INTO formula_item (formula_id, term, is_primary, sort_order, quantity_id, var_exponent, label) VALUES
  ('parallel_resistance', 1, 1, 0, 'resistance', 1,  NULL),
  ('parallel_resistance', 2, 0, 0, 'resistance', -1, '1'),
  ('parallel_resistance', 3, 0, 0, 'resistance', -1, '2');

INSERT INTO formula (id, name, science, branch, topic, difficulty, description) VALUES
  ('first_law_thermodynamics_adiabatic',
   '{"en-us": "First law (adiabatic): ΔU = −W"}',
   '{"en-us": "Physics"}', '{"en-us": "Thermodynamics"}', '{"en-us": "First law"}', 3,
   '{"en-us": "For an adiabatic process, no heat is exchanged so the change in internal energy equals negative work."}'),
  ('first_law_thermodynamics_isochoric',
   '{"en-us": "First law (isochoric): ΔU = Q"}',
   '{"en-us": "Physics"}', '{"en-us": "Thermodynamics"}', '{"en-us": "First law"}', 3,
   '{"en-us": "For an isochoric process, no work is done so the change in internal energy equals the heat added."}'),
  ('van_der_waals',
   '{"en-us": "Van der Waals equation of state"}',
   '{"en-us": "Physics"}', '{"en-us": "Thermodynamics"}', '{"en-us": "Equations of state"}', 5,
   '{"en-us": "A more accurate equation of state for real gases that accounts for intermolecular forces and finite molecular size."}');

-- ΔU = −W (adiabatic)
INSERT INTO formula_item (formula_id, term, is_primary, sort_order, coeff_value, coeff_exponent, quantity_id, var_exponent, latex_prefix, latex_suffix) VALUES
  ('first_law_thermodynamics_adiabatic', 1, 1, 0, NULL, NULL, 'internal_energy', -1, '\Delta{', '}'),
  ('first_law_thermodynamics_adiabatic', 2, 0, 0, -1,   1,    NULL,             NULL, NULL,       NULL),
  ('first_law_thermodynamics_adiabatic', 2, 0, 1, NULL, NULL, 'work',            1,   NULL,       NULL);

-- ΔU = Q (isochoric)
INSERT INTO formula_item (formula_id, term, is_primary, sort_order, quantity_id, var_exponent, latex_prefix, latex_suffix) VALUES
  ('first_law_thermodynamics_isochoric', 1, 1, 0, 'internal_energy', -1, '\Delta{', '}'),
  ('first_law_thermodynamics_isochoric', 2, 0, 0, 'heat',             1,  NULL,       NULL);

-- --------------------------------------------------
-- Conditions
-- --------------------------------------------------
INSERT INTO condition (name, formula_id, replacement_formula_id, default_on, sort_order) VALUES
  ('{"en-us": "Adiabatic process (Q = 0)"}',    'first_law_thermodynamics', 'first_law_thermodynamics_adiabatic', 0, 1),
  ('{"en-us": "Isochoric process (W = 0)"}',    'first_law_thermodynamics', 'first_law_thermodynamics_isochoric', 0, 2),
  ('{"en-us": "Ideal gas assumption"}',          'ideal_gas_law',            'van_der_waals',                      1, 1);

-- --------------------------------------------------
-- Formula relations
-- --------------------------------------------------
INSERT INTO formula_relation (formula_id, related_id, relation_type) VALUES
  ('kinetic_energy',            'newton_second_law_of_motion', 'derivation'),
  ('ideal_gas_law',             'keplers_third_law',           'prerequisite'),
  ('first_law_thermodynamics',  'kinetic_energy',              'derivation');
