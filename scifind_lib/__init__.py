"""Scifind library — physics formula database, parser, LaTeX renderer, web helpers."""
# Licensed under the LICENSE file in the project root.

from scifind_lib.db import (  # noqa: F401
    database_has_formula_table,
    database_path,
    init_database,
    open_database,
)

from scifind_lib.dimensions import (  # noqa: F401
    build_dimension_symbol_maps,
    compute_all_formula_dimensions,
    compute_formula_dimensions,
    dimension_matches,
    dimension_quantity_ids,
    dimension_symbols,
    extract_dimensions_from_row,
    format_dimensions_latex,
    format_dimensions_plain,
)

from scifind_lib.i18n import (  # noqa: F401
    difficulty_to_stars,
    locale_sibilants,
    localise,
    localise_english,
    render_symbol,
)

from scifind_lib.tree import (  # noqa: F401
    all_tree_ids,
    compress_selection,
    expand_selection,
    load_tree,
    topic_name,
    topic_name_map,
    topic_path,
    topic_tree_order,
    walk_tree,
)

from scifind_lib.units import (  # noqa: F401
    format_default_unit_html,
    format_default_unit_symbol,
    unit_name_map,
    unit_quantity_map,
    unit_symbol_map,
)

from scifind_lib.search import (  # noqa: F401
    search_headings,
    suggest_headings,
)

from scifind_lib.renderer import (  # noqa: F401
    preview_equation,
    render_formula,
)

from scifind_lib.queries import (  # noqa: F401
    _in_clause,
    fetch_all_constants,
    fetch_all_formulas,
    fetch_all_operators,
    fetch_all_quantities,
    fetch_formula,
    fetch_formula_detail_items,
    fetch_formula_quantities,
    fetch_formula_related,
    fetch_formulas_with_all_quantities,
    fetch_formulas_with_any_quantity,
    fetch_quantities_by_ids,
    fetch_quantity,
    fetch_quantity_formulas,
    fetch_quantity_formulas_by_side,
    fetch_quantity_related_formulas,
    fetch_quantity_units,
    fetch_si_unit_symbol,
    fetch_unit,
    parse_quantity_name_markers,
    render_variable_base,
)

from scifind_lib.sorting import (  # noqa: F401
    DEFAULT_FORMULA_SORT,
    DEFAULT_QUANTITY_SORT,
    DEFAULT_SEARCH_SORT,
    FORMULA_SORT_KEYS,
    QUANTITY_SORT_KEYS,
    SEARCH_SORT_KEYS,
    sort_formulas,
    sort_quantities,
    sort_search_rows,
)

from scifind_lib.build import (  # noqa: F401
    build_create_sql,
)

from scifind_lib.export import (  # noqa: F401
    export_to_csv,
    export_to_csv_directory,
    export_to_ods,
    export_to_xlsx,
)

from scifind_lib.display import (  # noqa: F401
    format_unit_str,
    group_by_topic,
)
