"""Scifind library — physics formula database, parser, LaTeX renderer, web helpers."""

from scifind_lib.db import (  # noqa: F401
    database_connection, database_has_formula_table, database_path, in_clause,
    initialize_database, open_database,
)
from scifind_lib.formula import (  # noqa: F401
    DIMENSION_OPS, build_dimension_symbol_triplet,
    compute_all_formula_dimensions, compute_compound_unit_dimensions,
    compute_formula_dimensions, compute_rpn_dimensions, dimension_columns,
    dimension_matches, dimension_quantity_ids, dimension_symbols,
    dimensions_from_row, format_dimension_number, format_dimensions_latex,
    format_dimensions_plain, parse_and_preview_equation, render_formula_latex,
)
from scifind_lib.i18n import (  # noqa: F401
    difficulty_to_stars, locale_sibilants, localise, localise_english,
    load_locale_config, wrap_symbol_in_latex,
)
from scifind_lib.tree import (  # noqa: F401
    all_tree_ids, compress_selection, expand_selection, load_tree, topic_name,
    topic_name_map, topic_path, topic_tree_order, walk_tree,
)
from scifind_lib.units import (  # noqa: F401
    DEFAULT_VISIBLE_EXPONENTS, SI_BASE_EXPONENT, compound_slug_is_base,
    compound_unit_by_slug, format_compound_unit_html,
    format_compound_unit_symbol, inject_si_prefix_nodes, parse_compound_unit,
    parse_compound_unit_parts, prefix_name_callback, select_base_unit,
    select_base_unit_with_fallback, si_prefix_sections, split_numerator_denominator,
    unit_by_id, unit_name_callback, unit_name_map, unit_quantity_map,
    unit_symbol_map,
)
from scifind_lib.fetch import (  # noqa: F401
    DEFAULT_FORMULA_SORT, DEFAULT_QUANTITY_SORT, DEFAULT_SEARCH_SORT,
    FORMULA_SORT_KEYS, MAX_DIFFICULTY, MIN_DIFFICULTY, QUANTITY_SORT_KEYS,
    SEARCH_SORT_KEYS, QuantityFilter,
    fetch_all_constants, fetch_all_formulas,
    fetch_all_operators, fetch_all_quantities,
    fetch_compound_units, fetch_constant, fetch_constant_formulas,
    fetch_first_unit, fetch_formula, fetch_formula_token_quantities,
    fetch_formula_quantities, fetch_formula_relations,
    fetch_formulas_filtered, fetch_formulas_with_all_quantities,
    fetch_formulas_with_any_quantity, fetch_keyed_rows,
    fetch_prefixable_base_units, fetch_quantities_by_ids, fetch_quantity,
    fetch_quantity_constants, fetch_quantity_formulas,
    fetch_quantity_formulas_by_side, fetch_quantity_related_formulas,
    fetch_quantity_units, fetch_search_meta, fetch_si_prefix_map,
    fetch_si_prefixes, fetch_unit, fetch_units_with_quantity,
    parse_csv_string, parse_filter_state, parse_int_with_default,
    search_entities, suggest_entities, sort_formulas,
    sort_quantities, sort_quantities_base_first, sort_search_rows,
    unit_is_base,
)
from scifind_lib.export import (  # noqa: F401
    EXPORT_TABLE_COLUMNS, EXPORT_TABLE_ORDER, FORMULA_COLUMNS, TOKEN_COLUMNS,
    build_create_sql, build_formula_insert_sql, export_to_csv,
    export_to_csv_directory, export_to_ods,
    export_to_sql, export_to_xlsx, export_to_csv_zip,
)
from scifind_lib.display import (  # noqa: F401
    build_entity_link, expand_quantity_markers, format_unit_symbol_plain,
    group_by_topic, quantity_units_table, render_compound_unit,
    render_variable_symbol, unit_name_link,
)
