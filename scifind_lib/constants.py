"""Constants shared across the scifind_lib submodules."""
# Licensed under the LICENSE file in the project root.

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
_LOCALE_DIR = PROJECT_DIR / "locales"
TREE_PATH = PROJECT_DIR / "tree.json"

_BASE_DIMENSION_ORDER = ("M", "L", "T", "I", "Θ", "N", "J")
_BASE_DIMENSION_QTY_IDS = {
    "M": "mass",
    "L": "length",
    "T": "time",
    "I": "current",
    "Θ": "temperature",
    "N": "amount",
    "J": "luminous_intensity",
}


# Quantities excluded from user-facing listings (search results,
# /quantities, the qty filter sidebar). "drop" is a placeholder used by
# some formulas and is meaningless on its own; "dimensionless" is a
# meta-quantity with no own dimension.
_HIDDEN_QUANTITY_IDS = frozenset({"drop", "dimensionless"})


def is_hidden_quantity(q):
    """Return True when a quantity's id is in _HIDDEN_QUANTITY_IDS.

    Accepts an id string or a row/dict with an "id" key."""
    if not q:
        return True
    if isinstance(q, str):
        return q in _HIDDEN_QUANTITY_IDS
    return q["id"] in _HIDDEN_QUANTITY_IDS

