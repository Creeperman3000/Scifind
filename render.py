#!/usr/bin/env python3
"""
Validate all Scifind formulas render to correct LaTeX.
"""

import json
import sys
from pathlib import Path

_project_dir = Path(__file__).resolve().parent
if str(_project_dir) not in sys.path:
    sys.path.insert(0, str(_project_dir))

from formula_lib import get_conn, get_formula_detail, get_formula_items, render_formula_items


def main():
    conn = get_conn()

    formula_ids = [
        "newton_second_law_of_motion",
        "kinetic_energy",
        "suvat_v2",
        "first_law_thermodynamics",
        "first_law_thermodynamics_adiabatic",
        "first_law_thermodynamics_isochoric",
        "conservation_of_momentum",
        "ideal_gas_law",
        "keplers_third_law",
        "parallel_resistance",
    ]

    for fid in formula_ids:
        items = get_formula_items(conn, fid)
        latex = render_formula_items(items)
        row = get_formula_detail(conn, fid)
        label = row["name_en"] if row else fid
        print(f"% {label}")
        print(f"$$ {latex} $$")
        print()

    conn.close()


if __name__ == "__main__":
    main()
