-- Consolidated seed data
INSERT OR IGNORE INTO quantity (id, name, symbol, symbol_overwrite, topic, difficulty, description, links, default_unit, dim_M, dim_L, dim_T, dim_I, dim_Θ, dim_N, dim_J) VALUES
  ('absorbance', '{"en-us": "Absorbance", "cs-cz": "Absorbance"}', 'A', NULL, 'analytical_chemistry', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('absorbed_dose', '{"en-us": "Absorbed dose", "cs-cz": "Absorbovaná dávka"}', 'D', NULL, 'nuclear_physics', 4, NULL, NULL, '[{"unit": "gray", "exponent": 1}]', 0.0, 2.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('absorbed_dose_rate', '{"en-us": "Absorbed dose rate", "cs-cz": "Dávkový příkon"}', '\dot{D}', NULL, 'nuclear_physics', 4, NULL, NULL, '[{"unit":"gray","exponent":1},{"unit":"second","exponent":-1}]', 0.0, 2.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('acceleration', '{"en-us": "Acceleration", "cs-cz": "Zrychlení"}', 'a', NULL, 'kinematics', 2, NULL, NULL, '[{"unit":"metre","exponent":1},{"unit":"second","exponent":-2}]', 0.0, 1.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('activity', '{"en-us": "Activity", "cs-cz": "Aktivita"}', 'A', NULL, 'nuclear_physics', 3, NULL, NULL, '[{"unit": "becquerel", "exponent": 1}]', 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('amount', '{"en-us": "Amount of substance", "cs-cz": "Látkové množství"}', 'n', NULL, 'ideal_gases', 3, NULL, NULL, '[{"unit": "mole", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
  ('angle', '{"en-us": "Plane angle", "cs-cz": "Rovinný úhel"}', '\theta', NULL, 'trigonometric_identities', 1, NULL, NULL, '[{"unit": "radian", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('angular_acceleration', '{"en-us": "Angular acceleration", "cs-cz": "Úhlové zrychlení"}', '\alpha', NULL, 'rotational_mechanics', 3, NULL, NULL, '[{"unit":"radian","exponent":1},{"unit":"second","exponent":-2}]', 0.0, 0.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('angular_momentum', '{"en-us": "Angular momentum", "cs-cz": "Moment hybnosti"}', 'L', NULL, 'angular_momentum', 3, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":2},{"unit":"second","exponent":-1}]', 1.0, 2.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('angular_velocity', '{"en-us": "Angular velocity", "cs-cz": "Úhlová rychlost"}', '\omega', NULL, 'rotational_mechanics', 3, NULL, NULL, '[{"unit":"radian","exponent":1},{"unit":"second","exponent":-1}]', 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('area', '{"en-us": "Area", "cs-cz": "Plocha"}', 'A', NULL, 'plane_geometry', 1, NULL, NULL, '[{"unit":"metre","exponent":2}]', 0.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('capacitance', '{"en-us": "Capacitance", "cs-cz": "Kapacita"}', 'C', NULL, 'circuits', 3, NULL, NULL, '[{"unit": "farad", "exponent": 1}]', -1.0, -2.0, 4.0, 2.0, 0.0, 0.0, 0.0),
  ('catalytic_activity', '{"en-us": "Catalytic activity", "cs-cz": "Katalytická aktivita"}', 'k', NULL, 'chemical_kinetics', 3, NULL, NULL, '[{"unit": "katal", "exponent": 1}]', 0.0, 0.0, -1.0, 0.0, 0.0, 1.0, 0.0),
  ('catalytic_activity_concentration', '{"en-us": "Catalytic activity concentration", "cs-cz": "Koncentrace katalytické aktivity"}', 'k_v', NULL, 'chemical_kinetics', 4, NULL, NULL, '[{"unit":"katal","exponent":1},{"unit":"metre","exponent":-3}]', 0.0, -3.0, -1.0, 0.0, 0.0, 1.0, 0.0),
  ('charge', '{"en-us": "Electric charge", "cs-cz": "Elektrický náboj"}', 'Q', NULL, 'electrostatics', 2, NULL, NULL, '[{"unit": "coulomb", "exponent": 1}]', 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0),
  ('charge_density', '{"en-us": "Electric charge density", "cs-cz": "Hustota elektrického náboje"}', '\rho', NULL, 'electrostatics', 3, NULL, NULL, '[{"unit":"coulomb","exponent":1},{"unit":"metre","exponent":-3}]', 0.0, -3.0, 1.0, 1.0, 0.0, 0.0, 0.0),
  ('coefficient_of_friction', '{"en-us": "Coefficient of friction", "cs-cz": "Součinitel tření"}', '\mu', NULL, 'friction', 2, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('coefficient_of_linear_expansion', '{"en-us": "Coefficient of linear expansion", "cs-cz": "Součinitel délkové roztažnosti"}', '\alpha', NULL, 'heat_transfer', 3, NULL, NULL, '[{"unit":"kelvin","exponent":-1}]', 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0),
  ('concentration', '{"en-us": "Concentration", "cs-cz": "Koncentrace"}', 'c', NULL, 'solutions', 2, NULL, NULL, '[{"unit":"mole","exponent":1},{"unit":"metre","exponent":-3}]', 0.0, -3.0, 0.0, 0.0, 0.0, 1.0, 0.0),
  ('conductance', '{"en-us": "Electrical conductance", "cs-cz": "Elektrická vodivost"}', 'G', NULL, 'circuits', 3, NULL, NULL, '[{"unit": "siemens", "exponent": 1}]', -1.0, -2.0, 3.0, 2.0, 0.0, 0.0, 0.0),
  ('current', '{"en-us": "Electric current", "cs-cz": "Elektrický proud"}', 'I', NULL, 'current_electricity', 2, NULL, NULL, '[{"unit": "ampere", "exponent": 1}]', 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
  ('current_density', '{"en-us": "Current density", "cs-cz": "Hustota proudu"}', 'j', NULL, 'circuits', 3, NULL, NULL, '[{"unit":"ampere","exponent":1},{"unit":"metre","exponent":-2}]', 0.0, -2.0, 0.0, 1.0, 0.0, 0.0, 0.0),
  ('degree_of_polarization', '{"en-us": "Degree of polarization", "cs-cz": "Stupeň polarizace"}', 'P', NULL, 'polarization', 4, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('density', '{"en-us": "Density", "cs-cz": "Hustota"}', '\rho', NULL, 'fluid_mechanics', 2, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":-3}]', 1.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('dimensionless', '{"en-us": "Dimensionless", "cs-cz": "Bezrozměrné"}', '', NULL, NULL, NULL, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('dose_equivalent', '{"en-us": "Dose equivalent", "cs-cz": "Dávkový ekvivalent"}', 'H', NULL, 'nuclear_physics', 4, NULL, NULL, '[{"unit": "sievert", "exponent": 1}]', 0.0, 2.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  -- drop: a sentinel quantity for dropping an operand of an operation
  ('drop', '{"en-us": "Drop", "cs-cz": "Vynechat"}', '', NULL, NULL, 1, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('dynamic_viscosity', '{"en-us": "Dynamic viscosity", "cs-cz": "Dynamická viskozita"}', '\eta', NULL, 'fluid_dynamics', 3, NULL, NULL, '[{"unit":"pascal","exponent":1},{"unit":"second","exponent":1}]', 1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('electric_field_strength', '{"en-us": "Electric field strength", "cs-cz": "Intenzita elektrického pole"}', 'E', NULL, 'electrostatics', 3, NULL, NULL, '[{"unit":"volt","exponent":1},{"unit":"metre","exponent":-1}]', 1.0, 1.0, -3.0, -1.0, 0.0, 0.0, 0.0),
  ('electric_potential', '{"en-us": "Electric potential", "cs-cz": "Elektrický potenciál"}', 'V', NULL, 'electrostatics', 3, NULL, NULL, '[{"unit": "volt", "exponent": 1}]', 1.0, 2.0, -3.0, -1.0, 0.0, 0.0, 0.0),
  ('electromagnetic_induction', '{"en-us": "Electromagnetic induction", "cs-cz": "Elektromagnetická indukce"}', '\mathcal{E}', NULL, 'electromagnetic_induction', 4, NULL, NULL, '[{"unit": "volt", "exponent": 1}]', 1.0, 2.0, -3.0, -1.0, 0.0, 0.0, 0.0),
  ('energy', '{"en-us": "Energy", "cs-cz": "Energie"}', 'E', NULL, 'work_and_energy', 2, NULL, NULL, '[{"unit": "joule", "exponent": 1}]', 1.0, 2.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('energy_density', '{"en-us": "Energy density", "cs-cz": "Hustota energie"}', 'u', NULL, 'work_and_energy', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"metre","exponent":-3}]', 1.0, -1.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('entropy', '{"en-us": "Entropy", "cs-cz": "Entropie"}', 'S', NULL, 'second_law', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"kelvin","exponent":-1}]', 1.0, 2.0, -2.0, 0.0, -1.0, 0.0, 0.0),
  ('equilibrium_constant', '{"en-us": "Equilibrium constant", "cs-cz": "Rovnovážná konstanta"}', 'K_\mathrm{eq}', NULL, 'chemical_equilibrium', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('exposure', '{"en-us": "Exposure", "cs-cz": "Ozáření"}', 'X', NULL, 'nuclear_physics', 4, NULL, NULL, '[{"unit":"coulomb","exponent":1},{"unit":"kilogram","exponent":-1}]', -1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0),
  ('force', '{"en-us": "Force", "cs-cz": "Síla"}', 'F', NULL, 'dynamics', 2, NULL, NULL, '[{"unit": "newton", "exponent": 1}]', 1.0, 1.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('frequency', '{"en-us": "Frequency", "cs-cz": "Frekvence"}', 'f', NULL, 'oscillations_and_waves', 2, NULL, NULL, '[{"unit": "hertz", "exponent": 1}]', 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('heat_engine_efficiency', '{"en-us": "Heat engine efficiency", "cs-cz": "Účinnost tepelného stroje"}', '\eta', NULL, 'heat_engines', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('illuminance', '{"en-us": "Illuminance", "cs-cz": "Osvětlení"}', 'E_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit": "lux", "exponent": 1}]', 0.0, -2.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('inductance', '{"en-us": "Inductance", "cs-cz": "Indukčnost"}', 'L', NULL, 'circuits', 3, NULL, NULL, '[{"unit": "henry", "exponent": 1}]', 1.0, 2.0, -2.0, -2.0, 0.0, 0.0, 0.0),
  ('irradiance', '{"en-us": "Irradiance", "cs-cz": "Intenzita záření"}', 'E', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit":"watt","exponent":1},{"unit":"metre","exponent":-2}]', 1.0, 0.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('length', '{"en-us": "Length", "cs-cz": "Délka"}', 'l', NULL, 'kinematics', 1, NULL, NULL, '[{"unit": "metre", "exponent": 1}]', 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
   ('logarithmic_ratio', '{"en-us": "Logarithmic ratio", "cs-cz": "Logaritmický podíl"}', '', NULL, NULL, NULL, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('lorentz_factor', '{"en-us": "Lorentz factor", "cs-cz": "Lorentzův faktor"}', '\gamma', NULL, 'relativity', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('luminance', '{"en-us": "Luminance", "cs-cz": "Svítivost"}', 'L_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit":"candela","exponent":1},{"unit":"metre","exponent":-2}]', 0.0, -2.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('luminous_flux', '{"en-us": "Luminous flux", "cs-cz": "Světelný tok"}', '\Phi_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit": "lumen", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('luminous_intensity', '{"en-us": "Luminous intensity", "cs-cz": "Svítivost"}', 'I_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit": "candela", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('magnetic_field_strength', '{"en-us": "Magnetic field strength", "cs-cz": "Intenzita magnetického pole"}', 'H', NULL, 'magnetism', 3, NULL, NULL, '[{"unit":"ampere","exponent":1},{"unit":"metre","exponent":-1}]', 0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0),
  ('magnetic_flux', '{"en-us": "Magnetic flux", "cs-cz": "Magnetický tok"}', '\Phi', NULL, 'magnetism', 3, NULL, NULL, '[{"unit": "weber", "exponent": 1}]', 1.0, 2.0, -2.0, -1.0, 0.0, 0.0, 0.0),
  ('magnetic_flux_density', '{"en-us": "Magnetic flux density", "cs-cz": "Magnetická indukce"}', 'B', NULL, 'magnetism', 3, NULL, NULL, '[{"unit": "tesla", "exponent": 1}]', 1.0, 0.0, -2.0, -1.0, 0.0, 0.0, 0.0),
  ('mass', '{"en-us": "Mass", "cs-cz": "Hmotnost"}', 'm', NULL, 'dynamics', 1, NULL, NULL, '[{"unit": "kilogram", "exponent": 1}]', 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('mass_concentration', '{"en-us": "Mass concentration", "cs-cz": "Hmotnostní koncentrace"}', '\gamma', NULL, 'solutions', 3, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":-3}]', 1.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('molar_absorptivity', '{"en-us": "Molar absorptivity", "cs-cz": "Molární absorpční koeficient"}', '\varepsilon', NULL, 'analytical_chemistry', 3, NULL, NULL, '[{"unit":"mole","exponent":-1},{"unit":"metre","exponent":-1}]', 0.0, 2.0, 0.0, 0.0, 0.0, -1.0, 0.0),
  ('molar_energy', '{"en-us": "Molar energy", "cs-cz": "Molární energie"}', 'E_m', NULL, 'thermochemistry', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"mole","exponent":-1}]', 1.0, 2.0, -2.0, 0.0, 0.0, -1.0, 0.0),
  ('molar_entropy', '{"en-us": "Molar entropy", "cs-cz": "Molární entropie"}', 'S_m', NULL, 'thermochemistry', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"mole","exponent":-1},{"unit":"kelvin","exponent":-1}]', 1.0, 2.0, -2.0, 0.0, -1.0, -1.0, 0.0),
  ('molar_mass', '{"en-us": "Molar mass", "cs-cz": "Molární hmotnost"}', 'M', NULL, 'molar_mass', 2, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"mole","exponent":-1}]', 1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0),
  ('moment_of_inertia', '{"en-us": "Moment of inertia", "cs-cz": "Moment setrvačnosti"}', 'I', NULL, 'moment_of_inertia', 3, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":2}]', 1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('momentum', '{"en-us": "Momentum", "cs-cz": "Hybnost"}', 'p', NULL, 'dynamics', 2, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":1},{"unit":"second","exponent":-1}]', 1.0, 1.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('permeability', '{"en-us": "Permeability", "cs-cz": "Permeabilita"}', '\mu', NULL, 'magnetism', 4, NULL, NULL, '[{"unit":"henry","exponent":1},{"unit":"metre","exponent":-1}]', 1.0, 1.0, -2.0, -2.0, 0.0, 0.0, 0.0),
  ('permittivity', '{"en-us": "Permittivity", "cs-cz": "Permitivita"}', '\varepsilon', NULL, 'electrostatics', 4, NULL, NULL, '[{"unit":"farad","exponent":1},{"unit":"metre","exponent":-1}]', -1.0, -3.0, 4.0, 2.0, 0.0, 0.0, 0.0),
  ('ph', '{"en-us": "pH", "cs-cz": "pH"}', '\mathrm{pH}', NULL, 'acids_and_bases', 2, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('power', '{"en-us": "Power", "cs-cz": "Výkon"}', 'P', NULL, 'work_and_energy', 2, NULL, NULL, '[{"unit": "watt", "exponent": 1}]', 1.0, 2.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('pressure', '{"en-us": "Pressure", "cs-cz": "Tlak"}', 'P', NULL, 'ideal_gases', 3, NULL, NULL, '[{"unit": "pascal", "exponent": 1}]', 1.0, -1.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('radiance', '{"en-us": "Radiance", "cs-cz": "Záře"}', 'L_e', NULL, 'electromagnetic_waves', 4, NULL, NULL, '[{"unit":"watt","exponent":1},{"unit":"metre","exponent":-2},{"unit":"steradian","exponent":-1}]', 1.0, 0.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('radiant_intensity', '{"en-us": "Radiant intensity", "cs-cz": "Zářivost"}', 'I_e', NULL, 'electromagnetic_waves', 4, NULL, NULL, '[{"unit":"watt","exponent":1},{"unit":"steradian","exponent":-1}]', 1.0, 2.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('reflectance', '{"en-us": "Reflectance", "cs-cz": "Reflexní schopnost"}', 'R', NULL, 'reflection', 2, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('refractive_index', '{"en-us": "Refractive index", "cs-cz": "Index lomu"}', 'n', NULL, 'refraction', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('resistance', '{"en-us": "Resistance", "cs-cz": "Elektrický odpor"}', 'R', NULL, 'circuits', 3, NULL, NULL, '[{"unit": "ohm", "exponent": 1}]', 1.0, 2.0, -3.0, -2.0, 0.0, 0.0, 0.0),
  ('reynolds_number', '{"en-us": "Reynolds number", "cs-cz": "Reynoldsovo číslo"}', '\mathit{Re}', NULL, 'reynolds_number', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('solid_angle', '{"en-us": "Solid angle", "cs-cz": "Prostorový úhel"}', '\Omega', NULL, 'trigonometric_identities', 2, NULL, NULL, '[{"unit": "steradian", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('specific_charge', '{"en-us": "Specific charge", "cs-cz": "Měrný náboj"}', 'q_m', NULL, 'electrostatics', 3, NULL, NULL, '[{"unit":"coulomb","exponent":1},{"unit":"kilogram","exponent":-1}]', -1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0),
  ('specific_energy', '{"en-us": "Specific energy", "cs-cz": "Měrná energie"}', 'e', NULL, 'work_and_energy', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"kilogram","exponent":-1}]', 0.0, 2.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('specific_heat_capacity', '{"en-us": "Specific heat capacity", "cs-cz": "Měrná tepelná kapacita"}', 'c', NULL, 'heat_transfer', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"kilogram","exponent":-1},{"unit":"kelvin","exponent":-1}]', 0.0, 2.0, -2.0, 0.0, -1.0, 0.0, 0.0),
  ('specific_volume', '{"en-us": "Specific volume", "cs-cz": "Měrný objem"}', 'v', NULL, 'fluid_mechanics', 3, NULL, NULL, '[{"unit":"metre","exponent":3},{"unit":"kilogram","exponent":-1}]', -1.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('spring_constant', '{"en-us": "Spring constant", "cs-cz": "Tuhost pružiny"}', 'k', NULL, 'springs', 3, NULL, NULL, '[{"unit": "newton", "exponent": 1}, {"unit": "metre", "exponent": -1}]', 1.0, 0.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('surface_charge_density', '{"en-us": "Surface charge density", "cs-cz": "Plošná hustota náboje"}', '\sigma', NULL, 'electrostatics', 3, NULL, NULL, '[{"unit":"coulomb","exponent":1},{"unit":"metre","exponent":-2}]', 0.0, -2.0, 1.0, 1.0, 0.0, 0.0, 0.0),
  ('surface_density', '{"en-us": "Surface density", "cs-cz": "Plošná hustota"}', '\rho_A', NULL, 'fluid_mechanics', 3, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":-2}]', 1.0, -2.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('surface_tension', '{"en-us": "Surface tension", "cs-cz": "Povrchové napětí"}', '\gamma', NULL, 'surface_tension', 3, NULL, NULL, '[{"unit":"newton","exponent":1},{"unit":"metre","exponent":-1}]', 1.0, 0.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('temperature', '{"en-us": "Temperature", "cs-cz": "Teplota"}', 'T', NULL, 'ideal_gases', 2, NULL, NULL, '[{"unit": "kelvin", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
  ('thermal_conductivity', '{"en-us": "Thermal conductivity", "cs-cz": "Tepelná vodivost"}', 'k', NULL, 'heat_transfer', 3, NULL, NULL, '[{"unit":"watt","exponent":1},{"unit":"metre","exponent":-1},{"unit":"kelvin","exponent":-1}]', 1.0, 1.0, -3.0, 0.0, -1.0, 0.0, 0.0),
  ('time', '{"en-us": "Time", "cs-cz": "Čas"}', 't', NULL, 'kinematics', 1, NULL, NULL, '[{"unit": "second", "exponent": 1}]', 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
  ('torque', '{"en-us": "Torque", "cs-cz": "Moment síly"}', '\tau', NULL, 'rotational_mechanics', 3, NULL, NULL, '[{"unit":"newton","exponent":1},{"unit":"metre","exponent":1}]', 1.0, 2.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('van_der_waals_attraction', '{"en-us": "Van der Waals attraction parameter", "cs-cz": "Van der Waalsova přitažlivost"}', 'a', NULL, 'ideal_gases', 4, NULL, NULL, '[{"unit":"pascal","exponent":1},{"unit":"metre","exponent":6},{"unit":"mole","exponent":-2}]', 1.0, 5.0, -2.0, 0.0, 0.0, -2.0, 0.0),
  ('van_der_waals_volume', '{"en-us": "Van der Waals volume parameter", "cs-cz": "Van der Waalsův objem"}', 'b', NULL, 'ideal_gases', 4, NULL, NULL, '[{"unit":"metre","exponent":3},{"unit":"mole","exponent":-1}]', 0.0, 3.0, 0.0, 0.0, 0.0, -1.0, 0.0),
  ('variable', '{"en-us": "Variable"}', 'x', NULL, 'equations', NULL, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('velocity', '{"en-us": "Velocity", "cs-cz": "Rychlost"}', 'v', NULL, 'kinematics', 2, NULL, NULL, '[{"unit":"metre","exponent":1},{"unit":"second","exponent":-1}]', 0.0, 1.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('volume', '{"en-us": "Volume", "cs-cz": "Objem"}', 'V', NULL, 'ideal_gases', 2, NULL, NULL, '[{"unit":"metre","exponent":3}]', 0.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('wavenumber', '{"en-us": "Wavenumber", "cs-cz": "Vlnové číslo"}', '\tilde{\nu}', NULL, 'oscillations_and_waves', 3, NULL, NULL, '[{"unit":"metre","exponent":-1}]', 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
;


INSERT OR IGNORE INTO unit VALUES('ampere','{"en-us": "Ampere", "cs-cz": "Ampér"}','A','current',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('arcminute','{"en-us": "Arcminute", "cs-cz": "Úhlová minuta"}','{}^{\prime}','angle',0,NULL,0.00029088820866572158,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('arcsecond','{"en-us": "Arcsecond", "cs-cz": "Úhlová vteřina"}','{}^{\prime\prime}','angle',0,NULL,4.8481368110953598e-06,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('astronomical_unit','{"en-us": "Astronomical unit", "cs-cz": "Astronomická jednotka"}','au','length',0,NULL,149597870700.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('becquerel','{"en-us": "Becquerel", "cs-cz": "Becquerel"}','Bq','activity',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('bel','{"en-us": "Bel", "cs-cz": "Bel"}','B','logarithmic_ratio',0,NULL,1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('candela','{"en-us": "Candela", "cs-cz": "Kandela"}','cd','luminous_intensity',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('centimetre','{"en-us": "Centimeter", "en-uk": "Centimetre", "cs-cz": "Centimetr"}','cm','length',0,'CGS',0.01,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('coulomb','{"en-us": "Coulomb", "cs-cz": "Coulomb"}','C','charge',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('dalton','{"en-us": "Dalton", "cs-cz": "Dalton"}','Da','mass',0,NULL,1.66053906892e-27,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('day','{"en-us": "Day", "cs-cz": "Den"}','d','time',0,NULL,86400.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('decibel','{"en-us": "Decibel", "cs-cz": "Decibel"}','dB','logarithmic_ratio',0,NULL,0.1,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('degree','{"en-us": "Degree", "cs-cz": "Stupeň"}','{}^{\circ}','angle',0,NULL,0.017453292519943296,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('degree_celsius','{"en-us": "Degree Celsius", "cs-cz": "Stupeň Celsia"}','{}^{\circ}\mathrm{C}','temperature',0,NULL,1.0,NULL,273.15);
INSERT OR IGNORE INTO unit VALUES('dyne','{"en-us": "Dyne", "cs-cz": "Dyn"}','dyn','force',0,'CGS',1.0e-05,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('electronvolt','{"en-us": "Electronvolt", "cs-cz": "Elektronvolt"}','eV','energy',0,NULL,1.602176634e-19,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('farad','{"en-us": "Farad", "cs-cz": "Farad"}','F','capacitance',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gram','{"en-us": "Gram", "cs-cz": "Gram"}','g','mass',0,'CGS',0.001,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gray','{"en-us": "Gray", "cs-cz": "Gray"}','Gy','absorbed_dose',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('hectare','{"en-us": "Hectare", "cs-cz": "Hektar"}','ha','area',0,NULL,10000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('henry','{"en-us": "Henry", "cs-cz": "Henry"}','H','inductance',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('hertz','{"en-us": "Hertz", "cs-cz": "Hertz"}','Hz','frequency',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('hour','{"en-us": "Hour", "cs-cz": "Hodina"}','h','time',0,NULL,3600.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('joule','{"en-us": "Joule", "cs-cz": "Joule"}','J','energy',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('katal','{"en-us": "Katal", "cs-cz": "Katal"}','kat','catalytic_activity',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kelvin','{"en-us": "Kelvin", "cs-cz": "Kelvin"}','K','temperature',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kilogram','{"en-us": "Kilogram", "cs-cz": "Kilogram"}','kg','mass',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('litre','{"en-us": "Litre", "cs-cz": "Litr"}','L','volume',0,NULL,0.001,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('lumen','{"en-us": "Lumen", "cs-cz": "Lumen"}','lm','luminous_flux',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('lux','{"en-us": "Lux", "cs-cz": "Lux"}','lx','illuminance',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('metre','{"en-us": "Meter", "en-uk": "Metre", "cs-cz": "Metr"}','m','length',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('minute','{"en-us": "Minute", "cs-cz": "Minuta"}','min','time',0,NULL,60.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('mole','{"en-us": "Mole", "cs-cz": "Mol"}','mol','amount',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('neper','{"en-us": "Neper", "cs-cz": "Neper"}','Np','logarithmic_ratio',0,NULL,1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('newton','{"en-us": "Newton", "cs-cz": "Newton"}','N','force',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('ohm','{"en-us": "Ohm", "cs-cz": "Ohm"}','\Omega','resistance',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('pascal','{"en-us": "Pascal", "cs-cz": "Pascal"}','Pa','pressure',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('radian','{"en-us": "Radian", "cs-cz": "Radián"}','rad','angle',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('second','{"en-us": "Second", "cs-cz": "Sekunda"}','s','time',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('siemens','{"en-us": "Siemens", "cs-cz": "Siemens"}','S','conductance',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('sievert','{"en-us": "Sievert", "cs-cz": "Sievert"}','Sv','dose_equivalent',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('steradian','{"en-us": "Steradian", "cs-cz": "Steradián"}','sr','solid_angle',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('tesla','{"en-us": "Tesla", "cs-cz": "Tesla"}','T','magnetic_flux_density',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('tonne','{"en-us": "Tonne", "cs-cz": "Tuna"}','t','mass',0,NULL,1000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('volt','{"en-us": "Volt", "cs-cz": "Volt"}','V','electric_potential',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('watt','{"en-us": "Watt", "cs-cz": "Watt"}','W','power',1,'SI',1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('weber','{"en-us": "Weber", "cs-cz": "Weber"}','Wb','magnetic_flux',1,'SI',1.0,NULL,0.0);
-- Extended unit catalogue: non-SI, CGS, imperial/US customary, historical
-- and practical derived units. factor converts to the quantity's SI base
-- unit; offset applies affine conversions (temperature scales).
INSERT OR IGNORE INTO unit VALUES('abampere','{"en-us": "Abampere", "cs-cz": "Abampér"}','\mathrm{abA}','current',0,'CGS',10.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('abcoulomb','{"en-us": "Abcoulomb", "cs-cz": "Abcoulomb"}','\mathrm{abC}','charge',0,'CGS',10.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('abfarad','{"en-us": "Abfarad", "cs-cz": "Abfarad"}','\mathrm{abF}','capacitance',0,'CGS',1000000000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('abhenry','{"en-us": "Abhenry", "cs-cz": "Abhenry"}','\mathrm{abH}','inductance',0,'CGS',1e-09,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('abohm','{"en-us": "Abohm", "cs-cz": "Abohm"}','\mathrm{ab\Omega}','resistance',0,'CGS',1e-09,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('abvolt','{"en-us": "Abvolt", "cs-cz": "Abvolt"}','\mathrm{abV}','electric_potential',0,'CGS',1e-08,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('acre','{"en-us": "Acre", "cs-cz": "Akr"}','\mathrm{ac}','area',0,'Imperial',4046.8564224,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('acre_foot','{"en-us": "Acre-foot", "cs-cz": "Akr-stopa"}','\mathrm{ac{\cdot}ft}','volume',0,'Imperial',1233.48183754752,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('angstrom','{"en-us": "Ångström", "cs-cz": "Ångström"}','\AA','length',0,NULL,1e-10,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('are','{"en-us": "Are", "cs-cz": "Ar"}','\mathrm{a}','area',0,NULL,100.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('bar','{"en-us": "Bar", "cs-cz": "Bar"}','\mathrm{bar}','pressure',0,NULL,100000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('barn','{"en-us": "Barn", "cs-cz": "Barn"}','\mathrm{b}','area',0,NULL,1e-28,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('barrel_petroleum','{"en-us": "Barrel (petroleum)", "cs-cz": "Barel ropy"}','\mathrm{bbl}','volume',0,NULL,0.158987294928,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('barye','{"en-us": "Barye", "cs-cz": "Barye"}','\mathrm{Ba}','pressure',0,'CGS',0.1,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('british_thermal_unit','{"en-us": "British thermal unit", "cs-cz": "Britská tepelná jednotka"}','\mathrm{Btu}','energy',0,'Imperial',1055.05585262,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('btu_per_hour','{"en-us": "BTU per hour", "cs-cz": "BTU za hodinu"}','\frac{\mathrm{Btu}}{\mathrm{h}}','power',0,'Imperial',0.2930710701722222,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('btu_per_pound','{"en-us": "BTU per pound", "cs-cz": "BTU na libru"}','\frac{\mathrm{Btu}}{\mathrm{lb}}','specific_energy',0,'Imperial',2326.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('bushel_us','{"en-us": "Bushel (US)", "cs-cz": "Bušl (US)"}','\mathrm{bu\,(US)}','volume',0,'Imperial',0.03523907016688,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('calorie','{"en-us": "Calorie", "cs-cz": "Kalorie"}','\mathrm{cal}','energy',0,NULL,4.184,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('calorie_per_gram','{"en-us": "Calorie per gram", "cs-cz": "Kalorie na gram"}','\frac{\mathrm{cal}}{\mathrm{g}}','specific_energy',0,NULL,4184.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('calorie_per_gram_kelvin','{"en-us": "Calorie per gram-kelvin", "cs-cz": "Kalorie na gram na kelvin"}','\frac{\mathrm{cal}}{\mathrm{g{\cdot}K}}','specific_heat_capacity',0,NULL,4184.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('carat','{"en-us": "Carat", "cs-cz": "Karát"}','\mathrm{ct}','mass',0,NULL,0.0002,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('cubic_centimetre','{"en-us": "Cubic centimetre", "cs-cz": "Krychlový centimetr"}','\mathrm{cm^{3}}','volume',0,NULL,1e-06,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('cubic_decimetre','{"en-us": "Cubic decimetre", "cs-cz": "Krychlový decimetr"}','\mathrm{dm^{3}}','volume',0,NULL,0.001,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('cubic_foot','{"en-us": "Cubic foot", "cs-cz": "Krychlová stopa"}','\mathrm{ft^{3}}','volume',0,'Imperial',0.028316846592,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('cubic_inch','{"en-us": "Cubic inch", "cs-cz": "Krychlový palec"}','\mathrm{in^{3}}','volume',0,'Imperial',1.6387064e-05,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('cubic_millimetre','{"en-us": "Cubic millimetre", "cs-cz": "Krychlový milimetr"}','\mathrm{mm^{3}}','volume',0,NULL,1e-09,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('cubic_yard','{"en-us": "Cubic yard", "cs-cz": "Krychlový yard"}','\mathrm{yd^{3}}','volume',0,'Imperial',0.764554857984,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('cup_us','{"en-us": "Cup (US legal)", "cs-cz": "Šálek (US)"}','\mathrm{cup}','volume',0,'Imperial',0.00024,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('curie','{"en-us": "Curie", "cs-cz": "Curie"}','\mathrm{Ci}','activity',0,NULL,37000000000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('degree_fahrenheit','{"en-us": "Degree Fahrenheit", "cs-cz": "Stupeň Fahrenheita"}','{}^{\circ}\mathrm{F}','temperature',0,'Imperial',0.5555555555555556,NULL,255.37222222222223);
INSERT OR IGNORE INTO unit VALUES('degree_rankine','{"en-us": "Degree Rankine", "cs-cz": "Stupeň Rankina"}','{}^{\circ}\mathrm{R}','temperature',0,'Imperial',0.5555555555555556,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('degree_reaumur','{"en-us": "Degree Réaumur", "cs-cz": "Stupeň Réaumura"}','{}^{\circ}\mathrm{Ré}','temperature',0,NULL,1.25,NULL,273.15);
INSERT OR IGNORE INTO unit VALUES('dyne_per_centimetre','{"en-us": "Dyne per centimetre", "cs-cz": "Dyn na centimetr"}','\frac{\mathrm{dyn}}{\mathrm{cm}}','surface_tension',0,'CGS',0.001,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('earth_mass','{"en-us": "Earth mass", "cs-cz": "Hmotnost Země"}','M_{\oplus}','mass',0,NULL,5.972168e+24,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('enzyme_unit','{"en-us": "Enzyme unit", "cs-cz": "Enzymová jednotka"}','\mathrm{U}','catalytic_activity',0,NULL,1.6666666666666667e-08,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('erg','{"en-us": "Erg", "cs-cz": "Erg"}','\mathrm{erg}','energy',0,'CGS',1e-07,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('erg_per_second','{"en-us": "Erg per second", "cs-cz": "Erg za sekundu"}','\frac{\mathrm{erg}}{\mathrm{s}}','power',0,'CGS',1e-07,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('fathom','{"en-us": "Fathom", "cs-cz": "Sáh"}','\mathrm{ftm}','length',0,'Imperial',1.8288,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('fluid_ounce_imperial','{"en-us": "Fluid ounce (imperial)", "cs-cz": "Tekutá unce (imp.)"}','\mathrm{fl\,oz\,(imp)}','volume',0,'Imperial',2.84130625e-05,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('fluid_ounce_us','{"en-us": "Fluid ounce (US)", "cs-cz": "Tekutá unce (US)"}','\mathrm{fl\,oz}','volume',0,'Imperial',2.95735295625e-05,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('foot','{"en-us": "Foot", "cs-cz": "Stopa"}','\mathrm{ft}','length',0,'Imperial',0.3048,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('foot_candle','{"en-us": "Foot-candle", "cs-cz": "Stopová svíčková jednotka"}','\mathrm{fc}','illuminance',0,'Imperial',10.763910416709722,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('foot_lambert','{"en-us": "Foot-lambert", "cs-cz": "Stopový lambert"}','\mathrm{fL}','luminance',0,'Imperial',3.4262590996353905,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('foot_per_second','{"en-us": "Foot per second", "cs-cz": "Stopa za sekundu"}','\frac{\mathrm{ft}}{\mathrm{s}}','velocity',0,'Imperial',0.3048,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('foot_pound','{"en-us": "Foot-pound", "cs-cz": "Stopa-libra"}','\mathrm{ft{\cdot}lbf}','energy',0,'Imperial',1.3558179483314003,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('foot_pound_per_second','{"en-us": "Foot-pound per second", "cs-cz": "Stopa-libra za sekundu"}','\frac{\mathrm{ft{\cdot}lbf}}{\mathrm{s}}','power',0,'Imperial',1.3558179483314003,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('fortnight','{"en-us": "Fortnight", "cs-cz": "Čtrnáct dní"}','\mathrm{fn}','time',0,NULL,1209600.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('furlong','{"en-us": "Furlong", "cs-cz": "Furlong"}','\mathrm{fur}','length',0,'Imperial',201.168,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gal','{"en-us": "Gal", "cs-cz": "Gal"}','\mathrm{Gal}','acceleration',0,'CGS',0.01,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gallon_imperial','{"en-us": "Gallon (imperial)", "cs-cz": "Galon (imp.)"}','\mathrm{gal\,(imp)}','volume',0,'Imperial',0.00454609,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gallon_us','{"en-us": "Gallon (US)", "cs-cz": "Galon (US)"}','\mathrm{gal\,(US)}','volume',0,'Imperial',0.003785411784,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gauss','{"en-us": "Gauss", "cs-cz": "Gauss"}','\mathrm{G}','magnetic_flux_density',0,'CGS',0.0001,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gee','{"en-us": "Standard gravity", "cs-cz": "Normální tíhové zrychlení"}','g_{\mathrm{n}}','acceleration',0,NULL,9.80665,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gradian','{"en-us": "Gradian", "cs-cz": "Grad"}','{}^{\mathrm{g}}','angle',0,NULL,0.015707963267948967,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('grain','{"en-us": "Grain", "cs-cz": "Gran"}','\mathrm{gr}','mass',0,'Imperial',6.479891e-05,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gram_per_cubic_centimetre','{"en-us": "Gram per cubic centimetre", "cs-cz": "Gram na krychlový centimetr"}','\frac{\mathrm{g}}{\mathrm{cm^{3}}}','density',0,NULL,1000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gram_per_litre','{"en-us": "Gram per litre", "cs-cz": "Gram na litr"}','\frac{\mathrm{g}}{\mathrm{L}}','mass_concentration',0,NULL,1.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('gram_per_mole','{"en-us": "Gram per mole", "cs-cz": "Gram na mol"}','\frac{\mathrm{g}}{\mathrm{mol}}','molar_mass',0,NULL,0.001,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('hartree','{"en-us": "Hartree", "cs-cz": "Hartree"}','E_{\mathrm{h}}','energy',0,NULL,4.3597447222071e-18,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('horsepower','{"en-us": "Horsepower (mechanical)", "cs-cz": "Koňská síla (mechanická)"}','\mathrm{hp}','power',0,'Imperial',745.6998715822702,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('inch','{"en-us": "Inch", "cs-cz": "Palec"}','\mathrm{in}','length',0,'Imperial',0.0254,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('inch_of_mercury','{"en-us": "Inch of mercury", "cs-cz": "Palec rtuťového sloupce"}','\mathrm{inHg}','pressure',0,'Imperial',3386.388640341,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('inch_of_water','{"en-us": "Inch of water", "cs-cz": "Palec vodního sloupce"}','\mathrm{inH_{2}O}','pressure',0,'Imperial',249.08891,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kayser','{"en-us": "Kayser", "cs-cz": "Kayser"}','\mathrm{cm^{-1}}','wavenumber',0,NULL,100.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kilocalorie','{"en-us": "Kilocalorie", "cs-cz": "Kilokalorie"}','\mathrm{kcal}','energy',0,NULL,4184.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kilocalorie_per_mole','{"en-us": "Kilocalorie per mole", "cs-cz": "Kilokalorie na mol"}','\frac{\mathrm{kcal}}{\mathrm{mol}}','molar_energy',0,NULL,4184.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kilogram_force','{"en-us": "Kilogram-force", "cs-cz": "Kilopond"}','\mathrm{kp}','force',0,NULL,9.80665,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kilogram_force_metre','{"en-us": "Kilogram-force metre", "cs-cz": "Kilopondmetr"}','\mathrm{kp{\cdot}m}','torque',0,NULL,9.80665,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kilojoule_per_mole','{"en-us": "Kilojoule per mole", "cs-cz": "Kilojoule na mol"}','\frac{\mathrm{kJ}}{\mathrm{mol}}','molar_energy',0,NULL,1000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kilometre_per_hour','{"en-us": "Kilometre per hour", "cs-cz": "Kilometr za hodinu"}','\frac{\mathrm{km}}{\mathrm{h}}','velocity',0,NULL,0.2777777777777778,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kilowatt_hour','{"en-us": "Kilowatt-hour", "cs-cz": "Kilowatthodina"}','\mathrm{kWh}','energy',0,NULL,3600000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('kip','{"en-us": "Kip", "cs-cz": "Kip"}','\mathrm{kip}','force',0,'Imperial',4448.2216152605,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('knot','{"en-us": "Knot", "cs-cz": "Uzel"}','\mathrm{kn}','velocity',0,NULL,0.5144444444444445,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('ksi','{"en-us": "Kilopound per square inch", "cs-cz": "Kilibra na čtverečný palec"}','\mathrm{ksi}','pressure',0,'Imperial',6894757.293168361,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('lambert','{"en-us": "Lambert", "cs-cz": "Lambert"}','\mathrm{La}','luminance',0,'CGS',3183.098861837907,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('league','{"en-us": "League", "cs-cz": "Legua"}','\mathrm{lea}','length',0,'Imperial',4828.032,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('light_year','{"en-us": "Light-year", "cs-cz": "Světelný rok"}','\mathrm{ly}','length',0,NULL,9460730472580800.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('long_ton','{"en-us": "Long ton (UK)", "cs-cz": "Britská tuna"}','\mathrm{ton\,(UK)}','mass',0,'Imperial',1016.0469088,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('maxwell','{"en-us": "Maxwell", "cs-cz": "Maxwell"}','\mathrm{Mx}','magnetic_flux',0,'CGS',1e-08,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('metric_horsepower','{"en-us": "Metric horsepower", "cs-cz": "Metrická koňská síla"}','\mathrm{PS}','power',0,NULL,735.49875,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('mil','{"en-us": "Mil", "cs-cz": "Mil"}','\mathrm{mil}','length',0,'Imperial',2.54e-05,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('mile','{"en-us": "Mile", "cs-cz": "Míle"}','\mathrm{mi}','length',0,'Imperial',1609.344,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('mile_per_hour','{"en-us": "Mile per hour", "cs-cz": "Míle za hodinu"}','\frac{\mathrm{mi}}{\mathrm{h}}','velocity',0,'Imperial',0.44704,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('millibar','{"en-us": "Millibar", "cs-cz": "Millibar"}','\mathrm{mbar}','pressure',0,NULL,100.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('millimetre_of_mercury','{"en-us": "Millimetre of mercury", "cs-cz": "Milimetr rtuťového sloupce"}','\mathrm{mmHg}','pressure',0,NULL,133.322387415,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('molar','{"en-us": "Molar", "cs-cz": "Molární"}','\mathrm{M}','concentration',0,NULL,1000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('month','{"en-us": "Month (average)", "cs-cz": "Měsíc (průměrný)"}','\mathrm{mo}','time',0,NULL,2629746.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('nautical_mile','{"en-us": "Nautical mile", "cs-cz": "Námořní míle"}','\mathrm{nmi}','length',0,NULL,1852.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('oersted','{"en-us": "Oersted", "cs-cz": "Oersted"}','\mathrm{Oe}','magnetic_field_strength',0,'CGS',79.57747154594767,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('ounce','{"en-us": "Ounce", "cs-cz": "Unce"}','\mathrm{oz}','mass',0,'Imperial',0.028349523125,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('ounce_force','{"en-us": "Ounce-force", "cs-cz": "Unce-síla"}','\mathrm{ozf}','force',0,'Imperial',0.2780138509537812,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('parsec','{"en-us": "Parsec", "cs-cz": "Parsek"}','\mathrm{pc}','length',0,NULL,3.085677581491367e+16,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('parts_per_billion','{"en-us": "Parts per billion", "cs-cz": "Miliardtina"}','\mathrm{ppb}','dimensionless',0,NULL,1e-09,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('parts_per_million','{"en-us": "Parts per million", "cs-cz": "Miliontina"}','\mathrm{ppm}','dimensionless',0,NULL,1e-06,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('percent','{"en-us": "Percent", "cs-cz": "Procento"}','\%','dimensionless',0,NULL,0.01,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('permille','{"en-us": "Permille", "cs-cz": "Promile"}','\text{\textperthousand}','dimensionless',0,NULL,0.001,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('phot','{"en-us": "Phot", "cs-cz": "Fot"}','\mathrm{ph}','illuminance',0,'CGS',10000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('pint_imperial','{"en-us": "Pint (imperial)", "cs-cz": "Pinta (imp.)"}','\mathrm{pt\,(imp)}','volume',0,'Imperial',0.00056826125,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('pint_us','{"en-us": "Pint (US)", "cs-cz": "Pinta (US)"}','\mathrm{pt\,(US)}','volume',0,'Imperial',0.000473176473,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('planck_time','{"en-us": "Planck time", "cs-cz": "Planckův čas"}','t_{\mathrm{P}}','time',0,NULL,5.391247e-44,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('poise','{"en-us": "Poise", "cs-cz": "Poise"}','\mathrm{P}','dynamic_viscosity',0,'CGS',0.1,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('pound','{"en-us": "Pound", "cs-cz": "Libra"}','\mathrm{lb}','mass',0,'Imperial',0.45359237,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('pound_force','{"en-us": "Pound-force", "cs-cz": "Libra-síla"}','\mathrm{lbf}','force',0,'Imperial',4.4482216152605,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('pound_force_foot','{"en-us": "Pound-force foot", "cs-cz": "Libra-síla stopa"}','\mathrm{lbf{\cdot}ft}','torque',0,'Imperial',1.3558179483314003,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('pound_force_inch','{"en-us": "Pound-force inch", "cs-cz": "Libra-síla palec"}','\mathrm{lbf{\cdot}in}','torque',0,'Imperial',0.1129848290276167,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('pound_per_cubic_foot','{"en-us": "Pound per cubic foot", "cs-cz": "Libra na krychlovou stopu"}','\frac{\mathrm{lb}}{\mathrm{ft^{3}}}','density',0,'Imperial',16.01846337396014,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('pound_per_gallon','{"en-us": "Pound per gallon (US)", "cs-cz": "Libra na galon (US)"}','\frac{\mathrm{lb}}{\mathrm{gal}}','mass_concentration',0,'Imperial',119.82642731689663,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('poundal','{"en-us": "Poundal", "cs-cz": "Poundál"}','\mathrm{pdl}','force',0,'Imperial',0.138254954376,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('psi','{"en-us": "Pound per square inch", "cs-cz": "Libra na čtverečný palec"}','\mathrm{psi}','pressure',0,'Imperial',6894.757293168361,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('quart_us','{"en-us": "Quart (US fluid)", "cs-cz": "Kvarta (US)"}','\mathrm{qt\,(US)}','volume',0,'Imperial',0.000946352946,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('rad','{"en-us": "Rad", "cs-cz": "Rad"}','\mathrm{rad}','absorbed_dose',0,NULL,0.01,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('rem','{"en-us": "Rem", "cs-cz": "Rem"}','\mathrm{rem}','dose_equivalent',0,NULL,0.01,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('revolutions_per_minute','{"en-us": "Revolutions per minute", "cs-cz": "Otáčky za minutu"}','\frac{\mathrm{rev}}{\mathrm{min}}','frequency',0,NULL,0.016666666666666666,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('roentgen','{"en-us": "Roentgen", "cs-cz": "Röntgen"}','\mathrm{R}','exposure',0,NULL,0.000258,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('rutherford','{"en-us": "Rutherford", "cs-cz": "Rutherford"}','\mathrm{Rd}','activity',0,NULL,1000000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('shake','{"en-us": "Shake", "cs-cz": "Shake"}','\mathrm{sh}','time',0,NULL,1e-08,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('short_ton','{"en-us": "Short ton (US)", "cs-cz": "Americká tuna"}','\mathrm{ton\,(US)}','mass',0,'Imperial',907.18474,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('slug','{"en-us": "Slug", "cs-cz": "Slug"}','\mathrm{slug}','mass',0,'Imperial',14.593902937206362,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('solar_mass','{"en-us": "Solar mass", "cs-cz": "Hmotnost Slunce"}','M_{\odot}','mass',0,NULL,1.98847e+30,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('solar_radius','{"en-us": "Solar radius", "cs-cz": "Sluneční poloměr"}','R_{\odot}','length',0,NULL,695700000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('square_foot','{"en-us": "Square foot", "cs-cz": "Čtvereční stopa"}','\mathrm{ft^{2}}','area',0,'Imperial',0.09290304,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('square_inch','{"en-us": "Square inch", "cs-cz": "Čtverečný palec"}','\mathrm{in^{2}}','area',0,'Imperial',0.00064516,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('square_mile','{"en-us": "Square mile", "cs-cz": "Čtvereční míle"}','\mathrm{mi^{2}}','area',0,'Imperial',2589988.110336,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('square_yard','{"en-us": "Square yard", "cs-cz": "Čtverečný yard"}','\mathrm{yd^{2}}','area',0,'Imperial',0.83612736,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('standard_atmosphere','{"en-us": "Standard atmosphere", "cs-cz": "Fyzikální atmosféra"}','\mathrm{atm}','pressure',0,NULL,101325.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('statampere','{"en-us": "Statampere", "cs-cz": "Statampér"}','\mathrm{statA}','current',0,'CGS',3.3356409519815207e-10,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('statcoulomb','{"en-us": "Statcoulomb", "cs-cz": "Statcoulomb"}','\mathrm{statC}','charge',0,'CGS',3.3356409519815207e-10,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('statfarad','{"en-us": "Statfarad", "cs-cz": "Statfarad"}','\mathrm{statF}','capacitance',0,'CGS',1.1126500560536185e-12,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('stathenry','{"en-us": "Stathenry", "cs-cz": "Stathenry"}','\mathrm{statH}','inductance',0,'CGS',898755178736.8176,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('statohm','{"en-us": "Statohm", "cs-cz": "Statohm"}','\mathrm{stat\Omega}','resistance',0,'CGS',898755178736.8176,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('statvolt','{"en-us": "Statvolt", "cs-cz": "Statvolt"}','\mathrm{statV}','electric_potential',0,'CGS',299.792458,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('statvolt_per_centimetre','{"en-us": "Statvolt per centimetre", "cs-cz": "Statvolt na centimetr"}','\frac{\mathrm{statV}}{\mathrm{cm}}','electric_field_strength',0,'CGS',29979.2458,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('stilb','{"en-us": "Stilb", "cs-cz": "Stilb"}','\mathrm{sb}','luminance',0,'CGS',10000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('stone','{"en-us": "Stone", "cs-cz": "Stone"}','\mathrm{st}','mass',0,'Imperial',6.35029318,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('svedberg','{"en-us": "Svedberg", "cs-cz": "Svedberg"}','\mathrm{S}','time',0,NULL,1e-13,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('technical_atmosphere','{"en-us": "Technical atmosphere", "cs-cz": "Technická atmosféra"}','\mathrm{at}','pressure',0,NULL,98066.5,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('therm','{"en-us": "Therm", "cs-cz": "Therm"}','\mathrm{thm}','energy',0,'Imperial',105506000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('tonne_force','{"en-us": "Tonne-force", "cs-cz": "Tunová síla"}','\mathrm{tf}','force',0,NULL,9806.65,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('tonne_tnt','{"en-us": "Tonne of TNT", "cs-cz": "Tuna TNT"}','\mathrm{t_{TNT}}','energy',0,NULL,4184000000.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('torr','{"en-us": "Torr", "cs-cz": "Torr"}','\mathrm{Torr}','pressure',0,NULL,133.32236842105263,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('troy_ounce','{"en-us": "Troy ounce", "cs-cz": "Trojská unce"}','\mathrm{oz\,t}','mass',0,NULL,0.0311034768,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('troy_pound','{"en-us": "Troy pound", "cs-cz": "Trojská libra"}','\mathrm{lb\,t}','mass',0,NULL,0.3732417216,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('turn','{"en-us": "Turn", "cs-cz": "Otočka"}','\mathrm{tr}','angle',0,NULL,6.283185307179586,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('watt_hour','{"en-us": "Watt-hour", "cs-cz": "Watthodina"}','\mathrm{Wh}','energy',0,NULL,3600.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('week','{"en-us": "Week", "cs-cz": "Týden"}','\mathrm{wk}','time',0,NULL,604800.0,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('yard','{"en-us": "Yard", "cs-cz": "Yard"}','\mathrm{yd}','length',0,'Imperial',0.9144,NULL,0.0);
INSERT OR IGNORE INTO unit VALUES('year','{"en-us": "Year (Julian)", "cs-cz": "Rok (juliánský)"}','\mathrm{a}','time',0,NULL,31557600.0,NULL,0.0);

-- Operator catalogue
-- An operator is a reusable symbol with fixed arity, precedence, and
-- associativity. math is a Python expression template using operand names
-- a, b, c, ... (NULL when not numerically computable, e.g. =, \propto).
-- symbol is the LaTeX display form (NULL = invisible).
--
-- Precedence is the binding strength; higher = binds tighter.
-- Special: relational operators use 5, arithmetic uses 10-30.

INSERT OR IGNORE INTO operator (id, symbol, math, arity, precedence, associativity, operator_type, paren_arg) VALUES
  ('add',    '+',      'a+b',                 2, 10, 'left',  'infix',      '[1,1]'),
  -- sub: arity-2 infix emitting `a - b`. When the left operand is the
  -- `drop` sentinel quantity, this is the unary minus (replaces the old
  -- `neg` prefix operator): `drop W sub` -> -W. Children: [a, b].
  ('sub',    '-',      'a-b',                 2, 10, 'left',  'infix',      '[1,1]'),
  ('pm',     '\pm',    'a',                   2, 10, 'left',  'infix',      '[1,1]'),
  ('mp',     '\mp',    'a',                   2, 10, 'left',  'infix',      '[1,1]'),
  ('mul',    NULL,     'a*b',                 2, 20, 'left',  'infix',      '[1,1]'),
  ('cdot',   '\cdot',  'a*b',                 2, 20, 'left',  'infix',      '[1,1]'),
  ('times',  '\times', 'a*b',                 2, 20, 'left',  'infix',      '[1,1]'),
  ('div',    '/',      'a/b',                 2, 20, 'left',  'infix',      '[1,1]'),
  ('frac',   '\frac',  'a/b',                 2, 20, 'left',  'infix',      '[0,0]'),
  ('pow',    '^',      'a**b',                2, 30, 'right', 'infix',      '[1,0]'),
  -- sqrt: arity-2 infix emitting \sqrt{radicand} (square root) or
  -- \sqrt[index]{radicand} (n-th root). Children: [radicand, index].
  -- paren_arg=[0,0]: both operands are inside the macro's {...} scopes.
  -- If index is `drop` or the literal number 2, emit `\sqrt{radicand}`.
  -- Otherwise emit `\sqrt[index]{radicand}`. With the implicit 2-omission,
  -- `sqrt x 2` -> \sqrt{x}, `sqrt x 3` -> \sqrt[3]{x}, `sqrt x drop` -> \sqrt{x}.
  ('sqrt',   '\sqrt',  'a**(1/b if b != 2 else 0.5)', 2, 30, 'right', 'infix', '[0,0]'),

  ('sin',    '\sin',   'math.sin(a)',         1, 30, 'right', 'prefix',     '[1]'),
  ('cos',    '\cos',   'math.cos(a)',         1, 30, 'right', 'prefix',     '[1]'),
  ('tan',    '\tan',   'math.tan(a)',         1, 30, 'right', 'prefix',     '[1]'),
  ('asin',   '\arcsin', 'math.asin(a)',       1, 30, 'right', 'prefix',     '[1]'),
  ('acos',   '\arccos', 'math.acos(a)',       1, 30, 'right', 'prefix',     '[1]'),
  ('atan',   '\arctan', 'math.atan(a)',       1, 30, 'right', 'prefix',     '[1]'),

  ('Delta',  '\Delta', NULL,                  1, 30, 'right', 'prefix',     '[1]'),
  ('nabla',  '\nabla', NULL,                  1, 30, 'right', 'prefix',     '[1]'),
  ('rmd',    '\mathrm{d}', NULL,              1, 30, 'right', 'prefix',     '[1]'),
  -- partial: prefix operator emitting \partial {a} (partial derivative
  -- symbol). Used for thermodynamics / Euler-Lagrange style notation.
  ('partial', '\partial', NULL,               1, 30, 'right', 'prefix',     '[1]'),
  ('overl',  '\overline', NULL,               1, 30, 'right', 'prefix',     '[0]'),

  ('abs',    NULL,      'abs(a)',             1, 30, 'right', 'prefix',     '[1]'),
  ('factorial', '!',    'math.factorial(a)',  1, 30, 'right', 'postfix',    '[1]'),
  ('exp',    '\exp',    'math.exp(a)',        1, 30, 'right', 'prefix',     '[1]'),
  -- log: arity-2 infix emitting \log_{base}{arg}. Children: [base, arg].
  -- paren_arg=[0,0]: both operands are inside the macro's {...} scopes, never
  -- auto-wrapped. The math template uses Python's math.log(arg, base) so the
  -- operand order matches the source (children[0]=base, children[1]=arg).
  -- Pass any operand as the `drop` quantity to blank it out: `log drop x`
  -- emits `\log x`, `log b drop` emits `\log_{b}`. With the implicit
  -- euler-omission (mirroring sqrt's implicit 2-omission), a base of the
  -- `euler_e` constant emits `\ln{arg}` rather than `\log_{e}{arg}`:
  -- `log euler_e length` -> \ln l.
  ('log',    '\log',    'math.log(b, a)',      2, 30, 'right', 'infix',      '[0,0]'),

  -- sum: arity-3 infix emitting \sum_{from}^{to}{body}. Children: [from, to, body].
  -- paren_arg=[0,0,0]: all three operands are inside the macro's {...} scopes.
  -- Pass any operand as the `drop` quantity to blank it out: `sum drop 5 x`
  -- emits `\sum^{5}{x}`, `sum 1 drop x` emits `\sum_{1}{x}` (or just `\sum{x}`
  -- if both limits are dropped).
  ('sum',    '\sum',    NULL,                  3, 30, 'right', 'infix',      '[0,0,0]'),
  -- prod: arity-3 infix emitting \prod_{from}^{to}{body}. Children: [from, to, body].
  -- paren_arg=[0,0,0]: same shape as `sum` and `int`. Drop in any slot
  -- blanks it out: `prod 1 drop x` -> \prod_{1}{x}, `prod drop drop x` -> \prod{x}.
  ('prod',   '\prod',   NULL,                  3, 30, 'right', 'infix',      '[0,0,0]'),

  -- oint: arity-3 infix emitting \oint_{from}^{to}{body}. Children: [from, to, body].
  -- paren_arg=[0,0,0]: feature-parity with `int`. Drop in any slot blanks it out.
  ('oint',   '\oint',   NULL,                  3, 30, 'right', 'infix',      '[0,0,0]'),
  -- lim: arity-3 infix emitting \lim_{var \to val}{body}. Children: [var, val, body].
  -- paren_arg=[0,0,0]: all three operands are inside the macro's {...} scopes.
  -- If either var or val is `drop`, the subscript is dropped entirely (a
  -- one-sided limit like `\lim_{x \to}` reads as malformed LaTeX, so we
  -- prefer `\lim{body}` rather than `\lim_{x \to}{body}`).
  ('lim',    '\lim',      NULL,                  3, 30, 'right', 'infix',      '[0,0,0]'),
  -- int: arity-3 infix emitting \int_{from}^{to}{body}. Children: [from, to, body].
  -- paren_arg=[0,0,0]: all three operands are inside the macro's {...} scopes.
  -- Symmetric with `sum`: any operand may be `drop` to blank it out.
  ('int',    '\int',      NULL,                  3, 30, 'right', 'infix',      '[0,0,0]'),

  ('newline','\\',        NULL,                  2,  2, 'left',  'infix',      '[0,0]'),

  ('eq',     '=',      NULL,                  2,  5, 'none',  'relational', '[1,1]'),
  ('neq',   '\neq',   NULL,                   2,  5, 'none',  'relational', '[1,1]'),
  ('approx', '\approx', NULL,                 2,  5, 'none',  'relational', '[1,1]'),
  ('prop',   '\propto', NULL,                 2,  5, 'none',  'relational', '[1,1]'),
  ('gt',     '>',      NULL,                  2,  5, 'none',  'relational', '[1,1]'),
  ('lt',     '<',      NULL,                  2,  5, 'none',  'relational', '[1,1]'),
  ('ngt',     '\ngtr',      NULL,             2,  5, 'none',  'relational', '[1,1]'),
  ('nlt',     '\nless',      NULL,            2,  5, 'none',  'relational', '[1,1]'),
  ('geq',    '\geq',   '\geq',                2,  5, 'none',  'relational', '[1,1]'),
  ('leq',    '\leq',   '\leq',                2,  5, 'none',  'relational', '[1,1]'),
  ('ngeq',    '\ngeq',   '\ngeq',             2,  5, 'none',  'relational', '[1,1]'),
  ('nleq',    '\nleq',   '\nleq',             2,  5, 'none',  'relational', '[1,1]'),
  ('sim',    '\sim',   NULL,                  2,  5, 'none',  'relational', '[1,1]'),
  ('perp',   '\perp',  NULL,                  2,  5, 'none',  'relational', '[1,1]'),
  ('parallel', '\parallel', NULL,             2,  5, 'none',  'relational', '[1,1]')
;


-- Constant catalogue
-- Constants are reusable symbols that can appear in any formula. value is
-- the numerical value (NULL for symbolic-only constants). default_unit
-- is JSON like in quantity.default_unit, used for dimensional physical
-- constants. difficulty mirrors the simplest formula using the constant;
-- quantity_id points at the quantity whose name/unit applies (same
-- dimensions); NULL leaves the constant unlisted on quantity pages.

INSERT OR IGNORE INTO constant (id, name, symbol, difficulty, description, links, value, default_unit, quantity_id) VALUES
  -- Pure mathematical constants
  ('pi',       '{"en-us": "Pi", "cs-cz": "Pí"}',                 '\pi', 1,
    '{"en-us": "Pi is the ratio of a circle''s circumference to its diameter, approximately 3.14159.", "cs-cz": "Pí je poměr obvodu kruhu k jeho průměru, přibližně 3,14159."}',
    '["https://en.wikipedia.org/wiki/Pi"]',
    3.141592653589793, NULL, NULL),
  ('euler_e',  '{"en-us": "Euler''s number", "cs-cz": "Eulerovo číslo"}', 'e', 4,
    '{"en-us": "Euler''s number is the base of the natural logarithm, approximately 2.71828.", "cs-cz": "Eulerovo číslo je základ přirozeného logaritmu, přibližně 2,71828."}',
    '["https://en.wikipedia.org/wiki/E_(mathematical_constant)"]',
    2.718281828459045, NULL, NULL),
  ('infinity', '{"en-us": "Infinity", "cs-cz": "Nekonečno"}',     '\infty', 2,
    '{"en-us": "Infinity is an unbounded value greater than every real number; it is not a number in the usual sense.", "cs-cz": "Nekonečno je neohraničená hodnota větší než všechna reálná čísla; v běžném smyslu se nejedná o číslo."}',
    '["https://en.wikipedia.org/wiki/Infinity"]',
    NULL, NULL, NULL),
  -- Dimensional physical constants (treated as constants for formula inclusion)
  ('gravitational_constant', '{"en-us": "Gravitational constant", "cs-cz": "Gravitační konstanta"}', 'G', 5,
    '{"en-us": "G determines the strength of gravity in Newton''s law of universal gravitation; measured as 6.674×10⁻¹¹ m³ kg⁻¹ s⁻².", "cs-cz": "G určuje sílu gravitace v Newtonově gravitačním zákoně; její změřená hodnota je 6,674×10⁻¹¹ m³ kg⁻¹ s⁻²."}',
    '["https://en.wikipedia.org/wiki/Gravitational_constant", "https://physics.nist.gov/cgi-bin/cuu/Value?bg"]',
    6.67430e-11,
    '[{"unit":"metre","exponent":3},{"unit":"kilogram","exponent":-1},{"unit":"second","exponent":-2}]',
    NULL),
  ('gas_constant',           '{"en-us": "Gas constant", "cs-cz": "Molární plynová konstanta"}', 'R', 5,
    '{"en-us": "The universal gas constant relates the pressure, volume and temperature of an ideal gas; R = N_A·k_B ≈ 8.314 J mol⁻¹ K⁻¹.", "cs-cz": "Univerzální plynová konstanta spojuje tlak, objem a teplotu ideálního plynu; R = N_A·k_B ≈ 8,314 J mol⁻¹ K⁻¹."}',
    '["https://en.wikipedia.org/wiki/Gas_constant"]',
    8.31446261815324,
    '[{"unit":"joule","exponent":1},{"unit":"mole","exponent":-1},{"unit":"kelvin","exponent":-1}]',
    'molar_entropy'),
  -- The speed of light in vacuum. Encoded as a constant so formulas can
  -- reference it (the legacy schema encoded it implicitly via a NULL
  -- quantity + coeff_exponent=2.0 row, which we now interpret as `c`).
  ('speed_of_light',         '{"en-us": "Speed of light in vacuum", "cs-cz": "Rychlost světla ve vakuu"}', 'c', 5,
    '{"en-us": "The speed at which light travels in vacuum; an exact SI defining constant, c = 299 792 458 m/s.", "cs-cz": "Rychlost šíření světla ve vakuu; přesně definovaná SI konstanta, c = 299 792 458 m/s."}',
    '["https://en.wikipedia.org/wiki/Speed_of_light"]',
    299792458.0,
    '[{"unit":"metre","exponent":1},{"unit":"second","exponent":-1}]',
    'velocity'),
  ('avogadro_number',        '{"en-us": "Avogadro number", "cs-cz": "Avogadrova konstanta"}', 'N_\mathrm{A}', 4,
    '{"en-us": "The number of particles in one mole of substance; an exact SI defining constant, N_A = 6.02214076×10²³ mol⁻¹.", "cs-cz": "Počet částic v jednom molu látky; přesně definovaná SI konstanta, N_A = 6,02214076×10²³ mol⁻¹."}',
    '["https://en.wikipedia.org/wiki/Avogadro_constant"]',
    6.02214076e23, NULL, NULL),
  ('planck_constant',        '{"en-us": "Planck constant", "cs-cz": "Planckova konstanta"}', 'h', 6,
    '{"en-us": "h relates the energy of a photon to its frequency (E = hν); an exact SI defining constant.", "cs-cz": "h spojuje energii fotonu s jeho frekvencí (E = hν); přesně definovaná SI konstanta."}',
    '["https://en.wikipedia.org/wiki/Planck_constant"]',
    6.62607015e-34,
    '[{"unit":"joule","exponent":1},{"unit":"second","exponent":1}]',
    'angular_momentum'),
  ('vacuum_permittivity',    '{"en-us": "Vacuum permittivity", "cs-cz": "Permitivita vakua"}', '\varepsilon_0', 6,
    '{"en-us": "ε₀ quantifies how strong an electric field a charge produces in vacuum; ε₀ = 1/(μ₀c²) ≈ 8.854×10⁻¹² F/m.", "cs-cz": "ε₀ udává, jak silné elektrické pole vytvoří náboj ve vakuu; ε₀ = 1/(μ₀c²) ≈ 8,854×10⁻¹² F/m."}',
    '["https://en.wikipedia.org/wiki/Vacuum_permittivity"]',
    8.8541878188e-12,
    '[{"unit":"farad","exponent":1},{"unit":"metre","exponent":-1}]',
    'permittivity'),
  ('vacuum_permeability',    '{"en-us": "Vacuum permeability", "cs-cz": "Permeabilita vakua"}', '\mu_0', 7,
    '{"en-us": "μ₀ characterises the magnetic response of vacuum; μ₀ ≈ 1.257×10⁻⁶ H/m.", "cs-cz": "μ₀ charakterizuje magnetické chování vakua; μ₀ ≈ 1,257×10⁻⁶ H/m."}',
    '["https://en.wikipedia.org/wiki/Vacuum_permeability"]',
    1.25663706127e-6,
    '[{"unit":"henry","exponent":1},{"unit":"metre","exponent":-1}]',
    'permeability'),
  ('boltzmann_constant',     '{"en-us": "Boltzmann constant", "cs-cz": "Boltzmannova konstanta"}', 'k_\mathrm{B}', 6,
    '{"en-us": "k_B relates the average energy of particles to temperature; an exact SI defining constant.", "cs-cz": "k_B spojuje střední energii částic s teplotou; přesně definovaná SI konstanta."}',
    '["https://en.wikipedia.org/wiki/Boltzmann_constant"]',
    1.380649e-23,
    '[{"unit":"joule","exponent":1},{"unit":"kelvin","exponent":-1}]',
    'entropy'),
  ('elementary_charge',      '{"en-us": "Elementary charge", "cs-cz": "Elementární náboj"}', 'e', 7,
    '{"en-us": "e is the electric charge carried by a single proton; an exact SI defining constant.", "cs-cz": "e je elektrický náboj jednoho protonu; přesně definovaná SI konstanta."}',
    '["https://en.wikipedia.org/wiki/Elementary_charge"]',
    1.602176634e-19,
    '[{"unit":"coulomb","exponent":1}]',
    'charge'),
  ('standard_gravity',       '{"en-us": "Standard gravity", "cs-cz": "Normální tíhové zrychlení"}', 'g_0', 3,
    '{"en-us": "g₀ is the nominal gravitational acceleration at sea level on Earth, defined as 9.80665 m/s².", "cs-cz": "g₀ je normované gravitační zrychlení na hladině moře na Zemi, definované jako 9,80665 m/s²."}',
    '["https://en.wikipedia.org/wiki/Standard_gravity"]',
    9.80665,
    '[{"unit":"metre","exponent":1},{"unit":"second","exponent":-2}]',
    'acceleration'),
  ('coulomb_constant',       '{"en-us": "Coulomb constant", "cs-cz": "Coulombova konstanta"}', 'k_\mathrm{e}', 6,
    '{"en-us": "k_e is the proportionality factor in Coulomb''s law, k_e = 1/(4πε₀) ≈ 8.988×10⁹ N m² C⁻².", "cs-cz": "k_e je koeficient proporcionality v Coulombově zákoně, k_e = 1/(4πε₀) ≈ 8,988×10⁹ N m² C⁻²."}',
    '["https://en.wikipedia.org/wiki/Coulomb_constant"]',
    8987551786.17,
    '[{"unit":"newton","exponent":1},{"unit":"metre","exponent":2},{"unit":"coulomb","exponent":-2}]',
    NULL),
  ('rydberg_constant',       '{"en-us": "Rydberg constant", "cs-cz": "Rydbergova konstanta"}', 'R_\mathrm{H}', 8,
    '{"en-us": "R_H gives the limiting wavenumber of photons emitted by electron transitions in hydrogen.", "cs-cz": "R_H udává mezní vlnové číslo fotonů emitovaných při přechodech elektronů v atomu vodíku."}',
    '["https://en.wikipedia.org/wiki/Rydberg_constant"]',
    10973731.568160,
    '[{"unit":"metre","exponent":-1}]',
    'wavenumber'),
  ('wiens_constant',         '{"en-us": "Wien''s displacement constant", "cs-cz": "Wienova konstanta"}', 'b', 8,
    '{"en-us": "b gives the peak wavelength of black-body radiation for a given temperature, λ_max = b/T.", "cs-cz": "b udává vlnovou délku maxima záření absolutně černého tělesa při dané teplotě, λ_max = b/T."}',
    '["https://en.wikipedia.org/wiki/Wien%27s_displacement_law"]',
    0.002897771955,
    '[{"unit":"metre","exponent":1},{"unit":"kelvin","exponent":1}]',
    NULL),
  ('celsius_zero',           '{"en-us": "Celsius zero in Kelvin", "cs-cz": "Nula Celsia v Kelvinech"}', '273.15', 3,
    '{"en-us": "The zero point of the Celsius scale expressed in kelvin; 0 °C = 273.15 K by definition.", "cs-cz": "Nulový bod Celsiovy stupnice vyjádřený v kelvinech; 0 °C = 273,15 K podle definice."}',
    '["https://en.wikipedia.org/wiki/Celsius"]',
    273.15,
    '[{"unit":"kelvin","exponent":1}]',
    'temperature'),
  ('faraday_constant',       '{"en-us": "Faraday constant", "cs-cz": "Faradayova konstanta"}', 'F', 8,
    '{"en-us": "F is the magnitude of electric charge per mole of electrons, F = N_A·e ≈ 96 485 C/mol.", "cs-cz": "F je velikost elektrického náboje jednoho molu elektronů, F = N_A·e ≈ 96 485 C/mol."}',
    '["https://en.wikipedia.org/wiki/Faraday_constant"]',
    96485.33212331002,
    '[{"unit":"coulomb","exponent":1},{"unit":"mole","exponent":-1}]',
    NULL),
  ('hubble_constant',        '{"en-us": "Hubble constant", "cs-cz": "Hubbleova konstanta"}', 'H_0', 8,
    '{"en-us": "H₀ is the present rate of expansion of the universe in Hubble''s law, v = H₀·d.", "cs-cz": "H₀ je současná rychlost rozpínání vesmíru v Hubbleově zákoně, v = H₀·d."}',
    '["https://en.wikipedia.org/wiki/Hubble%27s_law"]',
    2.1927112672380574e-18,
    '[{"unit":"second","exponent":-1}]',
    'frequency'),
  ('stefan_boltzmann_constant', '{"en-us": "Stefan-Boltzmann constant", "cs-cz": "Stefanova-Boltzmannova konstanta"}', '\sigma', 9,
    '{"en-us": "σ appears in the Stefan–Boltzmann law for the power radiated by a black body, j = σT⁴.", "cs-cz": "σ vystupuje ve Stefan–Boltzmannově zákoně pro výkon vyzařovaný absolutně černým tělesem, j = σT⁴."}',
    '["https://en.wikipedia.org/wiki/Stefan%E2%80%93Boltzmann_constant"]',
    5.670374419e-8,
    '[{"unit":"watt","exponent":1},{"unit":"metre","exponent":-2},{"unit":"kelvin","exponent":-4}]',
    NULL),
  ('bohr_radius',               '{"en-us": "Bohr radius", "cs-cz": "Bohrův poloměr"}', 'a_0', 8,
    '{"en-us": "a₀ is the most probable distance between the electron and the nucleus in a ground-state hydrogen atom.", "cs-cz": "a₀ je nejpravděpodobnější vzdálenost mezi elektronem a jádrem vodíkového atomu v základním stavu."}',
    '["https://en.wikipedia.org/wiki/Bohr_radius"]',
    5.29177210544e-11,
    '[{"unit":"metre","exponent":1}]',
    'length')
;


INSERT OR IGNORE INTO si_prefix (id, symbol, name, exponent) VALUES
  ('quetta',  'Q',    '{"en-us": "Quetta"}', 30),
  ('ronna',   'R',    '{"en-us": "Ronna"}', 27),
  ('yotta',   'Y',    '{"en-us": "Yotta", "cs-cz": "Jota"}', 24),
  ('zetta',   'Z',    '{"en-us": "Zetta", "cs-cz": "Zetta"}', 21),
  ('exa',     'E',    '{"en-us": "Exa", "cs-cz": "Exa"}', 18),
  ('peta',    'P',    '{"en-us": "Peta", "cs-cz": "Peta"}', 15),
  ('tera',    'T',    '{"en-us": "Tera", "cs-cz": "Tera"}', 12),
  ('giga',    'G',    '{"en-us": "Giga", "cs-cz": "Giga"}', 9),
  ('mega',    'M',    '{"en-us": "Mega", "cs-cz": "Mega"}', 6),
  ('kilo',    'k',    '{"en-us": "Kilo", "cs-cz": "Kilo"}', 3),
  ('hecto',   'h',    '{"en-us": "Hecto", "cs-cz": "Hekto"}', 2),
  ('deca',    'da',   '{"en-us": "Deca", "cs-cz": "Deka"}', 1),
  ('deci',    'd',    '{"en-us": "Deci", "cs-cz": "Deci"}', -1),
  ('centi',   'c',    '{"en-us": "Centi", "cs-cz": "Centi"}', -2),
  ('milli',   'm',    '{"en-us": "Milli", "cs-cz": "Milli"}', -3),
  ('micro',   '\mu',  '{"en-us": "Micro", "cs-cz": "Mikro"}', -6),
  ('nano',    'n',    '{"en-us": "Nano", "cs-cz": "Nano"}', -9),
  ('pico',    'p',    '{"en-us": "Pico", "cs-cz": "Piko"}', -12),
  ('femto',   'f',    '{"en-us": "Femto", "cs-cz": "Femto"}', -15),
  ('atto',    'a',    '{"en-us": "Atto", "cs-cz": "Atto"}', -18),
  ('zepto',   'z',    '{"en-us": "Zepto", "cs-cz": "Zepto"}', -21),
  ('yocto',   'y',    '{"en-us": "Yocto", "cs-cz": "Jokto"}', -24),
  ('ronto',   'r',    '{"en-us": "Ronto"}', -27),
  ('quecto',  'q',    '{"en-us": "Quecto"}', -30);
