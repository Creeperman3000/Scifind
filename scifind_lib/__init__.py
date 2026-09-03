"""Scifind library — physics formula database, parser, LaTeX renderer, web helpers."""

from scifind_lib.db import (  # noqa: F401
    database_has_formula_table, database_path, in_clause, initialize_database, open_database,
)
from scifind_lib.dimensions import (  # noqa: F401
    build_dimension_symbol_triplet, compute_all_formula_dimensions,
    compute_compound_unit_dimensions, compute_formula_dimensions, dimension_matches,
    dimension_quantity_ids, dimension_symbols, dimensions_from_row,
    format_dimensions_latex, format_dimensions_plain,
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
    compound_unit_by_id, format_compound_unit_html, format_compound_unit_symbol,
    parse_compound_unit, select_base_unit, select_base_unit_with_fallback, unit_by_id,
    unit_name_map, unit_quantity_map, unit_symbol_map,
)
from scifind_lib.search import search_entities, suggest_entities  # noqa: F401
from scifind_lib.renderer import parse_and_preview_equation, render_formula_latex  # noqa: F401
from scifind_lib.queries import (  # noqa: F401
    build_entity_link, fetch_all_constants, fetch_all_formulas,
    fetch_all_operators, fetch_all_quantities, fetch_constant, fetch_constant_formulas,
    fetch_formula, fetch_formula_token_quantities, fetch_formula_quantities,
    fetch_formula_relations, fetch_formulas_with_all_quantities,
    fetch_formulas_with_any_quantity, fetch_quantities_by_ids, fetch_quantity,
    fetch_quantity_constants, fetch_quantity_formulas,
    fetch_quantity_formulas_by_side, fetch_quantity_related_formulas,
    fetch_quantity_units, fetch_si_prefixes, fetch_unit,
    expand_quantity_markers, render_variable_symbol,
)
from scifind_lib.sorting import (  # noqa: F401
    DEFAULT_FORMULA_SORT, DEFAULT_QUANTITY_SORT, DEFAULT_SEARCH_SORT,
    FORMULA_SORT_KEYS, QUANTITY_SORT_KEYS, SEARCH_SORT_KEYS, sort_formulas,
    sort_quantities, sort_quantities_base_first, sort_search_rows,
)
from scifind_lib.build import build_create_sql  # noqa: F401
from scifind_lib.export import (  # noqa: F401
    build_formula_insert_sql, export_to_csv, export_to_csv_directory, export_to_ods,
    export_to_sql, export_to_xlsx,
)
from scifind_lib.display import format_unit_symbol_plain, group_by_topic  # noqa: F401