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


# Quantities that should never appear in user-facing listings (search
# results, /quantities, the qty filter sidebar). "drop" is a placeholder
# used by some formulas and is meaningless on its own; "dimensionless"
# is a meta-quantity with no own dimension. Truly dimensionless rows
# (all dim_* columns == 0) are excluded by is_hidden_quantity()
# because they're not enumerable here.
_HIDDEN_QUANTITY_IDS = frozenset({"drop", "dimensionless"})


def is_hidden_quantity(q):
    """Return True when a quantity should be hidden from listings.

    Drops rows whose id is in _HIDDEN_QUANTITY_IDS and rows whose all
    seven base dimensions are zero (truly dimensionless quantities —
    e.g. angle, refractive_index, reynolds_number)."""
    if not q:
        return True
    qid = q.get("id") if isinstance(q, dict) else q["id"]
    if qid in _HIDDEN_QUANTITY_IDS:
        return True
    cols = ("dim_M", "dim_L", "dim_T", "dim_I", "dim_Θ", "dim_N", "dim_J")
    if all((q[c] if isinstance(q, dict) else q[c]) == 0 for c in cols):
        return True
    return False

