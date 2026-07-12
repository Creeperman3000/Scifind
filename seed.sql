-- ============================================================
-- Consolidated seed data: quantities, units, formulas, items, relations
-- ============================================================

INSERT OR IGNORE INTO quantity (id, name, symbol, symbol_overwrite, topic, difficulty, description, links, default_unit, dim_M, dim_L, dim_T, dim_I, dim_Θ, dim_N, dim_J) VALUES
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
  ('concentration', '{"en-us": "Concentration", "cs-cz": "Koncentrace"}', 'c', NULL, 'solutions', 2, NULL, NULL, '[{"unit":"mole","exponent":1},{"unit":"metre","exponent":-3}]', 0.0, -3.0, 0.0, 0.0, 0.0, 1.0, 0.0),
  ('conductance', '{"en-us": "Electrical conductance", "cs-cz": "Elektrická vodivost"}', 'G', NULL, 'circuits', 3, NULL, NULL, '[{"unit": "siemens", "exponent": 1}]', -1.0, -2.0, 3.0, 2.0, 0.0, 0.0, 0.0),
  ('current', '{"en-us": "Electric current", "cs-cz": "Elektrický proud"}', 'I', NULL, 'current_electricity', 2, NULL, NULL, '[{"unit": "ampere", "exponent": 1}]', 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
  ('current_density', '{"en-us": "Current density", "cs-cz": "Hustota proudu"}', 'j', NULL, 'circuits', 3, NULL, NULL, '[{"unit":"ampere","exponent":1},{"unit":"metre","exponent":-2}]', 0.0, -2.0, 0.0, 1.0, 0.0, 0.0, 0.0),
  ('degree_of_polarization', '{"en-us": "Degree of polarization", "cs-cz": "Stupeň polarizace"}', 'P', NULL, 'polarization', 4, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('density', '{"en-us": "Density", "cs-cz": "Hustota"}', '\rho', NULL, 'fluid_mechanics', 2, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":-3}]', 1.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('dose_equivalent', '{"en-us": "Dose equivalent", "cs-cz": "Dávkový ekvivalent"}', 'H', NULL, 'nuclear_physics', 4, NULL, NULL, '[{"unit": "sievert", "exponent": 1}]', 0.0, 2.0, -2.0, 0.0, 0.0, 0.0, 0.0),
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
  ('gas_constant', '{"en-us": "Gas constant", "cs-cz": "Molární plynová konstanta"}', 'R', NULL, 'ideal_gases', 4, NULL, NULL, '[{"unit": "joule", "exponent": 1}, {"unit": "mole", "exponent": -1}, {"unit": "kelvin", "exponent": -1}]', 1.0, 2.0, -2.0, 0.0, 0.0, -1.0, 0.0),
  ('gravitational_constant', '{"en-us": "Gravitational constant", "cs-cz": "Gravitační konstanta"}', 'G', NULL, 'gravitation', 4, NULL, NULL, '[{"unit": "metre", "exponent": 3}, {"unit": "kilogram", "exponent": -1}, {"unit": "second", "exponent": -2}]', -1.0, 3.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('heat_engine_efficiency', '{"en-us": "Heat engine efficiency", "cs-cz": "Účinnost tepelného stroje"}', '\eta', NULL, 'heat_engines', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('illuminance', '{"en-us": "Illuminance", "cs-cz": "Osvětlení"}', 'E_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit": "lux", "exponent": 1}]', 0.0, -2.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('inductance', '{"en-us": "Inductance", "cs-cz": "Indukčnost"}', 'L', NULL, 'circuits', 3, NULL, NULL, '[{"unit": "henry", "exponent": 1}]', 1.0, 2.0, -2.0, -2.0, 0.0, 0.0, 0.0),
  ('irradiance', '{"en-us": "Irradiance", "cs-cz": "Intenzita záření"}', 'E', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit":"watt","exponent":1},{"unit":"metre","exponent":-2}]', 1.0, 0.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('length', '{"en-us": "Length", "cs-cz": "Délka"}', 'l', NULL, 'kinematics', 1, NULL, NULL, '[{"unit": "metre", "exponent": 1}]', 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('luminance', '{"en-us": "Luminance", "cs-cz": "Svítivost"}', 'L_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit":"candela","exponent":1},{"unit":"metre","exponent":-2}]', 0.0, -2.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('luminous_flux', '{"en-us": "Luminous flux", "cs-cz": "Světelný tok"}', '\Phi_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit": "lumen", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('luminous_intensity', '{"en-us": "Luminous intensity", "cs-cz": "Svítivost"}', 'I_v', NULL, 'electromagnetic_waves', 3, NULL, NULL, '[{"unit": "candela", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
  ('logarithmic_ratio', '{"en-us": "Logarithmic ratio", "cs-cz": "Logaritmický podíl"}', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('magnetic_field_strength', '{"en-us": "Magnetic field strength", "cs-cz": "Intenzita magnetického pole"}', 'H', NULL, 'magnetism', 3, NULL, NULL, '[{"unit":"ampere","exponent":1},{"unit":"metre","exponent":-1}]', 0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0),
  ('magnetic_flux', '{"en-us": "Magnetic flux", "cs-cz": "Magnetický tok"}', '\Phi', NULL, 'magnetism', 3, NULL, NULL, '[{"unit": "weber", "exponent": 1}]', 1.0, 2.0, -2.0, -1.0, 0.0, 0.0, 0.0),
  ('magnetic_flux_density', '{"en-us": "Magnetic flux density", "cs-cz": "Magnetická indukce"}', 'B', NULL, 'magnetism', 3, NULL, NULL, '[{"unit": "tesla", "exponent": 1}]', 1.0, 0.0, -2.0, -1.0, 0.0, 0.0, 0.0),
  ('mass', '{"en-us": "Mass", "cs-cz": "Hmotnost"}', 'm', NULL, 'dynamics', 1, NULL, NULL, '[{"unit": "kilogram", "exponent": 1}]', 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('mass_concentration', '{"en-us": "Mass concentration", "cs-cz": "Hmotnostní koncentrace"}', '\gamma', NULL, 'solutions', 3, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":-3}]', 1.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('molar_energy', '{"en-us": "Molar energy", "cs-cz": "Molární energie"}', 'E_m', NULL, 'thermochemistry', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"mole","exponent":-1}]', 1.0, 2.0, -2.0, 0.0, 0.0, -1.0, 0.0),
  ('molar_entropy', '{"en-us": "Molar entropy", "cs-cz": "Molární entropie"}', 'S_m', NULL, 'thermochemistry', 3, NULL, NULL, '[{"unit":"joule","exponent":1},{"unit":"mole","exponent":-1},{"unit":"kelvin","exponent":-1}]', 1.0, 2.0, -2.0, 0.0, -1.0, -1.0, 0.0),
  ('molar_mass', '{"en-us": "Molar mass", "cs-cz": "Molární hmotnost"}', 'M', NULL, 'molar_mass', 2, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"mole","exponent":-1}]', 1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0),
  ('moment_of_inertia', '{"en-us": "Moment of inertia", "cs-cz": "Moment setrvačnosti"}', 'I', NULL, 'moment_of_inertia', 3, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":2}]', 1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('momentum', '{"en-us": "Momentum", "cs-cz": "Hybnost"}', 'p', NULL, 'dynamics', 2, NULL, NULL, '[{"unit":"kilogram","exponent":1},{"unit":"metre","exponent":1},{"unit":"second","exponent":-1}]', 1.0, 1.0, -1.0, 0.0, 0.0, 0.0, 0.0),
  ('permeability', '{"en-us": "Permeability", "cs-cz": "Permeabilita"}', '\mu', NULL, 'magnetism', 4, NULL, NULL, '[{"unit":"henry","exponent":1},{"unit":"metre","exponent":-1}]', 1.0, 1.0, -2.0, -2.0, 0.0, 0.0, 0.0),
  ('permittivity', '{"en-us": "Permittivity", "cs-cz": "Permitivita"}', '\varepsilon', NULL, 'electrostatics', 4, NULL, NULL, '[{"unit":"farad","exponent":1},{"unit":"metre","exponent":-1}]', -1.0, -3.0, 4.0, 2.0, 0.0, 0.0, 0.0),
  ('power', '{"en-us": "Power", "cs-cz": "Výkon"}', 'P', NULL, 'work_and_energy', 2, NULL, NULL, '[{"unit": "watt", "exponent": 1}]', 1.0, 2.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('pressure', '{"en-us": "Pressure", "cs-cz": "Tlak"}', 'P', NULL, 'ideal_gases', 3, NULL, NULL, '[{"unit": "pascal", "exponent": 1}]', 1.0, -1.0, -2.0, 0.0, 0.0, 0.0, 0.0),
  ('radiance', '{"en-us": "Radiance", "cs-cz": "Záře"}', 'L_e', NULL, 'electromagnetic_waves', 4, NULL, NULL, '[{"unit":"watt","exponent":1},{"unit":"metre","exponent":-2},{"unit":"steradian","exponent":-1}]', 1.0, 0.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('radiant_intensity', '{"en-us": "Radiant intensity", "cs-cz": "Zářivost"}', 'I_e', NULL, 'electromagnetic_waves', 4, NULL, NULL, '[{"unit":"watt","exponent":1},{"unit":"steradian","exponent":-1}]', 1.0, 2.0, -3.0, 0.0, 0.0, 0.0, 0.0),
  ('reflectance', '{"en-us": "Reflectance", "cs-cz": "Reflexní schopnost"}', 'R', NULL, 'reflection', 2, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('refractive_index', '{"en-us": "Refractive index", "cs-cz": "Index lomu"}', 'n', NULL, 'refraction', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('resistance', '{"en-us": "Resistance", "cs-cz": "Elektrický odpor"}', 'R', NULL, 'circuits', 3, NULL, NULL, '[{"unit": "ohm", "exponent": 1}]', 1.0, 2.0, -3.0, -2.0, 0.0, 0.0, 0.0),
  ('reynolds_number', '{"en-us": "Reynolds number", "cs-cz": "Reynoldsovo číslo"}', '\mathit{Re}', NULL, 'reynolds_number', 3, NULL, NULL, NULL, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
  ('solid_angle', '{"en-us": "Solid angle", "cs-cz": "Prostorový úhel"}', '\Omega', NULL, 'trigonometric_identities', 2, NULL, NULL, '[{"unit": "steradian", "exponent": 1}]', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
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

INSERT OR IGNORE INTO formula (id, name, topic, difficulty, description) VALUES
  ('acids_and_bases', '{"en-us": "Acids And Bases", "cs-cz": "Kyseliny a zásady"}', 'acids_and_bases', 2, '{"en-us": "The pH equals the negative logarithm of the hydrogen ion concentration.", "cs-cz": "pH se rovná zápornému logaritmu koncentrace vodíkových iontů."}'),
  ('angular_momentum', '{"en-us": "Angular Momentum", "cs-cz": "Moment hybnosti"}', 'angular_momentum', 2, '{"en-us": "Angular momentum equals the product of moment of inertia and angular velocity.", "cs-cz": "Úhlový moment se rovná součinu momentu setrvačnosti a úhlové rychlosti."}'),
  ('archimedes_principle', '{"en-us": "Archimedes'' principle", "cs-cz": "Archimédův zákon"}', 'buoyancy', 3, '{"en-us": "The buoyant force on a submerged object equals the weight of the fluid displaced.", "cs-cz": "Vztlaková síla na ponořeném tělese se rovná hmotnosti vytlačené kapaliny."}'),
  ('area', '{"en-us": "Area", "cs-cz": "Plocha"}', 'plane_geometry', 2, '{"en-us": "The area of a square equals the square of its side length.", "cs-cz": "Obsah čtverce se rovná druhé mocně jeho strany."}'),
  ('atomic_physics', '{"en-us": "Atomic Physics", "cs-cz": "Atomová fyzika"}', 'atomic_physics', 2, '{"en-us": "The energy of a photon equals Planck''s constant times its frequency.", "cs-cz": "Energie fotonu se rovná Planckově konstantě vynásobené jeho frekvencí."}'),
  ('atomic_structure', '{"en-us": "Atomic Structure", "cs-cz": "Atomová struktura"}', 'atomic_structure', 2, '{"en-us": "Atoms consist of protons, neutrons, and electrons arranged in a nucleus and orbiting shells.", "cs-cz": "Atomy se skládají z protonů, neutronů a elektronů uspořádaných v jádře a obíhajících kolem něj."}'),
  ('bernoulli_equation', '{"en-us": "Bernoulli''s equation", "cs-cz": "Bernoulliho rovnice"}', 'bernoulli_equation', 4, '{"en-us": "For an ideal fluid, the sum of pressure, kinetic energy per volume, and potential energy per volume is constant along a streamline.", "cs-cz": "Pro ideální kapalinu je součet tlaku, kinetické energie na objem a potenciální energie na objem konstantní podél proudovice."}'),
  ('capacitance', '{"en-us": "Capacitance", "cs-cz": "Kapacita"}', 'capacitance', 2, '{"en-us": "Capacitance equals the charge stored per unit electric potential difference.", "cs-cz": "Kapacita se rovná uloženému náboji na jednotku elektrického potenciálového rozdílu."}'),
  ('centripetal_acceleration', '{"en-us": "Centripetal acceleration", "cs-cz": "Dostředivé zrychlení"}', 'circular_motion', 3, '{"en-us": "The centripetal acceleration of an object moving in a circle equals the square of its velocity divided by the radius.", "cs-cz": "Odstredivé zrychlení tělesa pohybujícího se po kružnici se rovná druhé mocně rychlosti dělené poloměrem."}'),
  ('chemical_bonding', '{"en-us": "Chemical Bonding", "cs-cz": "Chemická vazba"}', 'chemical_bonding', 2, '{"en-us": "Atoms bond together by sharing or transferring electrons to achieve stable electron configurations.", "cs-cz": "Atomy se vážou sdílením nebo přenosem elektronů za účelem dosažení stabilní elektronové konfigurace."}'),
  ('chemical_equilibrium', '{"en-us": "Chemical Equilibrium", "cs-cz": "Chemická rovnováha"}', 'chemical_equilibrium', 2, '{"en-us": "The equilibrium constant equals the ratio of product concentrations to reactant concentrations.", "cs-cz": "Konstanta chemické rovnováhy se rovná poměru koncentrací produktů a reaktantů."}'),
  ('chemical_kinetics', '{"en-us": "Chemical Kinetics", "cs-cz": "Chemická kinetika"}', 'chemical_kinetics', 2, '{"en-us": "The rate of a chemical reaction equals the rate constant times the concentration of reactants.", "cs-cz": "Rychlost chemické reakce se rovná rychlostní konstantě vynásobené koncentracemi reaktantů."}'),
  ('chemical_reactions', '{"en-us": "Chemical Reactions", "cs-cz": "Chemické reakce"}', 'chemical_reactions', 2, '{"en-us": "Chemical reactions involve the rearrangement of atoms to form new substances.", "cs-cz": "Chemické reakce zahrnují přeskupování atomů za vzniku nových látek."}'),
  ('circle_area', '{"en-us": "Area of a circle", "cs-cz": "Obsah kruhu"}', 'circles', 1, '{"en-us": "The area of a circle is pi times the radius squared.", "cs-cz": "Obsah kruhu se rovná π krát poloměr na druhou."}'),
  ('circle_circumference', '{"en-us": "Circumference of a circle", "cs-cz": "Obvod kruhu"}', 'circles', 1, '{"en-us": "The circumference of a circle is 2 pi times the radius.", "cs-cz": "Obvod kruhu se rovná 2π krát poloměr."}'),
  ('conservation_of_momentum', '{"en-us": "Conservation of momentum", "cs-cz": "Zákon zachování hybnosti"}', 'dynamics', 2, '{"en-us": "In a closed system, total momentum before a collision equals total momentum after.", "cs-cz": "V uzavřeném systému se celkový hybnost před srážkou rovná celkovému hybnostu po srážce."}'),
  ('continuity_equation_fluid', '{"en-us": "Continuity equation for fluids", "cs-cz": "Rovnice kontinuity pro tekutiny"}', 'continuity_equation', 3, '{"en-us": "For an incompressible fluid, the product of cross-sectional area and velocity is constant along a streamline.", "cs-cz": "Pro nestlačitelnou kapalinu je součin průřezové plochy a rychlosti konstantní."}'),
  ('coordinate_geometry', '{"en-us": "Coordinate Geometry", "cs-cz": "Analytická geometrie"}', 'coordinate_geometry', 2, '{"en-us": "The slope of a line equals the change in y divided by the change in x.", "cs-cz": "Sklon přímky se rovná změně y dělené změnou x."}'),
  ('density_formula', '{"en-us": "Density", "cs-cz": "Hustota"}', 'buoyancy', 1, '{"en-us": "Density equals mass divided by volume.", "cs-cz": "Hustota se rovná hmotnosti dělené objemem."}'),
  ('derivative_power', '{"en-us": "Power rule for derivatives", "cs-cz": "Derivace mocniny"}', 'derivatives', 2, '{"en-us": "The derivative of x to the power n is n times x to the power n minus one.", "cs-cz": "Derivace x na mocninu n se rovná n krát x na mocninu n minus jedna."}'),
  ('differential_equations', '{"en-us": "Differential Equations", "cs-cz": "Diferenciální rovnice"}', 'differential_equations', 2, '{"en-us": "A differential equation relates a function to its derivatives, describing rates of change.", "cs-cz": "Diferenciální rovnice popisuje vztah funkce k jejím derivacím a umožňuje popsat změny v čase."}'),
  ('diffraction', '{"en-us": "Diffraction", "cs-cz": "Difrakce"}', 'diffraction', 2, '{"en-us": "For single-slit diffraction minima, the sine of the angle equals the wavelength divided by the slit width.", "cs-cz": "Pro minima difrakce na jedné štěrbině se sin úhlu rovná vlnové délce dělené šířkou štěrbiny."}'),
  ('einstein_emc2', '{"en-us": "Mass-energy equivalence", "cs-cz": "Ekvivalence hmotnosti a energie"}', 'relativity', 4, '{"en-us": "Energy equals mass times the speed of light squared.", "cs-cz": "Energie se rovná hmotnosti krát rychlost svěla na druhou."}'),
  ('electric_fields', '{"en-us": "Electric Fields", "cs-cz": "Elektrické pole"}', 'electric_fields', 2, '{"en-us": "Electric field strength equals the force per unit charge.", "cs-cz": "Intenzita elektrického pole se rovná síle na jednotku náboje."}'),
  ('electrochemistry', '{"en-us": "Electrochemistry", "cs-cz": "Elektrochemie"}', 'electrochemistry', 2, '{"en-us": "The standard cell potential equals the difference between the cathode and anode standard potentials.", "cs-cz": "Standardní buněčný potenciál se rovná rozdílu mezi katodovým a anodovým potenciálem."}'),
  ('electromagnetic_induction', '{"en-us": "Electromagnetic Induction", "cs-cz": "Elektromagnetická indukce"}', 'electromagnetic_induction', 2, '{"en-us": "The induced electromotive force equals negative the rate of change of magnetic flux.", "cs-cz": "Indukované elektromotorické napětí se rovná záporné změně magnetického toku v čase."}'),
  ('electromagnetic_waves', '{"en-us": "Electromagnetic Waves", "cs-cz": "Elektromagnetické vlnění"}', 'electromagnetic_waves', 2, '{"en-us": "The speed of an electromagnetic wave equals frequency times wavelength.", "cs-cz": "Rychlost elektromagnetické vlny se rovná frekvenci krát vlnová délka."}'),
  ('entropy', '{"en-us": "Entropy", "cs-cz": "Entropie"}', 'entropy', 2, '{"en-us": "The change in entropy equals heat transferred divided by temperature.", "cs-cz": "Změna entropie se rovná přenesenému teplu dělenému teplotou."}'),
  ('escape_velocity', '{"en-us": "Escape Velocity", "cs-cz": "Úniková rychlost"}', 'escape_velocity', 2, '{"en-us": "Escape velocity equals the square root of twice the gravitational constant times mass divided by radius.", "cs-cz": "Úniková rychlost se rovná odmocnině ze dvou krát gravitační konstanta krát poloměr."}'),
  ('exponents', '{"en-us": "Exponents", "cs-cz": "Mocniny"}', 'exponents', 2, '{"en-us": "Exponents indicate repeated multiplication of a base number by itself.", "cs-cz": "Exponenty označují opakované násobení základního čísla sebou samým."}'),
  ('first_law_thermodynamics', '{"en-us": "First law of thermodynamics", "cs-cz": "První termodynamický zákon"}', 'first_law', 3, '{"en-us": "The change in internal energy of a system equals heat added to the system minus work done by the system.", "cs-cz": "Změna vnitřní energie systému se rovná teplu přidanému do systému minus práci vykonané systémem."}'),
  ('first_law_thermodynamics_adiabatic', '{"en-us": "First law (adiabatic): ΔU = −W", "cs-cz": "První zákon (adiabatický): ΔU = −W"}', 'first_law', 3, '{"en-us": "For an adiabatic process, no heat is exchanged so the change in internal energy equals negative work.", "cs-cz": "Pro adiabatický proces nedochází k výměně tepla, takže změna vnitřní energie se rovná práci."}'),
  ('first_law_thermodynamics_isochoric', '{"en-us": "First law (isochoric): ΔU = Q", "cs-cz": "První zákon (izochorický): ΔU = Q"}', 'first_law', 3, '{"en-us": "For an isochoric process, no work is done so the change in internal energy equals the heat added.", "cs-cz": "Pro izochorický proces se nekoná žádná práce, takže změna vnitřní energie se rovná přenesenému teplu."}'),
  ('friction', '{"en-us": "Friction", "cs-cz": "Tření"}', 'friction', 2, '{"en-us": "The force of friction equals the product of the coefficient of friction and the normal force.", "cs-cz": "Třecí síla se rovná součinu koeficientu tření a normálové síly."}'),
  ('heat', '{"en-us": "Heat", "cs-cz": "Teplo"}', 'heat', 2, '{"en-us": "The heat transferred equals mass times specific heat capacity times the change in temperature.", "cs-cz": "Přenesené teplo se rovná hmotnosti krát měrná tepelná kapacita krát změna teploty."}'),
  ('heat_conduction', '{"en-us": "Heat conduction (Fourier''s law)", "cs-cz": "Vedení tepla (Fourierův zákon)"}', 'heat_transfer', 3, '{"en-us": "The rate of heat transfer through a material is proportional to its thermal conductivity, area, and temperature gradient.", "cs-cz": "Rychlost přenosu tepla materiálem je úměrná jeho tepelné vodivosti, ploše a teplotnímu rozdílu."}'),
  ('heat_engines', '{"en-us": "Heat Engines", "cs-cz": "Tepelné stroje"}', 'heat_engines', 2, '{"en-us": "The efficiency of a heat engine equals work output divided by heat input.", "cs-cz": "Účinnost tepelného stroje se rovná práci na výstupu dělenému teplu na vstupu."}'),
  ('hookes_law', '{"en-us": "Hooke''s law", "cs-cz": "Hookeův zákon"}', 'springs', 2, '{"en-us": "The force exerted by a spring is proportional to its displacement from equilibrium.", "cs-cz": "Síla, kterou pružina vyvíjí, je úměrná jejímu vychýlení z rovnovážné polohy."}'),
  ('ideal_gas_law', '{"en-us": "Ideal gas law", "cs-cz": "Stavová rovnice ideálního plynu"}', 'ideal_gases', 3, '{"en-us": "The pressure of an ideal gas times its volume equals the amount of gas times the gas constant times temperature.", "cs-cz": "Tlak ideálního plynu krát jeho objem se rovná množství plynu krát plynová konstanta krát teplota."}'),
  ('impulse', '{"en-us": "Impulse", "cs-cz": "Impuls síly"}', 'impulse', 2, '{"en-us": "Impulse equals the product of force and the time interval over which it acts.", "cs-cz": "Impuls se rovná součinu síly a časového intervalu, po který působí."}'),
  ('integral_power', '{"en-us": "Power rule for integrals", "cs-cz": "Integrál mocniny"}', 'integrals', 2, '{"en-us": "The integral of x to the power n is x to the power n plus one divided by n plus one.", "cs-cz": "Integrál x na mocninu n se rovná x na mocninu n plus jedna dělené n plus jedna."}'),
  ('interference', '{"en-us": "Interference", "cs-cz": "Interference"}', 'interference', 2, '{"en-us": "For double-slit interference, the slit separation times the sine of the angle equals an integer multiple of the wavelength.", "cs-cz": "Pro interferenci na dvou štěrbinách se součin šířky štěrbiny a sin úhlu rovná celočíselnému násobku vlnové délky."}'),
  ('keplers_third_law', '{"en-us": "Kepler''s third law", "cs-cz": "Třetí Keplerův zákon"}', 'orbital_motion', 4, '{"en-us": "The square of a planet''s orbital period is proportional to the cube of its semi-major axis.", "cs-cz": "Druhá mocná oběžné doby planety je úměrná třetí mocně velké poloosy její dráhy."}'),
  ('kinetic_energy', '{"en-us": "Kinetic energy", "cs-cz": "Kinetická energie"}', 'work_and_energy', 2, '{"en-us": "The kinetic energy of a body is half its mass times the square of its velocity.", "cs-cz": "Kinetická energie tělesa se rovná polovině jeho hmotnosti krát čtverec rychlosti."}'),
  ('laws_of_sines_and_cosines', '{"en-us": "Laws Of Sines And Cosines", "cs-cz": "Sinová a kosinová věta"}', 'laws_of_sines_and_cosines', 2, '{"en-us": "The ratio of a side length to the sine of its opposite angle is constant for all sides of a triangle.", "cs-cz": "Poměr délky strany k sinu protějšího úhlu je konstantní pro všechny strany a úhly trojúhelníku."}'),
  ('lens_equation', '{"en-us": "Thin lens equation", "cs-cz": "Zobrazovací rovnice tenké čočky"}', 'lenses', 3, '{"en-us": "The inverse of the focal length equals the sum of the inverse of the object distance and the inverse of the image distance.", "cs-cz": "Inverze ohniskové vzdálenosti se rovná součtu inverzí předmětové a obrazové vzdálenosti."}'),
  ('limiting_reactants', '{"en-us": "Limiting Reactants", "cs-cz": "Limitující reaktant"}', 'limiting_reactants', 2, '{"en-us": "The limiting reactant determines the maximum amount of product that can be formed in a reaction.", "cs-cz": "Limitující reaktant určuje maximální množství produktu, které lze vytvořit."}'),
  ('limits', '{"en-us": "Limits", "cs-cz": "Limity"}', 'limits', 2, '{"en-us": "A limit describes the value a function approaches as the input approaches a particular value.", "cs-cz": "Limita popisuje hodnotu, ke které se funkce blíží, jak se vstup blíží k určitému bodu."}'),
  ('logarithm_product', '{"en-us": "Logarithm of a product", "cs-cz": "Logaritmus součinu"}', 'logarithms', 2, '{"en-us": "The logarithm of a product equals the sum of the logarithms.", "cs-cz": "Logaritmus součinu se rovná součtu logaritmů."}'),
  ('mirrors', '{"en-us": "Mirrors", "cs-cz": "Zrcadla"}', 'mirrors', 2, '{"en-us": "The inverse of the focal length equals the sum of the inverses of the object and image distances.", "cs-cz": "Inverze ohniskové vzdálenosti se rovná součtu inverzí předmětové a obrazové vzdálenosti."}'),
  ('molarity_formula', '{"en-us": "Molarity", "cs-cz": "Molární koncentrace"}', 'solution_stoichiometry', 2, '{"en-us": "Molarity equals the number of moles of solute divided by the volume of solution in litres.", "cs-cz": "Molarita se rovná počtu molů látky dělenému objemu roztoku."}'),
  ('moles_from_mass', '{"en-us": "Moles from mass", "cs-cz": "Látkové množství z hmotnosti"}', 'mole_concept', 2, '{"en-us": "The number of moles equals the mass divided by the molar mass.", "cs-cz": "Počet molů se rovná hmotnosti dělené molární hmotností."}'),
  ('moment_of_inertia', '{"en-us": "Moment Of Inertia", "cs-cz": "Moment setrvačnosti"}', 'moment_of_inertia', 2, '{"en-us": "The moment of inertia of a point mass equals its mass times the square of its distance from the axis.", "cs-cz": "Moment setrvačnosti bodové hmoty se rovná její hmotnosti krát čtverec vzdálenosti od osy."}'),
  ('momentum_formula', '{"en-us": "Linear momentum", "cs-cz": "Lineární hybnost"}', 'linear_momentum', 1, '{"en-us": "The linear momentum of an object is its mass times its velocity.", "cs-cz": "Lineární hybnost tělesa se rovná jeho hmotnosti krát rychlost."}'),
  ('newton_second_law_of_motion', '{"en-us": "Newton''s second law of motion", "cs-cz": "Druhý Newtonův pohybový zákon"}', 'dynamics', 2, '{"en-us": "The net force on a body is equal to its mass times its acceleration.", "cs-cz": "Výsledná síla na tělese se rovná jeho hmotnosti krát zrychlení."}'),
  ('newtons_law_of_gravitation', '{"en-us": "Newton''s law of universal gravitation", "cs-cz": "Newtonův gravitační zákon"}', 'newtonian_gravity', 3, '{"en-us": "Every particle attracts every other particle with a force proportional to the product of their masses and inversely proportional to the square of the distance.", "cs-cz": "Každá částice přitahuje každou jinou částici silou úměrnou součinu jejich hmotností a nepřímo úměrnou druhé mocně vzdálenosti."}'),
  ('ohms_law', '{"en-us": "Ohm''s law", "cs-cz": "Ohmův zákon"}', 'circuits', 2, '{"en-us": "The current through a conductor is directly proportional to the voltage across it.", "cs-cz": "Proud vodičem je přímo úměrný napětí přes vodič."}'),
  ('parallel_resistance', '{"en-us": "Parallel resistance", "cs-cz": "Paralelní odpor"}', 'circuits', 3, '{"en-us": "The reciprocal of total resistance in parallel equals the sum of the reciprocals of individual resistances.", "cs-cz": "Inverze celkového odporu v paralelním zapojení se rovná součtu inverzí jednotlivých odporů."}'),
  ('particle_physics', '{"en-us": "Particle Physics", "cs-cz": "Fyzika částic"}', 'particle_physics', 2, '{"en-us": "The square of total relativistic energy equals the square of momentum times c squared plus the square of rest energy.", "cs-cz": "Druhá mocná celkové relativistické energie se rovná druhé mocně hybnosti krát c na druhou."}'),
  ('pascals_principle', '{"en-us": "Pascal''s principle", "cs-cz": "Pascalův princip"}', 'pascals_law', 3, '{"en-us": "A change in pressure applied to an enclosed fluid is transmitted undiminished throughout the fluid.", "cs-cz": "Změna tlaku aplikovaná na uzavřenou kapalinu se přenáší beze ztráty do všech částí kapaliny."}'),
  ('percent_yield', '{"en-us": "Percent Yield", "cs-cz": "Procentuální výtěžek"}', 'percent_yield', 2, '{"en-us": "Percent yield compares the actual product yield to the theoretical maximum yield.", "cs-cz": "Procentní výtěžnost srovnává skutečný výnos produktu s teoretickým maximem."}'),
  ('period_pendulum', '{"en-us": "Simple pendulum period", "cs-cz": "Perioda matematického kyvadla"}', 'harmonic_motion', 3, '{"en-us": "The period of a simple pendulum is proportional to the square root of its length over gravitational acceleration.", "cs-cz": "Doba kmitu jednoduchého kyvadla je úměrná odmocnině z jeho délky."}'),
  ('periodic_table', '{"en-us": "Periodic Table", "cs-cz": "Periodická tabulka"}', 'periodic_table', 2, '{"en-us": "The periodic table organises elements by atomic number, electron configuration, and chemical properties.", "cs-cz": "Periodická tabulka uspořádává prvky podle atomového čísla, elektronové konfigurace a chemických vlastností."}'),
  ('photoelectric_effect', '{"en-us": "Photoelectric effect", "cs-cz": "Fotoelektrický jev"}', 'quantum_mechanics', 4, '{"en-us": "The maximum kinetic energy of ejected electrons equals the photon energy minus the work function.", "cs-cz": "Maximální kinetická energie vyražených elektronů se rovná energii fotonu minus pracovní funkci."}'),
  ('plane_geometry', '{"en-us": "Plane Geometry", "cs-cz": "Planimetrie"}', 'plane_geometry', 2, '{"en-us": "The area of a triangle equals half the product of its base and height.", "cs-cz": "Obsah trojúhelníku se rovná polovině součinu základny a výšky."}'),
  ('polarization', '{"en-us": "Polarization", "cs-cz": "Polarizace"}', 'polarization', 2, '{"en-us": "At Brewster''s angle, the tangent of the angle equals the ratio of transmitted to incident refractive indices.", "cs-cz": "Brewsterově úhlu se rovná tangenta úhlu rovná poměru přenesené a odražené intenzity."}'),
  ('polygons', '{"en-us": "Polygons", "cs-cz": "Mnohoúhelníky"}', 'polygons', 2, '{"en-us": "The area of a regular polygon equals half the product of its perimeter and apothem.", "cs-cz": "Obsah pravidelného mnohoúhelníku se rovná polovině součinu obvodu a poloviny vnitřní výšky."}'),
  ('polynomials', '{"en-us": "Polynomials", "cs-cz": "Polynomy"}', 'polynomials', 2, '{"en-us": "A polynomial is an expression consisting of variables and coefficients combined using addition and multiplication.", "cs-cz": "Polynom je výraz skládající se z proměnných a koeficientů kombinovaných pomocí sčítání, násobení a umocňování."}'),
  ('potential_energy', '{"en-us": "Potential Energy", "cs-cz": "Potenciální energie"}', 'potential_energy', 2, '{"en-us": "Gravitational potential energy equals the product of mass, gravitational acceleration, and height.", "cs-cz": "Gravitační potenciální energie se rovná součinu hmotnosti, gravitačního zrychlení a výšky."}'),
  ('power_formula', '{"en-us": "Power", "cs-cz": "Výkon"}', 'power', 2, '{"en-us": "Power equals work divided by time.", "cs-cz": "Výkon se rovná práci dělené časem."}'),
  ('pressure', '{"en-us": "Pressure", "cs-cz": "Tlak"}', 'pressure', 2, '{"en-us": "Pressure equals force divided by area.", "cs-cz": "Tlak se rovná síle dělené plochou."}'),
  ('projectile_motion', '{"en-us": "Projectile Motion", "cs-cz": "Vrh"}', 'projectile_motion', 2, '{"en-us": "The horizontal range of a projectile equals the square of its initial velocity divided by gravitational acceleration.", "cs-cz": "Vodorovný dostřel projektiletu se rovná druhé mocně počáteční rychlosti dělené gravitačním zrychlením."}'),
  ('pythagorean_theorem', '{"en-us": "Pythagorean theorem", "cs-cz": "Pythagorova věta"}', 'triangles', 1, '{"en-us": "In a right triangle, the square of the hypotenuse equals the sum of the squares of the other two sides.", "cs-cz": "V pravoúhlém trojúhelníku se druhá mocná přepony rovná součtu druhých mocných odvěsen."}'),
  ('quadratic_formula', '{"en-us": "Quadratic formula", "cs-cz": "Kvadratická rovnice"}', 'equations', 2, '{"en-us": "The solutions to a quadratic equation are given by the quadratic formula.", "cs-cz": "Řešení kvadratické rovnice jsou dána kvadratickým vzorcem."}'),
  ('radioactive_decay', '{"en-us": "Radioactive decay law", "cs-cz": "Zákon radioaktivního rozpadu"}', 'nuclear_physics', 4, '{"en-us": "The number of radioactive nuclei decreases exponentially with time.", "cs-cz": "Počet radioaktivních jáder klesá exponenciálně s časem."}'),
  ('reflection', '{"en-us": "Reflection", "cs-cz": "Odraz"}', 'reflection', 2, '{"en-us": "The angle of incidence equals the angle of reflection.", "cs-cz": "Úhel dopadu se rovná úhlu odrazu."}'),
  ('reynolds_number', '{"en-us": "Reynolds Number", "cs-cz": "Reynoldsovo číslo"}', 'reynolds_number', 2, '{"en-us": "The Reynolds number equals density times velocity times characteristic length divided by dynamic viscosity.", "cs-cz": "Reynoldsovo číslo se rovná hustotě krát rychlost krát charakteristická délka dělené viskozitou."}'),
  ('rotational_energy', '{"en-us": "Rotational Energy", "cs-cz": "Rotační energie"}', 'rotational_energy', 2, '{"en-us": "Rotational kinetic energy equals half the moment of inertia times angular velocity squared.", "cs-cz": "Rotační kinetická energie se rovná polovině momentu setrvačnosti krát úhlová rychlost."}'),
  ('second_law_thermodynamics_clausius', '{"en-us": "Second law of thermodynamics (Clausius statement)", "cs-cz": "Druhý termodynamický zákon (Clausiova formulace)"}', 'second_law', 4, '{"en-us": "Heat cannot spontaneously flow from a colder body to a hotter body.", "cs-cz": "Teplo nemůže spontánně proudit z chladnějšího tělesa do teplejšího."}'),
  ('simple_harmonic_motion', '{"en-us": "Simple harmonic motion position", "cs-cz": "Poloha harmonického kmitání"}', 'harmonic_motion', 3, '{"en-us": "The position of an object in simple harmonic motion varies sinusoidally with time.", "cs-cz": "Poloha tělesa v jednoduchém harmonickém pohybu se mění sinusoidálně s časem."}'),
  ('snells_law', '{"en-us": "Snell''s law", "cs-cz": "Snellův zákon"}', 'refraction', 3, '{"en-us": "The ratio of sines of the angles of incidence and refraction equals the inverse ratio of refractive indices.", "cs-cz": "Poměr sinů úhlů dopadu a lomu se rovná inverzi indexu lomu."}'),
  ('surface_tension', '{"en-us": "Surface Tension", "cs-cz": "Povrchové napětí"}', 'surface_tension', 2, '{"en-us": "Surface tension equals force per unit length acting along a liquid surface.", "cs-cz": "Povrchové napětí se rovná síle na jednotku délky působící na povrchu kapaliny."}'),
  ('suvat_v2', '{"en-us": "Uniform acceleration equation", "cs-cz": "Rovnice rovnoměrně zrychleného pohybu"}', 'kinematics', 3, '{"en-us": "Final velocity squared equals initial velocity squared plus twice acceleration times displacement.", "cs-cz": "Druhá mocná konečné rychlosti se rovná druhé mocně počáteční rychlosti plus dvakrát zrychlení krát dráha."}'),
  ('trig_sin2_cos2', '{"en-us": "Pythagorean trigonometric identity", "cs-cz": "Základní goniometrická identita"}', 'trigonometric_identities', 1, '{"en-us": "The square of the sine plus the square of the cosine equals one.", "cs-cz": "Druhá mocná sinu plus druhá mocná kosinu se rovná jedné."}'),
  ('van_der_waals', '{"en-us": "Van der Waals equation of state", "cs-cz": "Van der Waalsova stavová rovnice"}', 'ideal_gases', 5, '{"en-us": "A more accurate equation of state for real gases that accounts for intermolecular forces and finite molecular size.", "cs-cz": "Přesnější rovnice stavu pro reálné plyny, která zohledňuje intermolekulární síly a objem molekul."}'),
  ('wave_equation', '{"en-us": "Universal wave equation", "cs-cz": "Obecná rovnice vlnění"}', 'mechanical_waves', 2, '{"en-us": "The speed of a wave equals its frequency times its wavelength.", "cs-cz": "Rychlost vlny se rovná její frekvenci krát vlnová délka."}'),
  ('wave_interference', '{"en-us": "Wave Interference", "cs-cz": "Interference vlnění"}', 'wave_interference', 2, '{"en-us": "For constructive interference, the path difference equals an integer multiple of the wavelength.", "cs-cz": "Pro konstruktivní interferenci se dráhový rozdíl rovná celočíselnému násobku vlnové délky."}'),
  ('work_formula', '{"en-us": "Work done by a force", "cs-cz": "Práce vykonaná silou"}', 'work', 2, '{"en-us": "The work done by a force equals the force times the displacement times the cosine of the angle between them.", "cs-cz": "Práce vykonaná silou se rovná síle krát dráha krát kosinus úhlu mezi nimi."}'),
  ('dimensions', '{"en-us": "Dimensions", "cs-cz": "Rozměry"}', NULL, NULL, NULL)
;

INSERT OR IGNORE INTO formula_item VALUES('acids_and_bases',1,0,0,NULL,NULL,1.0,'concentration',1.0,NULL,'[\mathrm{H}^{+}]','{"en-us": "Hydrogen ion [Concentration]", "cs-cz": "Vodíkový iont [Concentration]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('angular_momentum',1,0,0,NULL,NULL,1.0,'moment_of_inertia',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('angular_momentum',1,0,1,NULL,NULL,1.0,'angular_velocity',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('angular_momentum',1,1,0,NULL,NULL,1.0,'angular_momentum',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('archimedes_principle',1,0,0,NULL,NULL,1.0,'density',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('archimedes_principle',1,0,1,NULL,NULL,1.0,'gravitational_constant',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('archimedes_principle',1,0,2,NULL,NULL,1.0,'volume',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('archimedes_principle',1,1,0,NULL,NULL,1.0,'force',-1.0,NULL,'{"en-us": "F_b"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('area',1,0,0,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "s"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('area',1,1,0,NULL,NULL,1.0,'area',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('atomic_physics',1,0,0,NULL,NULL,1.0,'frequency',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('atomic_physics',1,1,0,NULL,NULL,1.0,'energy',-1.0,NULL,NULL,NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('atomic_structure',1,0,0,NULL,NULL,1.0,'charge',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('capacitance',1,0,0,NULL,NULL,1.0,'charge',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('capacitance',1,0,1,NULL,NULL,1.0,'electric_potential',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('capacitance',1,1,0,NULL,NULL,1.0,'capacitance',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('centripetal_acceleration',1,0,0,NULL,NULL,1.0,'velocity',2.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('centripetal_acceleration',1,0,1,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "r"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('centripetal_acceleration',1,1,0,NULL,NULL,1.0,'acceleration',-1.0,'{"en-us": "c"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_bonding',1,0,0,NULL,NULL,1.0,'charge',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_equilibrium',1,0,0,NULL,NULL,1.0,'concentration',1.0,NULL,'[\mathrm{C}]','{"en-us": "Product [Concentration]", "cs-cz": "Produkt [Concentration]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_equilibrium',1,0,1,NULL,NULL,1.0,'concentration',-1.0,NULL,'[\mathrm{A}]','{"en-us": "Reactant [Concentration]", "cs-cz": "Reaktant [Concentration]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_kinetics',1,0,0,NULL,NULL,1.0,'concentration',1.0,NULL,'[\mathrm{A}]',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_kinetics',1,0,1,NULL,NULL,1.0,'activity',1.0,NULL,'k','{"en-us": "Rate constant [activity]", "cs-cz": "Rychlostní konstanta [activity|aktivita]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('chemical_reactions',1,0,0,NULL,NULL,1.0,'mass',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_area',1,0,0,NULL,NULL,1.0,NULL,1.0,NULL,'{"en-us": "r"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_area',1,0,1,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "r"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_area',1,1,0,NULL,NULL,1.0,'area',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_circumference',1,0,0,2.0,NULL,1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_circumference',1,0,1,NULL,NULL,1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_circumference',1,0,2,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "r"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('circle_circumference',1,1,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "C"}','{"en-us": "Circumference"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',1,1,0,NULL,NULL,1.0,'mass',-1.0,'{"en-us": "1"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',1,1,1,NULL,NULL,1.0,'velocity',-1.0,'{"en-us": "1"}','{"en-us": "u"}','{"en-us": "Initial [velocity]", "cs-cz": "Počáteční [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',2,1,0,NULL,NULL,1.0,'mass',-1.0,'{"en-us": "2"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',2,1,1,NULL,NULL,1.0,'velocity',-1.0,'{"en-us": "2"}','{"en-us": "u"}','{"en-us": "Initial [velocity]", "cs-cz": "Počáteční [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',3,0,0,NULL,NULL,1.0,'mass',1.0,'{"en-us": "1"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',3,0,1,NULL,NULL,1.0,'velocity',1.0,'{"en-us": "1"}',NULL,'{"en-us": "Final [velocity]", "cs-cz": "Konečná [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',4,0,0,NULL,NULL,1.0,'mass',1.0,'{"en-us": "2"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('conservation_of_momentum',4,0,1,NULL,NULL,1.0,'velocity',1.0,'{"en-us": "2"}',NULL,'{"en-us": "Final [velocity]", "cs-cz": "Konečná [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('coordinate_geometry',1,0,0,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "y"}',NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('coordinate_geometry',1,0,1,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "x"}',NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('density_formula',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('density_formula',1,0,1,NULL,NULL,1.0,'volume',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('density_formula',1,1,0,NULL,NULL,1.0,'density',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('differential_equations',1,0,0,NULL,NULL,1.0,'length',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('diffraction',1,0,0,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "\\lambda"}','{"en-us": "Wave [length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('diffraction',1,0,1,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "d"}','{"en-us": "Slit separation"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('diffraction',1,1,0,NULL,NULL,1.0,'angle',1.0,NULL,NULL,NULL,'\sin',NULL);
INSERT OR IGNORE INTO formula_item VALUES('einstein_emc2',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('einstein_emc2',1,0,1,NULL,NULL,2.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('einstein_emc2',1,1,0,NULL,NULL,1.0,'energy',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electric_fields',1,0,0,NULL,NULL,1.0,'force',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electric_fields',1,0,1,NULL,NULL,1.0,'charge',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electric_fields',1,1,0,NULL,NULL,1.0,'electric_field_strength',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electrochemistry',1,0,0,NULL,NULL,1.0,'electric_potential',1.0,NULL,'E^\circ_\mathrm{cathode}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electrochemistry',1,1,0,NULL,NULL,1.0,'electric_potential',-1.0,NULL,'{"en-us": "E_\\mathrm{cell}"}','{"en-us": "Cell"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electrochemistry',2,0,0,-1.0,NULL,1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electrochemistry',2,0,1,NULL,NULL,1.0,'electric_potential',1.0,NULL,'E^\circ_\mathrm{anode}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_induction',1,0,0,NULL,NULL,1.0,'magnetic_flux',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_induction',1,0,1,NULL,NULL,1.0,'time',-1.0,NULL,NULL,NULL,'\mathrm{d}',NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_induction',1,1,0,-1.0,NULL,1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_waves',1,0,0,NULL,NULL,1.0,'frequency',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_waves',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "\\lambda"}','{"en-us": "Wave [length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('electromagnetic_waves',1,1,0,NULL,NULL,1.0,'velocity',-1.0,NULL,'{"en-us": "c"}','{"en-us": "Wave [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('entropy',1,0,0,NULL,NULL,1.0,'energy',1.0,NULL,'{"en-us": "Q"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('entropy',1,0,1,NULL,NULL,1.0,'temperature',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('entropy',1,1,0,NULL,NULL,1.0,'entropy',-1.0,NULL,NULL,NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('escape_velocity',1,0,0,2.0,NULL,1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('escape_velocity',1,0,1,NULL,NULL,1.0,'gravitational_constant',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('escape_velocity',1,0,2,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('escape_velocity',1,0,3,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "r"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('escape_velocity',1,1,0,NULL,NULL,1.0,'velocity',-1.0,NULL,'{"en-us": "v_\\mathrm{esc}"}','{"en-us": "Escape [Velocity]", "cs-cz": "Úniková [Velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('exponents',1,0,0,NULL,NULL,1.0,'length',0.0,NULL,'{"en-us": "x"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics',1,1,0,NULL,NULL,NULL,'energy',-1.0,NULL,'{"en-us": "U"}','{"en-us": "Internal [energy]", "cs-cz": "Vnitřní [energy|energie]"}','\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics',2,0,0,NULL,NULL,NULL,'energy',1.0,NULL,'{"en-us": "Q"}','{"en-us": "Heat", "cs-cz": "Teplo"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics',3,0,0,-1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics',3,0,1,NULL,NULL,NULL,'energy',1.0,NULL,'{"en-us": "W"}','{"en-us": "Work", "cs-cz": "Práce"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics_adiabatic',1,1,0,NULL,NULL,NULL,'energy',-1.0,NULL,'{"en-us": "U"}','{"en-us": "Internal [energy]", "cs-cz": "Vnitřní [energy|energie]"}','\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics_adiabatic',2,0,0,-1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics_adiabatic',2,0,1,NULL,NULL,NULL,'energy',1.0,NULL,'{"en-us": "W"}','{"en-us": "Work", "cs-cz": "Práce"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics_isochoric',1,1,0,NULL,NULL,1.0,'energy',-1.0,NULL,'{"en-us": "U"}','{"en-us": "Internal [energy]", "cs-cz": "Vnitřní [energy|energie]"}','\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('first_law_thermodynamics_isochoric',2,0,0,NULL,NULL,1.0,'energy',1.0,NULL,'{"en-us": "Q"}','{"en-us": "Heat", "cs-cz": "Teplo"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('friction',1,0,0,NULL,NULL,1.0,'force',1.0,NULL,'{"en-us": "N"}','{"en-us": "Normal [force]", "cs-cz": "Normálová [force|síla]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('friction',1,1,0,NULL,NULL,1.0,'force',-1.0,NULL,'F_\mathrm{f}','{"en-us": "Friction [force]", "cs-cz": "Třecí [force|síla]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat',1,0,1,NULL,NULL,1.0,'specific_heat_capacity',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat',1,0,2,NULL,NULL,1.0,'temperature',1.0,NULL,NULL,NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat',1,1,0,NULL,NULL,1.0,'energy',-1.0,NULL,'{"en-us": "Q"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_conduction',1,0,0,NULL,NULL,1.0,'thermal_conductivity',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_conduction',1,0,1,NULL,NULL,1.0,'area',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_conduction',1,0,2,NULL,NULL,1.0,'temperature',1.0,NULL,NULL,NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_conduction',1,0,3,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "x"}',NULL,'\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_conduction',1,1,0,-1.0,NULL,1.0,'power',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_engines',1,0,0,NULL,NULL,1.0,'energy',1.0,NULL,'{"en-us": "W"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('heat_engines',1,0,1,NULL,NULL,1.0,'energy',-1.0,NULL,'{"en-us": "Q"}',NULL,NULL,NULL);
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
INSERT OR IGNORE INTO formula_item VALUES('impulse',1,1,0,NULL,NULL,1.0,'momentum',-1.0,NULL,'{"en-us": "J"}','{"en-us": "Impulse [Momentum]", "cs-cz": "Impuls [Momentum]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('interference',1,0,0,NULL,NULL,1.0,'angle',1.0,NULL,NULL,NULL,'\sin',NULL);
INSERT OR IGNORE INTO formula_item VALUES('interference',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "\\lambda"}','{"en-us": "Wave [length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('interference',1,1,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "d"}','{"en-us": "Slit separation"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('keplers_third_law',1,1,0,NULL,NULL,NULL,'time',-2.0,NULL,'{"en-us": "T"}','{"en-us": "Orbital [time]", "cs-cz": "Oběžná [time|doba]"}',NULL,NULL);
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
INSERT OR IGNORE INTO formula_item VALUES('mirrors',1,0,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "u"}','{"en-us": "Object distance"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('mirrors',1,0,1,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "v"}','{"en-us": "Image distance"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('mirrors',1,1,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "f"}','{"en-us": "Focal length"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('molarity_formula',1,0,0,NULL,NULL,1.0,'amount',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('molarity_formula',1,0,1,NULL,NULL,1.0,'volume',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('molarity_formula',1,1,0,NULL,NULL,1.0,'concentration',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('moles_from_mass',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('moles_from_mass',1,0,1,NULL,NULL,1.0,'molar_mass',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('moles_from_mass',1,1,0,NULL,NULL,1.0,'amount',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('moment_of_inertia',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('moment_of_inertia',1,0,1,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "r"}',NULL,NULL,NULL);
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
INSERT OR IGNORE INTO formula_item VALUES('percent_yield',1,0,0,NULL,NULL,1.0,'amount',1.0,NULL,NULL,'{"en-us": "Actual [Amount]", "cs-cz": "Skutečné [Amount]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('percent_yield',1,0,1,NULL,NULL,1.0,'amount',-1.0,NULL,NULL,'{"en-us": "Theoretical [Amount]", "cs-cz": "Teoretické [Amount]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('periodic_table',1,0,0,NULL,NULL,1.0,'amount',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('plane_geometry',1,0,0,2.0,NULL,-1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('plane_geometry',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "b"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('plane_geometry',1,0,2,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "h"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('plane_geometry',1,1,0,NULL,NULL,1.0,'area',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polarization',1,0,0,NULL,NULL,1.0,'refractive_index',1.0,NULL,'{"en-us": "n_2"}','{"en-us": "Transmitted [Refractive index]", "cs-cz": "Lomený [Refractive index]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polarization',1,0,1,NULL,NULL,1.0,'refractive_index',-1.0,NULL,'{"en-us": "n_1"}','{"en-us": "Incident [Refractive index]", "cs-cz": "Dopadající [Refractive index]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polarization',1,1,0,NULL,NULL,1.0,'angle',1.0,NULL,'\theta_\mathrm{B}','{"en-us": "Brewster [Angle]", "cs-cz": "Brewsterův [Angle]"}','\tan',NULL);
INSERT OR IGNORE INTO formula_item VALUES('polygons',1,0,0,2.0,NULL,-1.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polygons',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "s"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polygons',1,0,2,NULL,NULL,1.0,'angle',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polygons',1,1,0,NULL,NULL,1.0,'area',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polynomials',2,0,0,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "x"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polynomials',3,0,0,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "x"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('polynomials',4,0,0,NULL,NULL,1.0,'length',0.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('potential_energy',1,0,0,NULL,NULL,1.0,'mass',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('potential_energy',1,0,1,NULL,NULL,1.0,'acceleration',1.0,NULL,'{"en-us": "g"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('potential_energy',1,0,2,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "h"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('potential_energy',1,1,0,NULL,NULL,1.0,'energy',-1.0,'{"en-us": "p"}',NULL,'{"en-us": "Potential [energy]", "cs-cz": "Potenciální [energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('power_formula',1,0,0,NULL,NULL,1.0,'energy',1.0,NULL,'{"en-us": "W"}',NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('power_formula',1,0,1,NULL,NULL,1.0,'time',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('power_formula',1,1,0,NULL,NULL,1.0,'power',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pressure',1,0,0,NULL,NULL,1.0,'force',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pressure',1,0,1,NULL,NULL,1.0,'area',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pressure',1,1,0,NULL,NULL,1.0,'pressure',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('projectile_motion',1,0,0,NULL,NULL,1.0,'velocity',2.0,NULL,NULL,'{"en-us": "Initial [velocity]", "cs-cz": "Počáteční [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('projectile_motion',1,0,1,NULL,NULL,1.0,'acceleration',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('projectile_motion',1,1,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "R"}','{"en-us": "Range"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pythagorean_theorem',1,1,0,NULL,NULL,1.0,'length',-2.0,NULL,'{"en-us": "c"}','{"en-us": "Hypotenuse", "cs-cz": "Přepona"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pythagorean_theorem',2,0,0,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "a"}','{"en-us": "Side a", "cs-cz": "Strana a"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('pythagorean_theorem',3,0,0,NULL,NULL,1.0,'length',2.0,NULL,'{"en-us": "b"}','{"en-us": "Side b", "cs-cz": "Strana b"}',NULL,NULL);
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
INSERT OR IGNORE INTO formula_item VALUES('rotational_energy',1,1,0,NULL,NULL,1.0,'energy',-1.0,'{"en-us": "rot"}',NULL,'{"en-us": "Rotational [energy]", "cs-cz": "Rotační [energy]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('snells_law',1,1,0,NULL,NULL,1.0,'refractive_index',-1.0,'{"en-us": "1"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('snells_law',1,1,1,NULL,NULL,1.0,'angle',-1.0,'{"en-us": "i"}',NULL,NULL,'\sin',NULL);
INSERT OR IGNORE INTO formula_item VALUES('snells_law',2,0,0,NULL,NULL,1.0,'refractive_index',1.0,'{"en-us": "2"}',NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('snells_law',2,0,1,NULL,NULL,1.0,'angle',1.0,'{"en-us": "r"}',NULL,NULL,'\sin',NULL);
INSERT OR IGNORE INTO formula_item VALUES('surface_tension',1,0,0,NULL,NULL,1.0,'force',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('surface_tension',1,0,1,NULL,NULL,1.0,'length',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('surface_tension',1,1,0,NULL,NULL,1.0,'surface_tension',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('suvat_v2',1,1,0,NULL,NULL,1.0,'velocity',-2.0,NULL,NULL,'{"en-us": "Final [velocity]", "cs-cz": "Konečná [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('suvat_v2',2,0,0,NULL,NULL,1.0,'velocity',2.0,NULL,'{"en-us": "u"}','{"en-us": "Initial [velocity]", "cs-cz": "Počáteční [velocity]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('suvat_v2',3,0,0,2.0,NULL,1.0,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('suvat_v2',3,0,1,NULL,NULL,1.0,'acceleration',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('suvat_v2',3,0,2,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "s"}','{"en-us": "Displacement"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('wave_equation',1,0,0,NULL,NULL,1.0,'frequency',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('wave_equation',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "\\lambda"}','{"en-us": "Wave [length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('wave_equation',1,1,0,NULL,NULL,1.0,'velocity',-1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('wave_interference',1,0,0,NULL,NULL,1.0,'length',1.0,NULL,'{"en-us": "\\lambda"}','{"en-us": "Wave [length]"}',NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('wave_interference',1,1,0,NULL,NULL,1.0,'length',-1.0,NULL,'{"en-us": "\\Delta x"}','{"en-us": "Path difference"}','\Delta',NULL);
INSERT OR IGNORE INTO formula_item VALUES('work_formula',1,0,0,NULL,NULL,1.0,'force',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('work_formula',1,0,1,NULL,NULL,1.0,'length',1.0,NULL,NULL,NULL,NULL,NULL);
INSERT OR IGNORE INTO formula_item VALUES('work_formula',1,0,2,NULL,NULL,1.0,'angle',1.0,NULL,NULL,NULL,NULL,'{}');
INSERT OR IGNORE INTO formula_item VALUES('work_formula',1,1,0,NULL,NULL,1.0,'energy',-1.0,NULL,'{"en-us": "W"}',NULL,NULL,NULL);

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
UPDATE formula_item SET quantity_id='velocity', symbol_overwrite='{"en-us": "v_\\mathrm{esc}"}', quantity_name_overwrite='{"en-us": "Escape [velocity]", "cs-cz": "Úniková [velocity|rychlost]"}' WHERE formula_id='escape_velocity' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\lambda"}', quantity_name_overwrite='{"en-us": "Wave [length]", "cs-cz": "Vlnová [length|délka]"}' WHERE formula_id='diffraction' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\lambda"}', quantity_name_overwrite='{"en-us": "Wave [length]", "cs-cz": "Vlnová [length|délka]"}' WHERE formula_id='electromagnetic_waves' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\lambda"}', quantity_name_overwrite='{"en-us": "Wave [length]", "cs-cz": "Vlnová [length|délka]"}' WHERE formula_id='interference' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\lambda"}', quantity_name_overwrite='{"en-us": "Wave [length]", "cs-cz": "Vlnová [length|délka]"}' WHERE formula_id='wave_equation' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\lambda"}', quantity_name_overwrite='{"en-us": "Wave [length]", "cs-cz": "Vlnová [length|délka]"}' WHERE formula_id='wave_interference' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET quantity_id='length', symbol_overwrite='{"en-us": "\\Delta x"}', quantity_name_overwrite='{"en-us": "Path difference", "cs-cz": "Dráhový rozdíl"}' WHERE formula_id='wave_interference' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET quantity_id='electric_potential', symbol_overwrite='{"en-us": "E_\\mathrm{cell}"}', quantity_name_overwrite='{"en-us": "Cell", "cs-cz": "Článek"}' WHERE formula_id='electrochemistry' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET quantity_id='momentum', symbol_overwrite='{"en-us": "J"}', quantity_name_overwrite='{"en-us": "Impulse", "cs-cz": "Impuls"}' WHERE formula_id='impulse' AND term=1 AND is_primary=1 AND sort_order=0;

-- Pythagorean theorem: c² = a² + b²
UPDATE formula_item SET symbol_overwrite='{"en-us": "c"}', quantity_name_overwrite='{"en-us": "Hypotenuse", "cs-cz": "Přepona"}' WHERE formula_id='pythagorean_theorem' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "a"}' WHERE formula_id='pythagorean_theorem' AND term=2 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "b"}', label=NULL WHERE formula_id='pythagorean_theorem' AND term=3 AND is_primary=0 AND sort_order=0;

-- SUVAT: v² = u² + 2as
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Final [velocity]", "cs-cz": "Konečná [velocity|rychlost]"}' WHERE formula_id='suvat_v2' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "u"}', label=NULL, quantity_name_overwrite='{"en-us": "Initial [velocity]", "cs-cz": "Počáteční [velocity|rychlost]"}' WHERE formula_id='suvat_v2' AND term=2 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "s"}', quantity_name_overwrite='{"en-us": "Displacement", "cs-cz": "Dráha"}' WHERE formula_id='suvat_v2' AND term=3 AND is_primary=0 AND sort_order=2;

-- Conservation of momentum: m₁u₁ + m₂u₂ = m₁v₁ + m₂v₂
UPDATE formula_item SET symbol_overwrite='{"en-us": "u"}', label='{"en-us": "1"}', quantity_name_overwrite='{"en-us": "Initial [velocity]", "cs-cz": "Počáteční [velocity|rychlost]"}' WHERE formula_id='conservation_of_momentum' AND term=1 AND is_primary=1 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "u"}', label='{"en-us": "2"}', quantity_name_overwrite='{"en-us": "Initial [velocity]", "cs-cz": "Počáteční [velocity|rychlost]"}' WHERE formula_id='conservation_of_momentum' AND term=2 AND is_primary=1 AND sort_order=1;
UPDATE formula_item SET label='{"en-us": "1"}', quantity_name_overwrite='{"en-us": "Final [velocity]", "cs-cz": "Konečná [velocity|rychlost]"}' WHERE formula_id='conservation_of_momentum' AND term=3 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET label='{"en-us": "2"}', quantity_name_overwrite='{"en-us": "Final [velocity]", "cs-cz": "Konečná [velocity|rychlost]"}' WHERE formula_id='conservation_of_momentum' AND term=4 AND is_primary=0 AND sort_order=1;

-- Other formula_item refinements (labels → symbol_overwrite/quantity_name_overwrite)
UPDATE formula_item SET symbol_overwrite='{"en-us": "s"}', label=NULL WHERE formula_id='area' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "r"}' WHERE formula_id='circle_area' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "C"}', quantity_name_overwrite='{"en-us": "Circumference", "cs-cz": "Obvod"}' WHERE formula_id='circle_circumference' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "r"}' WHERE formula_id='circle_circumference' AND term=1 AND is_primary=0 AND sort_order=2;
UPDATE formula_item SET symbol_overwrite='{"en-us": "r"}' WHERE formula_id='moment_of_inertia' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "s"}', label=NULL WHERE formula_id='polygons' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "b"}', label=NULL WHERE formula_id='plane_geometry' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "h"}', label=NULL WHERE formula_id='plane_geometry' AND term=1 AND is_primary=0 AND sort_order=2;
UPDATE formula_item SET symbol_overwrite='{"en-us": "d"}', label=NULL, quantity_name_overwrite='{"en-us": "Slit separation", "cs-cz": "Šířka štěrbiny"}' WHERE formula_id='interference' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "d"}', label=NULL, quantity_name_overwrite='{"en-us": "Slit separation", "cs-cz": "Šířka štěrbiny"}' WHERE formula_id='diffraction' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "f"}', label=NULL, quantity_name_overwrite='{"en-us": "Focal length", "cs-cz": "Ohnisková vzdálenost"}' WHERE formula_id='mirrors' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "u"}', label=NULL, quantity_name_overwrite='{"en-us": "Object distance", "cs-cz": "Předmětová vzdálenost"}' WHERE formula_id='mirrors' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite='{"en-us": "v"}', label=NULL, quantity_name_overwrite='{"en-us": "Image distance", "cs-cz": "Obrazová vzdálenost"}' WHERE formula_id='mirrors' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Brewster [angle]", "cs-cz": "Brewsterův [angle|úhel]"}' WHERE formula_id='polarization' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Transmitted [refractive index]", "cs-cz": "Přenesený [refractive index|index lomu]"}' WHERE formula_id='polarization' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Incident [refractive index]", "cs-cz": "Dopadající [refractive index|index lomu]"}' WHERE formula_id='polarization' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite='{"en-us": "R"}', label=NULL, quantity_name_overwrite='{"en-us": "Range", "cs-cz": "Dostřel"}' WHERE formula_id='projectile_motion' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Initial [velocity]", "cs-cz": "Počáteční [velocity|rychlost]"}' WHERE formula_id='projectile_motion' AND term=1 AND is_primary=0 AND sort_order=0;

-- Clear English-word labels where qno/symbol already describes the quantity
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Wave [velocity]", "cs-cz": "Vlnová [velocity|rychlost]"}' WHERE formula_id='electromagnetic_waves' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Product [concentration]", "cs-cz": "Produkt [concentration|koncentrace]"}' WHERE formula_id='chemical_equilibrium' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Reactant [concentration]", "cs-cz": "Reaktant [concentration|koncentrace]"}' WHERE formula_id='chemical_equilibrium' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Actual [amount]", "cs-cz": "Skutečné [amount|množství]"}' WHERE formula_id='percent_yield' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET label=NULL, quantity_name_overwrite='{"en-us": "Theoretical [amount]", "cs-cz": "Teoretické [amount|množství]"}' WHERE formula_id='percent_yield' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET quantity_name_overwrite='{"en-us": "Hydrogen ion [concentration]", "cs-cz": "Vodíkový iont [concentration|koncentrace]"}' WHERE formula_id='acids_and_bases' AND term=1 AND is_primary=0 AND sort_order=0;

-- Re-seed safety: clear no-op symbol_overwrites that match quantity symbol
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='atomic_physics' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='entropy' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='entropy' AND term=1 AND is_primary=0 AND sort_order=1;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='heat' AND term=1 AND is_primary=0 AND sort_order=2;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='heat_conduction' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='heat_conduction' AND term=1 AND is_primary=0 AND sort_order=0;
UPDATE formula_item SET symbol_overwrite=NULL WHERE formula_id='heat_conduction' AND term=1 AND is_primary=0 AND sort_order=2;
-- Re-seed safety: add markers to qno values that were updated in INSERTs above
UPDATE formula_item SET quantity_name_overwrite='{"en-us": "Potential [energy]", "cs-cz": "Potenciální [energy|energie]"}' WHERE formula_id='potential_energy' AND term=1 AND is_primary=1 AND sort_order=0;
UPDATE formula_item SET quantity_name_overwrite='{"en-us": "Rotational [energy]", "cs-cz": "Rotační [energy|energie]"}' WHERE formula_id='rotational_energy' AND term=1 AND is_primary=1 AND sort_order=0;

