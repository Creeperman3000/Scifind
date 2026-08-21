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
