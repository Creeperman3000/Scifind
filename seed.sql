-- ============================================================
-- Consolidated seed data: quantities, units, formulas, items, relations
-- ============================================================

INSERT OR IGNORE INTO quantity (id, name, symbol, symbol_overwrite, topic, difficulty, description, links, default_unit, dim_M, dim_L, dim_T, dim_I, dim_Θ, dim_N, dim_J) VALUES
  ('absorbed_dose', '{"en-us": "Absorbed dose"}', 'D', NULL, 'nuclear_physics', 4, NULL, NULL, '[{"unit": "gray", "exponent": 1}]', 0.0, 2.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('absorbed_dose_rate', '{"en-us": "Absorbed dose rate"}', '\dot{D}', NULL, 'nuclear_physics', 4, NULL, NULL, '[{"unit":"gray","exponent":1},{"unit":"second","exponent":-1}]', 0.0, 2.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('acceleration', '{"en-us": "Acceleration"}', 'a', NULL, 'kinematics', 2, NULL, NULL, '[{"unit":"metre","exponent":1},{"unit":"second","exponent":-2}]', 0.0, 1.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('activity', '{"en-us": "Activity"}', 'A', NULL, 'nuclear_physics', 3, NULL, NULL, '[{"unit": "becquerel", "exponent": 1}]', 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('amount', '{"en-us": "Amount of substance"}', 'n', NULL, 'ideal_gases', 3, NULL, NULL, '[{"unit": "mole", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
  ('angle', '{"en-us": "Plane angle"}', '\theta', NULL, 'trigonometric_identities', 1, NULL, NULL, '[{"unit": "radian", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('angular_acceleration', '{"en-us": "Angular acceleration"}', '\alpha', NULL, 'rotational_mechanics', 3, NULL, NULL, '[{"unit":"radian","exponent":1},{"unit":"second","exponent":-2}]', 0.0, 0.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('angular_momentum', '{"en-us": "Angular momentum"}', 'L', NULL, 'angular_momentum', 3, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":2},{"unit":"second","exponent":-1}]', 1.0, 2.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('angular_resolution', '{"en-us": "Angular resolution"}', '\theta_\mathrm{min}', NULL, 'diffraction', 4, NULL, NULL, '[{"unit": "radian", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('angular_velocity', '{"en-us": "Angular velocity"}', '\omega', NULL, 'rotational_mechanics', 3, NULL, NULL, '[{"unit":"radian","exponent":1},{"unit":"second","exponent":-1}]', 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('area', '{"en-us": "Area"}', 'A', NULL, 'plane_geometry', 1, NULL, NULL, '[{"unit":"metre","exponent":2}]', 0.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('capacitance', '{"en-us": "Capacitance"}', 'C', NULL, 'circuits', 3, NULL, NULL, '[{"unit": "farad", "exponent": 1}]', -1.0, -2.0, 4.0, 2.0, 0.0, 0.0, 0.0),
  ('catalytic_activity', '{"en-us": "Catalytic activity"}', 'k', NULL, 'chemical_kinetics', 3, NULL, NULL, '[{"unit": "katal", "exponent": 1}]', 0.0, 0.0, -1.0, 0.0, 0.0, 1.0, 0.0),
  ('catalytic_activity_concentration', '{"en-us": "Catalytic activity concentration"}', 'k_v', NULL, 'chemical_kinetics', 4, NULL, NULL, '[{"unit":"katal","exponent":1},{"unit":"metre","exponent":-3}]', 0.0, -3.0, -1.0, 0.0, 0.0, 1.0, 0.0),
  ('charge', '{"en-us": "Electric charge"}', 'Q', NULL, 'electrostatics', 2, NULL, NULL, '[{"unit": "coulomb", "exponent": 1}]', 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0),
  ('charge_density', '{"en-us": "Electric charge density"}', '\rho', NULL, 'electrostatics', 3, NULL, NULL, '[{"unit":"coulomb","exponent":1},{"unit":"metre","exponent":-3}]', 0.0, -3.0, 1.0, 1.0, 0.0, 0.0, 0.0),
  ('concentration', '{"en-us": "Concentration"}', 'c', NULL, 'solutions', 2, NULL, NULL, '[{"unit":"mole","exponent":1},{"unit":"metre","exponent":-3}]', 0.0, -3.0, 0.0, 0.0, 0.0, 1.0, 0.0),
  ('conductance', '{"en-us": "Electrical conductance"}', 'G', NULL, 'circuits', 3, NULL, NULL, '[{"unit": "siemens", "exponent": 1}]', -1.0, -2.0, 3.0, 2.0, 0.0, 0.0, 0.0),
  ('current', '{"en-us": "Electric current"}', 'I', NULL, 'current_electricity', 2, NULL, NULL, '[{"unit": "ampere", "exponent": 1}]', 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
  ('current_density', '{"en-us": "Current density"}', 'j', NULL, 'circuits', 3, NULL, NULL, '[{"unit":"ampere","exponent":1},{"unit":"metre","exponent":-2}]', 0.0, -2.0, 0.0, 1.0, 0.0, 0.0, 0.0),
  ('degree_of_polarization', '{"en-us": "Degree of polarization"}', 'P', NULL, 'polarization', 4, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('density', '{"en-us": "Density"}', '\rho', NULL, 'fluid_mechanics', 2, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":-3}]', 1.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('dose_equivalent', '{"en-us": "Dose equivalent"}', 'H', NULL, 'nuclear_physics', 4, NULL, NULL, '[{"unit": "sievert", "exponent": 1}]', 0.0, 2.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('dynamic_viscosity', '{"en-us": "Dynamic viscosity"}', '\eta', NULL, 'fluid_dynamics', 3, NULL, NULL, '[{"unit":"pascal","exponent":1},{"unit":"second","exponent":1}]', 1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('electric_field_strength', '{"en-us": "Electric field strength"}', 'E', NULL, 'electrostatics', 3, NULL, NULL, '[{"unit":"volt","exponent":1},{"unit":"metre","exponent":-1}]', 1.0, 1.0, -3.0, -1.0, 0.0, 0.0, 0.0),
  ('electric_potential', '{"en-us": "Electric potential"}', 'V', NULL, 'electrostatics', 3, NULL, NULL, '[{"unit": "volt", "exponent": 1}]', 1.0, 2.0, -3.0, -1.0, 0.0, 0.0, 0.0),
  ('electromagnetic_induction', '{"en-us": "Electromagnetic induction"}', '\mathcal{E}', NULL, 'electromagnetic_induction', 4, NULL, NULL, '[{"unit": "volt", "exponent": 1}]', 1.0, 2.0, -3.0, -1.0, 0.0, 0.0, 0.0),
  ('energy', '{"en-us": "Energy"}', 'E', NULL, 'work_and_energy', 2, NULL, NULL, '[{"unit": "joule", "exponent": 1}]', 1.0, 2.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('energy_density', '{"en-us": "Energy density"}', 'u', NULL, 'work_and_energy', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"metre","exponent":-3}]', 1.0, -1.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('entropy', '{"en-us": "Entropy"}', 'S', NULL, 'second_law', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"kelvin","exponent":-1}]', 1.0, 2.0, -2.0, 0.0, -1.0, 0.0, 0.0),
  ('equilibrium_constant', '{"en-us": "Equilibrium constant"}', 'K_\mathrm{eq}', NULL, 'chemical_equilibrium', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('exposure', '{"en-us": "Exposure"}', 'X', NULL, 'nuclear_physics', 4, NULL, NULL, '[{"unit":"coulomb","exponent":1},{"unit":"kilogram","exponent":-1}]', -1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0),
  ('force', '{"en-us": "Force"}', 'F', NULL, 'dynamics', 2, NULL, NULL, '[{"unit": "newton", "exponent": 1}]', 1.0, 1.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('frequency', '{"en-us": "Frequency"}', 'f', NULL, 'oscillations_and_waves', 2, NULL, NULL, '[{"unit": "hertz", "exponent": 1}]', 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('gas_constant', '{"en-us": "Gas constant"}', 'R', NULL, 'ideal_gases', 4, NULL, NULL, '[{"unit": "joule", "exponent": 1}, {"unit": "mole", "exponent": -1}, {"unit": "kelvin", "exponent": -1}]', 1.0, 2.0, -2.0, 0.0, 0.0, -1.0, 0.0),
  ('gravitational_constant', '{"en-us": "Gravitational constant"}', 'G', NULL, 'gravitation', 4, NULL, NULL, '[{"unit": "metre", "exponent": 3}, {"unit": "kilogram", "exponent": -1}, {"unit": "second", "exponent": -2}]', -1.0, 3.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('heat_engine_efficiency', '{"en-us": "Heat engine efficiency"}', '\eta', NULL, 'heat_engines', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('illuminance', '{"en-us": "Illuminance"}', 'E_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit": "lux", "exponent": 1}]', 0.0, -2.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('inductance', '{"en-us": "Inductance"}', 'L', NULL, 'circuits', 3, NULL, NULL, '[{"unit": "henry", "exponent": 1}]', 1.0, 2.0, -2.0, -2.0, 0.0, 0.0, 0.0),
  ('irradiance', '{"en-us": "Irradiance"}', 'E', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit":"watt","exponent":1},{"unit":"metre","exponent":-2}]', 1.0, 0.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('length', '{"en-us": "Length"}', 'l', NULL, 'kinematics', 1, NULL, NULL, '[{"unit": "metre", "exponent": 1}]', 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('luminance', '{"en-us": "Luminance"}', 'L_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit":"candela","exponent":1},{"unit":"metre","exponent":-2}]', 0.0, -2.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('luminous_flux', '{"en-us": "Luminous flux"}', '\Phi_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit": "lumen", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('luminous_intensity', '{"en-us": "Luminous intensity"}', 'I_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit": "candela", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('magnetic_field_strength', '{"en-us": "Magnetic field strength"}', 'H', NULL, 'magnetism', 3, NULL, NULL, '[{"unit":"ampere","exponent":1},{"unit":"metre","exponent":-1}]', 0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0),
  ('magnetic_flux', '{"en-us": "Magnetic flux"}', '\Phi', NULL, 'magnetism', 3, NULL, NULL, '[{"unit": "weber", "exponent": 1}]', 1.0, 2.0, -2.0, -1.0, 0.0, 0.0, 0.0),
  ('magnetic_flux_density', '{"en-us": "Magnetic flux density"}', 'B', NULL, 'magnetism', 3, NULL, NULL, '[{"unit": "tesla", "exponent": 1}]', 1.0, 0.0, -2.0, -1.0, 0.0, 0.0, 0.0),
  ('mass', '{"en-us": "Mass"}', 'm', NULL, 'dynamics', 1, NULL, NULL, '[{"unit": "kilogram", "exponent": 1}]', 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('mass_concentration', '{"en-us": "Mass concentration"}', '\gamma', NULL, 'solutions', 3, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":-3}]', 1.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('molar_energy', '{"en-us": "Molar energy"}', 'E_m', NULL, 'thermochemistry', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"mole","exponent":-1}]', 1.0, 2.0, -2.0, 0.0, 0.0, -1.0, 0.0),
  ('molar_entropy', '{"en-us": "Molar entropy"}', 'S_m', NULL, 'thermochemistry', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"mole","exponent":-1},{"unit":"kelvin","exponent":-1}]', 1.0, 2.0, -2.0, 0.0, -1.0, -1.0, 0.0),
  ('molar_mass', '{"en-us": "Molar mass"}', 'M', NULL, 'molar_mass', 2, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"mole","exponent":-1}]', 1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0),
  ('moment_of_inertia', '{"en-us": "Moment of inertia"}', 'I', NULL, 'moment_of_inertia', 3, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":2}]', 1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('momentum', '{"en-us": "Momentum"}', 'p', NULL, 'dynamics', 2, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":1},{"unit":"second","exponent":-1}]', 1.0, 1.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('permeability', '{"en-us": "Permeability"}', '\mu', NULL, 'magnetism', 4, NULL, NULL, '[{"unit":"henry","exponent":1},{"unit":"metre","exponent":-1}]', 1.0, 1.0, -2.0, -2.0, 0.0, 0.0, 0.0),
  ('permittivity', '{"en-us": "Permittivity"}', '\varepsilon', NULL, 'electrostatics', 4, NULL, NULL, '[{"unit":"farad","exponent":1},{"unit":"metre","exponent":-1}]', -1.0, -3.0, 4.0, 2.0, 0.0, 0.0, 0.0),
  ('power', '{"en-us": "Power"}', 'P', NULL, 'work_and_energy', 2, NULL, NULL, '[{"unit": "watt", "exponent": 1}]', 1.0, 2.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('pressure', '{"en-us": "Pressure"}', 'P', NULL, 'ideal_gases', 3, NULL, NULL, '[{"unit": "pascal", "exponent": 1}]', 1.0, -1.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('radiance', '{"en-us": "Radiance"}', 'L_e', NULL, 'electromagnetic_waves', 4, NULL, NULL, '[{"unit":"watt","exponent":1},{"unit":"metre","exponent":-2},{"unit":"steradian","exponent":-1}]', 1.0, 0.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('radiant_intensity', '{"en-us": "Radiant intensity"}', 'I_e', NULL, 'electromagnetic_waves', 4, NULL, NULL, '[{"unit":"watt","exponent":1},{"unit":"steradian","exponent":-1}]', 1.0, 2.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('rate_constant', '{"en-us": "Rate constant"}', 'k', NULL, 'chemical_kinetics', 3, NULL, NULL, '[{"unit": "second", "exponent": -1}]', 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('reflectance', '{"en-us": "Reflectance"}', 'R', NULL, 'reflection', 2, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('refractive_index', '{"en-us": "Refractive index"}', 'n', NULL, 'refraction', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('resistance', '{"en-us": "Resistance"}', 'R', NULL, 'circuits', 3, NULL, NULL, '[{"unit": "ohm", "exponent": 1}]', 1.0, 2.0, -3.0, -2.0, 0.0, 0.0, 0.0),
  ('reynolds_number', '{"en-us": "Reynolds number"}', '\mathit{Re}', NULL, 'reynolds_number', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('solid_angle', '{"en-us": "Solid angle"}', '\Omega', NULL, 'trigonometric_identities', 2, NULL, NULL, '[{"unit": "steradian", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('specific_energy', '{"en-us": "Specific energy"}', 'e', NULL, 'work_and_energy', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"kilogram","exponent":-1}]', 0.0, 2.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('specific_heat_capacity', '{"en-us": "Specific heat capacity"}', 'c', NULL, 'heat_transfer', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"kilogram","exponent":-1},{"unit":"kelvin","exponent":-1}]', 0.0, 2.0, -2.0, 0.0, -1.0, 0.0, 0.0),
  ('specific_volume', '{"en-us": "Specific volume"}', 'v', NULL, 'fluid_mechanics', 3, NULL, NULL, '[{"unit":"metre","exponent":3},{"unit":"kilogram","exponent":-1}]', -1.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('spring_constant', '{"en-us": "Spring constant"}', 'k', NULL, 'springs', 3, NULL, NULL, '[{"unit": "newton", "exponent": 1}, {"unit": "metre", "exponent": -1}]', 1.0, 0.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('surface_charge_density', '{"en-us": "Surface charge density"}', '\sigma', NULL, 'electrostatics', 3, NULL, NULL, '[{"unit":"coulomb","exponent":1},{"unit":"metre","exponent":-2}]', 0.0, -2.0, 1.0, 1.0, 0.0, 0.0, 0.0),
  ('surface_density', '{"en-us": "Surface density"}', '\rho_A', NULL, 'fluid_mechanics', 3, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":-2}]', 1.0, -2.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('surface_tension', '{"en-us": "Surface tension"}', '\gamma', NULL, 'surface_tension', 3, NULL, NULL, '[{"unit":"newton","exponent":1},{"unit":"metre","exponent":-1}]', 1.0, 0.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('temperature', '{"en-us": "Temperature"}', 'T', NULL, 'ideal_gases', 2, NULL, NULL, '[{"unit": "kelvin", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
  ('thermal_conductivity', '{"en-us": "Thermal conductivity"}', 'k', NULL, 'heat_transfer', 3, NULL, NULL, '[{"unit":"watt","exponent":1},{"unit":"metre","exponent":-1},{"unit":"kelvin","exponent":-1}]', 1.0, 1.0, -3.0, 0.0, -1.0, 0.0, 0.0),
  ('time', '{"en-us": "Time"}', 't', NULL, 'kinematics', 1, NULL, NULL, '[{"unit": "second", "exponent": 1}]', 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
  ('torque', '{"en-us": "Torque"}', '\tau', NULL, 'rotational_mechanics', 3, NULL, NULL, '[{"unit":"newton","exponent":1},{"unit":"metre","exponent":1}]', 1.0, 2.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('velocity', '{"en-us": "Velocity"}', 'v', NULL, 'kinematics', 2, NULL, NULL, '[{"unit":"metre","exponent":1},{"unit":"second","exponent":-1}]', 0.0, 1.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('volume', '{"en-us": "Volume"}', 'V', NULL, 'ideal_gases', 2, NULL, NULL, '[{"unit":"metre","exponent":3}]', 0.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('wavenumber', '{"en-us": "Wavenumber"}', '\tilde{\nu}', NULL, 'oscillations_and_waves', 3, NULL, NULL, '[{"unit":"metre","exponent":-1}]', 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
;

INSERT OR IGNORE INTO unit VALUES('ampere','{"en-us": "Ampere"}','A','current',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('arcminute','{"en-us": "Arcminute"}','{}^{\prime}','angle',0,NULL,0.00029088820866572158,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('arcsecond','{"en-us": "Arcsecond"}','{}^{\prime\prime}','angle',0,NULL,4.8481368110953598e-06,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('astronomical_unit','{"en-us": "Astronomical unit"}','au','length',0,NULL,149597870700.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('becquerel','{"en-us": "Becquerel"}','Bq','activity',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('bel','{"en-us": "Bel"}','B','angle',0,NULL,1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('candela','{"en-us": "Candela"}','cd','luminous_intensity',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('centimetre','{"en-us": "Centimeter", "en-uk": "Centimetre"}','cm','length',0,'CGS',0.01,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('coulomb','{"en-us": "Coulomb"}','C','charge',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('dalton','{"en-us": "Dalton"}','Da','mass',0,NULL,1.66053906892e-27,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('day','{"en-us": "Day"}','d','time',0,NULL,86400.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('decibel','{"en-us": "Decibel"}','dB','angle',0,NULL,0.1,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('degree','{"en-us": "Degree"}','{}^{\circ}','angle',0,NULL,0.017453292519943296,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('degree_celsius','{"en-us": "Degree Celsius"}','{}^{\circ}\mathrm{C}','temperature',0,NULL,1.0,NULL,273.15);
INSERT OR IGNORE INTO unit VALUES('dyne','{"en-us": "Dyne"}','dyn','force',0,'CGS',1.0e-05,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('electronvolt','{"en-us": "Electronvolt"}','eV','energy',0,NULL,1.602176634e-19,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('farad','{"en-us": "Farad"}','F','capacitance',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gram','{"en-us": "Gram"}','g','mass',0,'CGS',0.001,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gray','{"en-us": "Gray"}','Gy','absorbed_dose',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('hectare','{"en-us": "Hectare"}','ha','area',0,NULL,10000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('henry','{"en-us": "Henry"}','H','inductance',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('hertz','{"en-us": "Hertz"}','Hz','frequency',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('hour','{"en-us": "Hour"}','h','time',0,NULL,3600.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('joule','{"en-us": "Joule"}','J','energy',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('katal','{"en-us": "Katal"}','kat','catalytic_activity',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kelvin','{"en-us": "Kelvin"}','K','temperature',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kilogram','{"en-us": "Kilogram"}','kg','mass',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('litre','{"en-us": "Litre"}','L','volume',0,NULL,0.001,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('lumen','{"en-us": "Lumen"}','lm','luminous_flux',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('lux','{"en-us": "Lux"}','lx','illuminance',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('metre','{"en-us": "Meter", "en-uk": "Metre"}','m','length',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('minute','{"en-us": "Minute"}','min','time',0,NULL,60.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('mole','{"en-us": "Mole"}','mol','amount',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('neper','{"en-us": "Neper"}','Np','angle',0,NULL,1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('newton','{"en-us": "Newton"}','N','force',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('ohm','{"en-us": "Ohm"}','\Omega','resistance',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('pascal','{"en-us": "Pascal"}','Pa','pressure',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('radian','{"en-us": "Radian"}','rad','angle',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('second','{"en-us": "Second"}','s','time',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('siemens','{"en-us": "Siemens"}','S','conductance',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('sievert','{"en-us": "Sievert"}','Sv','dose_equivalent',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('steradian','{"en-us": "Steradian"}','sr','solid_angle',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('tesla','{"en-us": "Tesla"}','T','magnetic_flux_density',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('tonne','{"en-us": "Tonne"}','t','mass',0,NULL,1000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('volt','{"en-us": "Volt"}','V','electric_potential',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('watt','{"en-us": "Watt"}','W','power',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('weber','{"en-us": "Weber"}','Wb','magnetic_flux',1,'SI',1.0,NULL,0.0);

INSERT OR IGNORE INTO formula (id, name, topic, difficulty, description) VALUES
  ('acids_and_bases', '{"en-us": "Acids And Bases"}', 'acids_and_bases', 2, '{"en-us": "The pH equals the negative logarithm of the hydrogen ion concentration."}'),
  ('angular_momentum', '{"en-us": "Angular Momentum"}', 'angular_momentum', 2, '{"en-us": "Angular momentum equals the product of moment of inertia and angular velocity."}'),
  ('archimedes_principle', '{"en-us": "Archimedes'' principle"}', 'buoyancy', 3, '{"en-us": "The buoyant force on a submerged object equals the weight of the fluid displaced."}'),
  ('area', '{"en-us": "Area"}', 'area', 2, '{"en-us": "The area of a square equals the square of its side length."}'),
  ('atomic_physics', '{"en-us": "Atomic Physics"}', 'atomic_physics', 2, '{"en-us": "The energy of a photon equals Planck''s constant times its frequency."}'),
  ('atomic_structure', '{"en-us": "Atomic Structure"}', 'atomic_structure', 2, '{"en-us": "Atoms consist of protons, neutrons, and electrons arranged in a nucleus and orbiting shells."}'),
  ('bernoulli_equation', '{"en-us": "Bernoulli''s equation"}', 'bernoulli_equation', 4, '{"en-us": "For an ideal fluid, the sum of pressure, kinetic energy per volume, and potential energy per volume is constant along a streamline."}'),
  ('capacitance', '{"en-us": "Capacitance"}', 'capacitance', 2, '{"en-us": "Capacitance equals the charge stored per unit electric potential difference."}'),
  ('centripetal_acceleration', '{"en-us": "Centripetal acceleration"}', 'circular_motion', 3, '{"en-us": "The centripetal acceleration of an object moving in a circle equals the square of its velocity divided by the radius."}'),
  ('chemical_bonding', '{"en-us": "Chemical Bonding"}', 'chemical_bonding', 2, '{"en-us": "Atoms bond together by sharing or transferring electrons to achieve stable electron configurations."}'),
  ('chemical_equilibrium', '{"en-us": "Chemical Equilibrium"}', 'chemical_equilibrium', 2, '{"en-us": "The equilibrium constant equals the ratio of product concentrations to reactant concentrations."}'),
  ('chemical_kinetics', '{"en-us": "Chemical Kinetics"}', 'chemical_kinetics', 2, '{"en-us": "The rate of a chemical reaction equals the rate constant times the concentration of reactants."}'),
  ('chemical_reactions', '{"en-us": "Chemical Reactions"}', 'chemical_reactions', 2, '{"en-us": "Chemical reactions involve the rearrangement of atoms to form new substances."}'),
  ('circle_area', '{"en-us": "Area of a circle"}', 'circles', 1, '{"en-us": "The area of a circle is pi times the radius squared."}'),
  ('circle_circumference', '{"en-us": "Circumference of a circle"}', 'circles', 1, '{"en-us": "The circumference of a circle is 2 pi times the radius."}'),
  ('conservation_of_momentum', '{"en-us": "Conservation of momentum"}', 'dynamics', 2, '{"en-us": "In a closed system, total momentum before a collision equals total momentum after."}'),
  ('continuity_equation_fluid', '{"en-us": "Continuity equation for fluids"}', 'continuity_equation', 3, '{"en-us": "For an incompressible fluid, the product of cross-sectional area and velocity is constant along a streamline."}'),
  ('coordinate_geometry', '{"en-us": "Coordinate Geometry"}', 'coordinate_geometry', 2, '{"en-us": "The slope of a line equals the change in y divided by the change in x."}'),
  ('density_formula', '{"en-us": "Density"}', 'buoyancy', 1, '{"en-us": "Density equals mass divided by volume."}'),
  ('derivative_power', '{"en-us": "Power rule for derivatives"}', 'derivatives', 2, '{"en-us": "The derivative of x to the power n is n times x to the power n minus one."}'),
  ('differential_equations', '{"en-us": "Differential Equations"}', 'differential_equations', 2, '{"en-us": "A differential equation relates a function to its derivatives, describing rates of change."}'),
  ('diffraction', '{"en-us": "Diffraction"}', 'diffraction', 2, '{"en-us": "For single-slit diffraction minima, the sine of the angle equals the wavelength divided by the slit width."}'),
  ('einstein_emc2', '{"en-us": "Mass-energy equivalence"}', 'relativity', 4, '{"en-us": "Energy equals mass times the speed of light squared."}'),
  ('electric_fields', '{"en-us": "Electric Fields"}', 'electric_fields', 2, '{"en-us": "Electric field strength equals the force per unit charge."}'),
  ('electrochemistry', '{"en-us": "Electrochemistry"}', 'electrochemistry', 2, '{"en-us": "The standard cell potential equals the difference between the cathode and anode standard potentials."}'),
  ('electromagnetic_induction', '{"en-us": "Electromagnetic Induction"}', 'electromagnetic_induction', 2, '{"en-us": "The induced electromotive force equals negative the rate of change of magnetic flux."}'),
  ('electromagnetic_waves', '{"en-us": "Electromagnetic Waves"}', 'electromagnetic_waves', 2, '{"en-us": "The speed of an electromagnetic wave equals frequency times wavelength."}'),
  ('entropy', '{"en-us": "Entropy"}', 'entropy', 2, '{"en-us": "The change in entropy equals heat transferred divided by temperature."}'),
  ('escape_velocity', '{"en-us": "Escape Velocity"}', 'escape_velocity', 2, '{"en-us": "Escape velocity equals the square root of twice the gravitational constant times mass divided by radius."}'),
  ('exponents', '{"en-us": "Exponents"}', 'exponents', 2, '{"en-us": "Exponents indicate repeated multiplication of a base number by itself."}'),
  ('first_law_thermodynamics', '{"en-us": "First law of thermodynamics"}', 'first_law', 3, '{"en-us": "The change in internal energy of a system equals heat added to the system minus work done by the system."}'),
  ('first_law_thermodynamics_adiabatic', '{"en-us": "First law (adiabatic): ΔU = −W"}', 'first_law', 3, '{"en-us": "For an adiabatic process, no heat is exchanged so the change in internal energy equals negative work."}'),
  ('first_law_thermodynamics_isochoric', '{"en-us": "First law (isochoric): ΔU = Q"}', 'first_law', 3, '{"en-us": "For an isochoric process, no work is done so the change in internal energy equals the heat added."}'),
  ('friction', '{"en-us": "Friction"}', 'friction', 2, '{"en-us": "The force of friction equals the product of the coefficient of friction and the normal force."}'),
  ('heat', '{"en-us": "Heat"}', 'heat', 2, '{"en-us": "The heat transferred equals mass times specific heat capacity times the change in temperature."}'),
  ('heat_conduction', '{"en-us": "Heat conduction (Fourier''s law)"}', 'heat_transfer', 3, '{"en-us": "The rate of heat transfer through a material is proportional to its thermal conductivity, area, and temperature gradient."}'),
  ('heat_engines', '{"en-us": "Heat Engines"}', 'heat_engines', 2, '{"en-us": "The efficiency of a heat engine equals work output divided by heat input."}'),
  ('hookes_law', '{"en-us": "Hooke''s law"}', 'springs', 2, '{"en-us": "The force exerted by a spring is proportional to its displacement from equilibrium."}'),
  ('ideal_gas_law', '{"en-us": "Ideal gas law"}', 'ideal_gases', 3, '{"en-us": "The pressure of an ideal gas times its volume equals the amount of gas times the gas constant times temperature."}'),
  ('impulse', '{"en-us": "Impulse"}', 'impulse', 2, '{"en-us": "Impulse equals the product of force and the time interval over which it acts."}'),
  ('integral_power', '{"en-us": "Power rule for integrals"}', 'integrals', 2, '{"en-us": "The integral of x to the power n is x to the power n plus one divided by n plus one."}'),
  ('interference', '{"en-us": "Interference"}', 'interference', 2, '{"en-us": "For double-slit interference, the slit separation times the sine of the angle equals an integer multiple of the wavelength."}'),
  ('keplers_third_law', '{"en-us": "Kepler''s third law"}', 'orbital_motion', 4, '{"en-us": "The square of a planet''s orbital period is proportional to the cube of its semi-major axis."}'),
  ('kinetic_energy', '{"en-us": "Kinetic energy"}', 'work_and_energy', 2, '{"en-us": "The kinetic energy of a body is half its mass times the square of its velocity."}'),
  ('laws_of_sines_and_cosines', '{"en-us": "Laws Of Sines And Cosines"}', 'laws_of_sines_and_cosines', 2, '{"en-us": "The ratio of a side length to the sine of its opposite angle is constant for all sides of a triangle."}'),
  ('lens_equation', '{"en-us": "Thin lens equation"}', 'lenses', 3, '{"en-us": "The inverse of the focal length equals the sum of the inverse of the object distance and the inverse of the image distance."}'),
  ('limiting_reactants', '{"en-us": "Limiting Reactants"}', 'limiting_reactants', 2, '{"en-us": "The limiting reactant determines the maximum amount of product that can be formed in a reaction."}'),
  ('limits', '{"en-us": "Limits"}', 'limits', 2, '{"en-us": "A limit describes the value a function approaches as the input approaches a particular value."}'),
  ('logarithm_product', '{"en-us": "Logarithm of a product"}', 'logarithms', 2, '{"en-us": "The logarithm of a product equals the sum of the logarithms."}'),
  ('mirrors', '{"en-us": "Mirrors"}', 'mirrors', 2, '{"en-us": "The inverse of the focal length equals the sum of the inverses of the object and image distances."}'),
  ('molarity_formula', '{"en-us": "Molarity"}', 'solution_stoichiometry', 2, '{"en-us": "Molarity equals the number of moles of solute divided by the volume of solution in litres."}'),
  ('moles_from_mass', '{"en-us": "Moles from mass"}', 'mole_concept', 2, '{"en-us": "The number of moles equals the mass divided by the molar mass."}'),
  ('moment_of_inertia', '{"en-us": "Moment Of Inertia"}', 'moment_of_inertia', 2, '{"en-us": "The moment of inertia of a point mass equals its mass times the square of its distance from the axis."}'),
  ('momentum_formula', '{"en-us": "Linear momentum"}', 'linear_momentum', 1, '{"en-us": "The linear momentum of an object is its mass times its velocity."}'),
  ('newton_second_law_of_motion', '{"en-us": "Newton''s second law of motion"}', 'dynamics', 2, '{"en-us": "The net force on a body is equal to its mass times its acceleration."}'),
  ('newtons_law_of_gravitation', '{"en-us": "Newton''s law of universal gravitation"}', 'newtonian_gravity', 3, '{"en-us": "Every particle attracts every other particle with a force proportional to the product of their masses and inversely proportional to the square of the distance."}'),
  ('ohms_law', '{"en-us": "Ohm''s law"}', 'circuits', 2, '{"en-us": "The current through a conductor is directly proportional to the voltage across it."}'),
  ('parallel_resistance', '{"en-us": "Parallel resistance"}', 'circuits', 3, '{"en-us": "The reciprocal of total resistance in parallel equals the sum of the reciprocals of individual resistances."}'),
  ('particle_physics', '{"en-us": "Particle Physics"}', 'particle_physics', 2, '{"en-us": "The square of total relativistic energy equals the square of momentum times c squared plus the square of rest energy."}'),
  ('pascals_principle', '{"en-us": "Pascal''s principle"}', 'pascals_law', 3, '{"en-us": "A change in pressure applied to an enclosed fluid is transmitted undiminished throughout the fluid."}'),
  ('percent_yield', '{"en-us": "Percent Yield"}', 'percent_yield', 2, '{"en-us": "Percent yield compares the actual product yield to the theoretical maximum yield."}'),
  ('period_pendulum', '{"en-us": "Simple pendulum period"}', 'harmonic_motion', 3, '{"en-us": "The period of a simple pendulum is proportional to the square root of its length over gravitational acceleration."}'),
  ('periodic_table', '{"en-us": "Periodic Table"}', 'periodic_table', 2, '{"en-us": "The periodic table organises elements by atomic number, electron configuration, and chemical properties."}'),
  ('photoelectric_effect', '{"en-us": "Photoelectric effect"}', 'quantum_mechanics', 4, '{"en-us": "The maximum kinetic energy of ejected electrons equals the photon energy minus the work function."}'),
  ('plane_geometry', '{"en-us": "Plane Geometry"}', 'plane_geometry', 2, '{"en-us": "The area of a triangle equals half the product of its base and height."}'),
  ('polarization', '{"en-us": "Polarization"}', 'polarization', 2, '{"en-us": "At Brewster''s angle, the tangent of the angle equals the ratio of transmitted to incident refractive indices."}'),
  ('polygons', '{"en-us": "Polygons"}', 'polygons', 2, '{"en-us": "The area of a regular polygon equals half the product of its perimeter and apothem."}'),
  ('polynomials', '{"en-us": "Polynomials"}', 'polynomials', 2, '{"en-us": "A polynomial is an expression consisting of variables and coefficients combined using addition and multiplication."}'),
  ('potential_energy', '{"en-us": "Potential Energy"}', 'potential_energy', 2, '{"en-us": "Gravitational potential energy equals the product of mass, gravitational acceleration, and height."}'),
  ('power_formula', '{"en-us": "Power"}', 'power', 2, '{"en-us": "Power equals work divided by time."}'),
  ('pressure', '{"en-us": "Pressure"}', 'pressure', 2, '{"en-us": "Pressure equals force divided by area."}'),
  ('projectile_motion', '{"en-us": "Projectile Motion"}', 'projectile_motion', 2, '{"en-us": "The horizontal range of a projectile equals the square of its initial velocity divided by gravitational acceleration."}'),
  ('pythagorean_theorem', '{"en-us": "Pythagorean theorem"}', 'triangles', 1, '{"en-us": "In a right triangle, the square of the hypotenuse equals the sum of the squares of the other two sides."}'),
  ('quadratic_formula', '{"en-us": "Quadratic formula"}', 'equations', 2, '{"en-us": "The solutions to a quadratic equation are given by the quadratic formula."}'),
  ('radioactive_decay', '{"en-us": "Radioactive decay law"}', 'nuclear_physics', 4, '{"en-us": "The number of radioactive nuclei decreases exponentially with time."}'),
  ('reflection', '{"en-us": "Reflection"}', 'reflection', 2, '{"en-us": "The angle of incidence equals the angle of reflection."}'),
  ('reynolds_number', '{"en-us": "Reynolds Number"}', 'reynolds_number', 2, '{"en-us": "The Reynolds number equals density times velocity times characteristic length divided by dynamic viscosity."}'),
  ('rotational_energy', '{"en-us": "Rotational Energy"}', 'rotational_energy', 2, '{"en-us": "Rotational kinetic energy equals half the moment of inertia times angular velocity squared."}'),
  ('second_law_thermodynamics_clausius', '{"en-us": "Second law of thermodynamics (Clausius statement)"}', 'second_law', 4, '{"en-us": "Heat cannot spontaneously flow from a colder body to a hotter body."}'),
  ('simple_harmonic_motion', '{"en-us": "Simple harmonic motion position"}', 'harmonic_motion', 3, '{"en-us": "The position of an object in simple harmonic motion varies sinusoidally with time."}'),
  ('snells_law', '{"en-us": "Snell''s law"}', 'refraction', 3, '{"en-us": "The ratio of sines of the angles of incidence and refraction equals the inverse ratio of refractive indices."}'),
  ('surface_tension', '{"en-us": "Surface Tension"}', 'surface_tension', 2, '{"en-us": "Surface tension equals force per unit length acting along a liquid surface."}'),
  ('suvat_v2', '{"en-us": "Uniform acceleration equation"}', 'kinematics', 3, '{"en-us": "Final velocity squared equals initial velocity squared plus twice acceleration times displacement."}'),
  ('trig_sin2_cos2', '{"en-us": "Pythagorean trigonometric identity"}', 'trigonometric_identities', 1, '{"en-us": "The square of the sine plus the square of the cosine equals one."}'),
  ('van_der_waals', '{"en-us": "Van der Waals equation of state"}', 'ideal_gases', 5, '{"en-us": "A more accurate equation of state for real gases that accounts for intermolecular forces and finite molecular size."}'),
  ('wave_equation', '{"en-us": "Universal wave equation"}', 'mechanical_waves', 2, '{"en-us": "The speed of a wave equals its frequency times its wavelength."}'),
  ('wave_interference', '{"en-us": "Wave Interference"}', 'wave_interference', 2, '{"en-us": "For constructive interference, the path difference equals an integer multiple of the wavelength."}'),
  ('work_formula', '{"en-us": "Work done by a force"}', 'work', 2, '{"en-us": "The work done by a force equals the force times the displacement times the cosine of the angle between them."}'),
  ('dimensions', '{"en-us": "Dimensions"}', NULL, NULL, NULL)
;

INSERT OR IGNORE INTO formula_item VALUES('acids_and_bases',1,0,0,NULL,NULL,1.0,'concentration',1.0,NULL,'[\mathrm{H}^{+}]','{"en-us": "Hydrogen ion [Concentration]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('angular_momentum',1,0,0,NULL,NULL,1.0,'moment_of_inertia',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('angular_momentum',1,0,1,NULL,NULL,1.0,'angular_velocity',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('angular_momentum',1,1,0,NULL,NULL,1.0,'angular_momentum',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('archimedes_principle',1,0,0,NULL,NULL,1.0,'density',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('archimedes_principle',1,0,1,NULL,NULL,1.0,'gravitational_constant',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('archimedes_principle',1,0,2,NULL,NULL,1.0,'volume',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('archimedes_principle',1,1,0,NULL,NULL,1.0,'force',-1.0,NULL,'{"en-us": "F_b"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('area',1,0,0,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "s"}','{"en-us": "[Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('area',1,1,0,NULL,NULL,1.0,'area',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('atomic_physics',1,0,0,NULL,NULL,1.0,'frequency',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('atomic_physics',1,1,0,NULL,NULL,1.0,'energy',-1.0,NULL,NULL,NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('atomic_structure',1,0,0,NULL,NULL,1.0,'charge',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('capacitance',1,0,0,NULL,NULL,1.0,'charge',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('capacitance',1,0,1,NULL,NULL,1.0,'electric_potential',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('capacitance',1,1,0,NULL,NULL,1.0,'capacitance',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('centripetal_acceleration',1,0,0,NULL,NULL,1.0,'velocity',2.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('centripetal_acceleration',1,0,1,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "r"}','{"en-us": "[Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('centripetal_acceleration',1,1,0,NULL,NULL,1.0,'acceleration',-1.0,'{"en-us": "c"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_bonding',1,0,0,NULL,NULL,1.0,'charge',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_equilibrium',1,0,0,NULL,NULL,1.0,'concentration',1.0,NULL,'[\mathrm{C}]','{"en-us": "Product [Concentration]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_equilibrium',1,0,1,NULL,NULL,1.0,'concentration',-1.0,NULL,'[\mathrm{A}]','{"en-us": "Reactant [Concentration]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_kinetics',1,0,0,NULL,NULL,1.0,'concentration',1.0,NULL,'[\mathrm{A}]',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_kinetics',1,0,1,NULL,NULL,1.0,'rate_constant',1.0,NULL,NULL,'{"en-us": "[Rate constant]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_reactions',1,0,0,NULL,NULL,1.0,'mass',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_area',1,0,0,NULL,NULL,1.0,NULL,1.0,NULL,'{"en-us": "r"}','{"en-us": "[Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_area',1,0,1,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "r"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_area',1,1,0,NULL,NULL,1.0,'area',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_circumference',1,0,0,2.0,NULL,1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_circumference',1,0,1,NULL,NULL,1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_circumference',1,0,2,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "r"}','{"en-us": "[Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_circumference',1,1,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "C"}','{"en-us": "Circumference [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',1,1,0,NULL,NULL,1.0,'mass',-1.0,'{"en-us": "1"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',1,1,1,NULL,NULL,1.0,'velocity',-1.0,'{"en-us": "1"}','{"en-us": "u"}','{"en-us": "Initial [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',2,1,0,NULL,NULL,1.0,'mass',-1.0,'{"en-us": "2"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',2,1,1,NULL,NULL,1.0,'velocity',-1.0,'{"en-us": "2"}','{"en-us": "u"}','{"en-us": "Initial [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',3,0,0,NULL,NULL,1.0,'mass',1.0,'{"en-us": "1"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',3,0,1,NULL,NULL,1.0,'velocity',1.0,'{"en-us": "1"}',NULL,'{"en-us": "Final [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',4,0,0,NULL,NULL,1.0,'mass',1.0,'{"en-us": "2"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',4,0,1,NULL,NULL,1.0,'velocity',1.0,'{"en-us": "2"}',NULL,'{"en-us": "Final [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('coordinate_geometry',1,0,0,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "y"}',NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('coordinate_geometry',1,0,1,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "x"}',NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('density_formula',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('density_formula',1,0,1,NULL,NULL,1.0,'volume',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('density_formula',1,1,0,NULL,NULL,1.0,'density',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('differential_equations',1,0,0,NULL,NULL,1.0,'length',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('diffraction',1,0,0,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "\\lambda"}','{"en-us": "Wavelength [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('diffraction',1,0,1,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "d"}','{"en-us": "Slit separation [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('diffraction',1,1,0,NULL,NULL,1.0,'angle',1.0,NULL,NULL,NULL,'\sin',NULL);
INSERT OR IGNORE INTO formula_item VALUES('einstein_emc2',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('einstein_emc2',1,0,1,NULL,NULL,2.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('einstein_emc2',1,1,0,NULL,NULL,1.0,'energy',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electric_fields',1,0,0,NULL,NULL,1.0,'force',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electric_fields',1,0,1,NULL,NULL,1.0,'charge',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electric_fields',1,1,0,NULL,NULL,1.0,'electric_field_strength',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electrochemistry',1,0,0,NULL,NULL,1.0,'electric_potential',1.0,NULL,'E^\circ_\mathrm{cathode}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electrochemistry',1,1,0,NULL,NULL,1.0,'electric_potential',-1.0,NULL,'{"en-us": "E_\\mathrm{cell}"}','{"en-us": "Cell [Electric potential]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electrochemistry',2,0,0,-1.0,NULL,1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electrochemistry',2,0,1,NULL,NULL,1.0,'electric_potential',1.0,NULL,'E^\circ_\mathrm{anode}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_induction',1,0,0,NULL,NULL,1.0,'magnetic_flux',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_induction',1,0,1,NULL,NULL,1.0,'time',-1.0,NULL,NULL,NULL,'\mathrm{d}',NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_induction',1,1,0,-1.0,NULL,1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_waves',1,0,0,NULL,NULL,1.0,'frequency',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_waves',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "\\lambda"}','{"en-us": "Wavelength [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_waves',1,1,0,NULL,NULL,1.0,'velocity',-1.0,NULL,'{"en-us": "c"}','{"en-us": "Wave [Velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('entropy',1,0,0,NULL,NULL,1.0,'energy',1.0,NULL,'{"en-us": "Q"}','{"en-us": "[Energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('entropy',1,0,1,NULL,NULL,1.0,'temperature',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('entropy',1,1,0,NULL,NULL,1.0,'entropy',-1.0,NULL,NULL,NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('escape_velocity',1,0,0,2.0,NULL,1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('escape_velocity',1,0,1,NULL,NULL,1.0,'gravitational_constant',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('escape_velocity',1,0,2,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('escape_velocity',1,0,3,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "r"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('escape_velocity',1,1,0,NULL,NULL,1.0,'velocity',-1.0,NULL,'{"en-us": "v_\\mathrm{esc}"}','{"en-us": "Escape [Velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('exponents',1,0,0,NULL,NULL,1.0,'length',0.0,NULL,'{"en-us": "x"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics',1,1,0,NULL,NULL,NULL,'energy',-1.0,NULL,'{"en-us": "U"}','{"en-us": "Internal [Energy]"}','\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics',2,0,0,NULL,NULL,NULL,'energy',1.0,NULL,'{"en-us": "Q"}','{"en-us": "[Energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics',3,0,0,-1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics',3,0,1,NULL,NULL,NULL,'energy',1.0,NULL,'{"en-us": "W"}','{"en-us": "[Energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics_adiabatic',1,1,0,NULL,NULL,NULL,'energy',-1.0,NULL,'{"en-us": "U"}','{"en-us": "Internal [Energy]"}','\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics_adiabatic',2,0,0,-1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics_adiabatic',2,0,1,NULL,NULL,NULL,'energy',1.0,NULL,'{"en-us": "W"}','{"en-us": "[Energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics_isochoric',1,1,0,NULL,NULL,1.0,'energy',-1.0,NULL,'{"en-us": "U"}','{"en-us": "Internal [Energy]"}','\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics_isochoric',2,0,0,NULL,NULL,1.0,'energy',1.0,NULL,'{"en-us": "Q"}','{"en-us": "[Energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('friction',1,0,0,NULL,NULL,1.0,'force',1.0,NULL,'{"en-us": "N"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('friction',1,1,0,NULL,NULL,1.0,'force',-1.0,NULL,'F_\mathrm{f}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat',1,0,1,NULL,NULL,1.0,'specific_heat_capacity',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat',1,0,2,NULL,NULL,1.0,'temperature',1.0,NULL,NULL,NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat',1,1,0,NULL,NULL,1.0,'energy',-1.0,NULL,'{"en-us": "Q"}','{"en-us": "[Energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_conduction',1,0,0,NULL,NULL,1.0,'thermal_conductivity',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_conduction',1,0,1,NULL,NULL,1.0,'area',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_conduction',1,0,2,NULL,NULL,1.0,'temperature',1.0,NULL,NULL,NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_conduction',1,0,3,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "x"}',NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_conduction',1,1,0,-1.0,NULL,1.0,'power',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_engines',1,0,0,NULL,NULL,1.0,'energy',1.0,NULL,'{"en-us": "W"}','{"en-us": "[Energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_engines',1,0,1,NULL,NULL,1.0,'energy',-1.0,NULL,'{"en-us": "Q"}','{"en-us": "[Energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_engines',1,1,0,NULL,NULL,1.0,'heat_engine_efficiency',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('hookes_law',1,0,0,-1.0,NULL,1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('hookes_law',1,0,1,NULL,NULL,1.0,'spring_constant',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('hookes_law',1,0,2,NULL,NULL,1.0,'length',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('hookes_law',1,1,0,NULL,NULL,1.0,'force',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('ideal_gas_law',1,1,0,NULL,NULL,1.0,'pressure',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('ideal_gas_law',1,1,1,NULL,NULL,1.0,'volume',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('ideal_gas_law',2,0,0,NULL,NULL,1.0,'amount',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('ideal_gas_law',2,0,1,NULL,NULL,1.0,'gas_constant',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('ideal_gas_law',2,0,2,NULL,NULL,1.0,'temperature',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('impulse',1,0,0,NULL,NULL,1.0,'force',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('impulse',1,0,1,NULL,NULL,1.0,'time',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('impulse',1,1,0,NULL,NULL,1.0,'momentum',-1.0,NULL,'{"en-us": "J"}','{"en-us": "Impulse [Momentum]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('interference',1,0,0,NULL,NULL,1.0,'angle',1.0,NULL,NULL,NULL,'\sin',NULL);
INSERT OR IGNORE INTO formula_item VALUES('interference',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "\\lambda"}','{"en-us": "Wavelength [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('interference',1,1,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "d"}','{"en-us": "Slit separation [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('keplers_third_law',1,1,0,NULL,NULL,NULL,'time',-2.0,NULL,'{"en-us": "T"}','{"en-us": "Orbital [Time]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('keplers_third_law',2,0,0,4.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('keplers_third_law',2,0,1,NULL,'\\pi',2.0,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('keplers_third_law',2,0,2,NULL,NULL,NULL,'gravitational_constant',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('keplers_third_law',2,0,3,NULL,NULL,NULL,'mass',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('keplers_third_law',2,0,4,NULL,NULL,NULL,'length',3.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('kinetic_energy',1,0,0,2.0,NULL,-1.0,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('kinetic_energy',1,0,1,NULL,NULL,NULL,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('kinetic_energy',1,0,2,NULL,NULL,NULL,'velocity',2.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('kinetic_energy',1,1,0,NULL,NULL,NULL,'energy',-1.0,'{"en-us": "k"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('laws_of_sines_and_cosines',1,0,0,NULL,NULL,1.0,'angle',-1.0,NULL,'{"en-us": "A"}',NULL,'\sin',NULL);
INSERT OR IGNORE INTO formula_item VALUES('laws_of_sines_and_cosines',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "b"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('laws_of_sines_and_cosines',1,0,2,NULL,NULL,1.0,'angle',-1.0,NULL,'{"en-us": "B"}',NULL,'\sin',NULL);
INSERT OR IGNORE INTO formula_item VALUES('laws_of_sines_and_cosines',1,1,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "a"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('limiting_reactants',1,0,0,NULL,NULL,1.0,'amount',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('limits',1,0,0,NULL,NULL,1.0,'length',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('mirrors',1,0,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "u"}','{"en-us": "Object distance [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('mirrors',1,0,1,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "v"}','{"en-us": "Image distance [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('mirrors',1,1,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "f"}','{"en-us": "Focal length [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('molarity_formula',1,0,0,NULL,NULL,1.0,'amount',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('molarity_formula',1,0,1,NULL,NULL,1.0,'volume',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('molarity_formula',1,1,0,NULL,NULL,1.0,'concentration',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('moles_from_mass',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('moles_from_mass',1,0,1,NULL,NULL,1.0,'molar_mass',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('moles_from_mass',1,1,0,NULL,NULL,1.0,'amount',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('moment_of_inertia',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('moment_of_inertia',1,0,1,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "r"}','{"en-us": "[Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('moment_of_inertia',1,1,0,NULL,NULL,1.0,'moment_of_inertia',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('momentum_formula',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('momentum_formula',1,0,1,NULL,NULL,1.0,'velocity',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('momentum_formula',1,1,0,NULL,NULL,1.0,'momentum',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('newton_second_law_of_motion',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('newton_second_law_of_motion',1,0,1,NULL,NULL,1.0,'acceleration',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('newton_second_law_of_motion',1,1,0,NULL,NULL,1.0,'force',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('newtons_law_of_gravitation',1,0,0,NULL,NULL,1.0,'gravitational_constant',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('newtons_law_of_gravitation',1,0,1,NULL,NULL,1.0,'mass',1.0,'{"en-us": "1"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('newtons_law_of_gravitation',1,0,2,NULL,NULL,1.0,'mass',1.0,'{"en-us": "2"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('newtons_law_of_gravitation',1,0,3,NULL,NULL,1.0,'length',-2.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('newtons_law_of_gravitation',1,1,0,NULL,NULL,1.0,'force',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('ohms_law',1,0,0,NULL,NULL,1.0,'current',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('ohms_law',1,0,1,NULL,NULL,1.0,'resistance',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('ohms_law',1,1,0,NULL,NULL,1.0,'electric_potential',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('parallel_resistance',1,1,0,NULL,NULL,1.0,'resistance',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('parallel_resistance',2,0,0,NULL,NULL,1.0,'resistance',-1.0,'{"en-us": "1"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('parallel_resistance',3,0,0,NULL,NULL,1.0,'resistance',-1.0,'{"en-us": "2"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('particle_physics',1,1,0,NULL,NULL,1.0,'energy',-2.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('particle_physics',2,0,0,NULL,NULL,1.0,'momentum',2.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('particle_physics',3,0,0,NULL,NULL,1.0,'mass',2.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('particle_physics',3,0,1,NULL,NULL,2.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pascals_principle',1,0,0,NULL,NULL,1.0,'density',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pascals_principle',1,0,1,NULL,NULL,1.0,'gravitational_constant',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pascals_principle',1,0,2,NULL,NULL,1.0,'length',1.0,NULL,NULL,NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('pascals_principle',1,1,0,-1.0,NULL,1.0,'pressure',1.0,NULL,NULL,NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('percent_yield',1,0,0,NULL,NULL,1.0,'amount',1.0,NULL,NULL,'{"en-us": "Actual [Amount]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('percent_yield',1,0,1,NULL,NULL,1.0,'amount',-1.0,NULL,NULL,'{"en-us": "Theoretical [Amount]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('periodic_table',1,0,0,NULL,NULL,1.0,'amount',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('plane_geometry',1,0,0,2.0,NULL,-1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('plane_geometry',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "b"}','{"en-us": "[Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('plane_geometry',1,0,2,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "h"}','{"en-us": "[Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('plane_geometry',1,1,0,NULL,NULL,1.0,'area',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polarization',1,0,0,NULL,NULL,1.0,'refractive_index',1.0,NULL,'{"en-us": "n_2"}','{"en-us": "Transmitted [Refractive index]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polarization',1,0,1,NULL,NULL,1.0,'refractive_index',-1.0,NULL,'{"en-us": "n_1"}','{"en-us": "Incident [Refractive index]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polarization',1,1,0,NULL,NULL,1.0,'angle',1.0,NULL,'\theta_\mathrm{B}','{"en-us": "Brewster [Angle]"}','\tan',NULL);
INSERT OR IGNORE INTO formula_item VALUES('polygons',1,0,0,2.0,NULL,-1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polygons',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "s"}','{"en-us": "[Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polygons',1,0,2,NULL,NULL,1.0,'angle',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polygons',1,1,0,NULL,NULL,1.0,'area',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polynomials',2,0,0,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "x"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polynomials',3,0,0,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "x"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polynomials',4,0,0,NULL,NULL,1.0,'length',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('potential_energy',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('potential_energy',1,0,1,NULL,NULL,1.0,'acceleration',1.0,NULL,'{"en-us": "g"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('potential_energy',1,0,2,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "h"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('potential_energy',1,1,0,NULL,NULL,1.0,'energy',-1.0,'{"en-us": "p"}',NULL,'{"en-us": "Potential [Energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('power_formula',1,0,0,NULL,NULL,1.0,'energy',1.0,NULL,'{"en-us": "W"}','{"en-us": "[Energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('power_formula',1,0,1,NULL,NULL,1.0,'time',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('power_formula',1,1,0,NULL,NULL,1.0,'power',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pressure',1,0,0,NULL,NULL,1.0,'force',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pressure',1,0,1,NULL,NULL,1.0,'area',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pressure',1,1,0,NULL,NULL,1.0,'pressure',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('projectile_motion',1,0,0,NULL,NULL,1.0,'velocity',2.0,NULL,NULL,'{"en-us": "Initial [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('projectile_motion',1,0,1,NULL,NULL,1.0,'acceleration',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('projectile_motion',1,1,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "R"}','{"en-us": "Range [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pythagorean_theorem',1,1,0,NULL,NULL,1.0,'length',-2.0,NULL,'{"en-us": "c"}','{"en-us": "Hypotenuse [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pythagorean_theorem',2,0,0,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "a"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pythagorean_theorem',3,0,0,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "b"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('reflection',1,0,0,NULL,NULL,1.0,'angle',1.0,NULL,'\theta_\mathrm{r}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('reflection',1,1,0,NULL,NULL,1.0,'angle',-1.0,NULL,'\theta_\mathrm{i}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('reynolds_number',1,0,0,NULL,NULL,1.0,'density',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('reynolds_number',1,0,1,NULL,NULL,1.0,'velocity',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('reynolds_number',1,0,2,NULL,NULL,1.0,'length',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('reynolds_number',1,0,3,NULL,NULL,1.0,'dynamic_viscosity',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('reynolds_number',1,1,0,NULL,NULL,1.0,'reynolds_number',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('rotational_energy',1,0,0,2.0,NULL,-1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('rotational_energy',1,0,1,NULL,NULL,1.0,'moment_of_inertia',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('rotational_energy',1,0,2,NULL,NULL,1.0,'angular_velocity',2.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('rotational_energy',1,1,0,NULL,NULL,1.0,'energy',-1.0,'{"en-us": "rot"}',NULL,'{"en-us": "Rotational [Energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('snells_law',1,1,0,NULL,NULL,1.0,'refractive_index',-1.0,'{"en-us": "1"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('snells_law',1,1,1,NULL,NULL,1.0,'angle',-1.0,'{"en-us": "i"}',NULL,NULL,'\sin',NULL);
INSERT OR IGNORE INTO formula_item VALUES('snells_law',2,0,0,NULL,NULL,1.0,'refractive_index',1.0,'{"en-us": "2"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('snells_law',2,0,1,NULL,NULL,1.0,'angle',1.0,'{"en-us": "r"}',NULL,NULL,'\sin',NULL);
INSERT OR IGNORE INTO formula_item VALUES('surface_tension',1,0,0,NULL,NULL,1.0,'force',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('surface_tension',1,0,1,NULL,NULL,1.0,'length',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('surface_tension',1,1,0,NULL,NULL,1.0,'surface_tension',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('suvat_v2',1,1,0,NULL,NULL,1.0,'velocity',-2.0,NULL,NULL,'{"en-us": "Final [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('suvat_v2',2,0,0,NULL,NULL,1.0,'velocity',2.0,NULL,'{"en-us": "u"}','{"en-us": "Initial [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('suvat_v2',3,0,0,2.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('suvat_v2',3,0,1,NULL,NULL,1.0,'acceleration',1.0,NULL,NULL,'{"en-us": "[Acceleration]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('suvat_v2',3,0,2,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "s"}','{"en-us": "Displacement [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('wave_equation',1,0,0,NULL,NULL,1.0,'frequency',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('wave_equation',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "\\lambda"}','{"en-us": "Wavelength [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('wave_equation',1,1,0,NULL,NULL,1.0,'velocity',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('wave_interference',1,0,0,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "\\lambda"}','{"en-us": "Wavelength [Length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('wave_interference',1,1,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "\\Delta x"}','{"en-us": "Path difference [Length]"}','\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('work_formula',1,0,0,NULL,NULL,1.0,'force',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('work_formula',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('work_formula',1,0,2,NULL,NULL,1.0,'angle',1.0,NULL,NULL,NULL,NULL,'{}');
INSERT OR IGNORE INTO formula_item VALUES('work_formula',1,1,0,NULL,NULL,1.0,'energy',-1.0,NULL,'{"en-us": "W"}','{"en-us": "[Energy]"}',NULL,NULL);

-- Dimension definitions (base SI quantities identified via formula_item)
INSERT OR IGNORE INTO formula_item VALUES('dimensions',0,0,1,NULL,NULL,1.0,'mass',1.0,NULL,'M',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('dimensions',0,0,2,NULL,NULL,1.0,'length',1.0,NULL,'L',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('dimensions',0,0,3,NULL,NULL,1.0,'time',1.0,NULL,'T',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('dimensions',0,0,4,NULL,NULL,1.0,'current',1.0,NULL,'I',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('dimensions',0,0,5,NULL,NULL,1.0,'temperature',1.0,NULL,'Θ',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('dimensions',0,0,6,NULL,NULL,1.0,'amount',1.0,NULL,'N',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('dimensions',0,0,7,NULL,NULL,1.0,'luminous_intensity',1.0,NULL,'J',NULL,NULL,NULL);

INSERT OR IGNORE INTO formula_relation VALUES('first_law_thermodynamics','first_law_thermodynamics_adiabatic','condition','{"en-us": "Adiabatic process (Q = 0)"}');
INSERT OR IGNORE INTO formula_relation VALUES('first_law_thermodynamics','first_law_thermodynamics_isochoric','condition','{"en-us": "Isochoric process (W = 0)"}');
INSERT OR IGNORE INTO formula_relation VALUES('first_law_thermodynamics','kinetic_energy','derivation','{"en-us": "Changes in internal energy via heat and work encompass kinetic energy as a component of total energy."}');
INSERT OR IGNORE INTO formula_relation VALUES('ideal_gas_law','van_der_waals','assumption','{"en-us": "Gas particles are treated as non-interacting point masses with no intermolecular forces."}');
INSERT OR IGNORE INTO formula_relation VALUES('ideal_gas_law','keplers_third_law','assumption','{"en-us": "Planetary orbits are treated as two-body systems with negligible mutual interactions."}');
INSERT OR IGNORE INTO formula_relation VALUES('kinetic_energy','newton_second_law_of_motion','derivation','{"en-us": "Kinetic energy is the work required to accelerate a mass from rest to a given velocity, as described by Newton''s second law."}');

-- ============================================================
-- Data fixes / overrides
-- ============================================================

UPDATE formula_item SET quantity_id='energy', symbol_overwrite='{"en-us": "Q"}' WHERE formula_id='entropy' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET quantity_id='energy', symbol_overwrite='{"en-us": "Q"}' WHERE formula_id='heat' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET quantity_id='energy', symbol_overwrite='{"en-us": "Q"}', label=NULL WHERE formula_id='heat_engines' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET quantity_id='energy', symbol_overwrite='{"en-us": "W"}' WHERE formula_id='heat_engines' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET quantity_id='energy', symbol_overwrite='{"en-us": "W"}' WHERE formula_id='work_formula' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET quantity_id='energy', symbol_overwrite='{"en-us": "W"}' WHERE formula_id='power_formula' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET quantity_id='power' WHERE formula_id='power_formula' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET quantity_id='velocity', symbol_overwrite='{"en-us": "v_\\mathrm{esc}"}', quantity_name_overwrite='{"en-us": "Escape [velocity]"}' WHERE formula_id='escape_velocity' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\lambda"}', quantity_name_overwrite='{"en-us": "Wavelength [length]"}' WHERE formula_id='diffraction' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\lambda"}', quantity_name_overwrite='{"en-us": "Wavelength [length]"}' WHERE formula_id='electromagnetic_waves' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\lambda"}', quantity_name_overwrite='{"en-us": "Wavelength [length]"}' WHERE formula_id='interference' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\lambda"}', quantity_name_overwrite='{"en-us": "Wavelength [length]"}' WHERE formula_id='wave_equation' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\lambda"}', quantity_name_overwrite='{"en-us": "Wavelength [length]"}' WHERE formula_id='wave_interference' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\Delta x"}', quantity_name_overwrite='{"en-us": "Path difference [length]"}' WHERE formula_id='wave_interference' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET quantity_id='electric_potential', symbol_overwrite='{"en-us": "E_\\mathrm{cell}"}', quantity_name_overwrite='{"en-us": "Cell [electric potential]"}' WHERE formula_id='electrochemistry' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET quantity_id='momentum', symbol_overwrite='{"en-us": "J"}', quantity_name_overwrite='{"en-us": "Impulse [momentum]"}' WHERE formula_id='impulse' AND term=1 AND is_primary=1 AND sort_order=0;

-- Pythagorean theorem: c² = a² + b²
UPDATE formula_item SET symbol_overwrite='{"en-us": "c"}', quantity_name_overwrite='{"en-us": "Hypotenuse [length]"}' WHERE formula_id='pythagorean_theorem' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "a"}' WHERE formula_id='pythagorean_theorem' AND term=2 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "b"}', label=NULL WHERE formula_id='pythagorean_theorem' AND term=3 AND is_primary=0 AND sort_order=0;

-- SUVAT: v² = u² + 2as
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Final [velocity]"}' WHERE formula_id='suvat_v2' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "u"}', label=NULL, quantity_name_overwrite='{"en-us": "Initial [velocity]"}' WHERE formula_id='suvat_v2' AND term=2 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "s"}', quantity_name_overwrite='{"en-us": "Displacement [length]"}' WHERE formula_id='suvat_v2' AND term=3 AND is_primary=0 AND sort_order=2;

-- Conservation of momentum: m₁u₁ + m₂u₂ = m₁v₁ + m₂v₂
UPDATE formula_item SET symbol_overwrite='{"en-us": "u"}', label='{"en-us": "1"}', quantity_name_overwrite='{"en-us": "Initial [velocity]"}' WHERE formula_id='conservation_of_momentum' AND term=1 AND is_primary=1 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "u"}', label='{"en-us": "2"}', quantity_name_overwrite='{"en-us": "Initial [velocity]"}' WHERE formula_id='conservation_of_momentum' AND term=2 AND is_primary=1 AND sort_order=1;
UPDATE formula_item SET label='{"en-us": "1"}', quantity_name_overwrite='{"en-us": "Final [velocity]"}' WHERE formula_id='conservation_of_momentum' AND term=3 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET label='{"en-us": "2"}', quantity_name_overwrite='{"en-us": "Final [velocity]"}' WHERE formula_id='conservation_of_momentum' AND term=4 AND is_primary=0 AND sort_order=1;

-- Other formula_item refinements (labels → symbol_overwrite/quantity_name_overwrite)
UPDATE formula_item SET symbol_overwrite='{"en-us": "s"}', label=NULL WHERE formula_id='area' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "r"}' WHERE formula_id='circle_area' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "C"}', quantity_name_overwrite='{"en-us": "Circumference [length]"}' WHERE formula_id='circle_circumference' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "r"}' WHERE formula_id='circle_circumference' AND term=1 AND is_primary=0 AND sort_order=2;
UPDATE formula_item SET symbol_overwrite='{"en-us": "r"}' WHERE formula_id='moment_of_inertia' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "s"}', label=NULL WHERE formula_id='polygons' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "b"}', label=NULL WHERE formula_id='plane_geometry' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "h"}', label=NULL WHERE formula_id='plane_geometry' AND term=1 AND is_primary=0 AND sort_order=2;
UPDATE formula_item SET symbol_overwrite='{"en-us": "d"}', label=NULL, quantity_name_overwrite='{"en-us": "Slit separation [length]"}' WHERE formula_id='interference' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "d"}', label=NULL, quantity_name_overwrite='{"en-us": "Slit separation [length]"}' WHERE formula_id='diffraction' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "f"}', label=NULL, quantity_name_overwrite='{"en-us": "Focal length [length]"}' WHERE formula_id='mirrors' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "u"}', label=NULL, quantity_name_overwrite='{"en-us": "Object distance [length]"}' WHERE formula_id='mirrors' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "v"}', label=NULL, quantity_name_overwrite='{"en-us": "Image distance [length]"}' WHERE formula_id='mirrors' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Brewster [angle]"}' WHERE formula_id='polarization' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Transmitted [refractive index]"}' WHERE formula_id='polarization' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Incident [refractive index]"}' WHERE formula_id='polarization' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "R"}', label=NULL, quantity_name_overwrite='{"en-us": "Range [length]"}' WHERE formula_id='projectile_motion' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Initial [velocity]"}' WHERE formula_id='projectile_motion' AND term=1 AND is_primary=0 AND sort_order=0;

-- Clear English-word labels where qno/symbol already describes the quantity
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Wave [velocity]"}' WHERE formula_id='electromagnetic_waves' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Product [concentration]"}' WHERE formula_id='chemical_equilibrium' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Reactant [concentration]"}' WHERE formula_id='chemical_equilibrium' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Actual [amount]"}' WHERE formula_id='percent_yield' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Theoretical [amount]"}' WHERE formula_id='percent_yield' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET quantity_name_overwrite='{"en-us": "Hydrogen ion [concentration]"}' WHERE formula_id='acids_and_bases' AND term=1 AND is_primary=0 AND sort_order=0;

-- Re-seed safety: clear no-op symbol_overwrites that match quantity symbol
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='atomic_physics' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='entropy' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='entropy' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='heat' AND term=1 AND is_primary=0 AND sort_order=2;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='heat_conduction' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='heat_conduction' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='heat_conduction' AND term=1 AND is_primary=0 AND sort_order=2;
-- Re-seed safety: add markers to qno values that were updated in INSERTs above
UPDATE formula_item SET quantity_name_overwrite='{"en-us": "Potential [energy]"}' WHERE formula_id='potential_energy' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET quantity_name_overwrite='{"en-us": "Rotational [energy]"}' WHERE formula_id='rotational_energy' AND term=1 AND is_primary=1 AND sort_order=0;

