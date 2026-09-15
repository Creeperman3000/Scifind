"""Shared paths, superscript digit map."""

import re
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOCALE_DIR = PROJECT_DIR / "locales"

SUPERSCRIPT_DIGITS = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")

# Dimension search filter operators (position order); replaces the
# dimension_filter_operator seed table.
FILTER_OPS = ("eq", "geq", "leq")

# SI prefix exponents rendered expanded by default; replaces the
# app_config 'si_visible_exponents' seed row.
DEFAULT_VISIBLE_EXPONENTS = frozenset({0, 3, -3})


def is_slug(value):
    """True if `value` is a lowercase snake_case identifier."""
    return isinstance(value, str) and re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", value) is not None