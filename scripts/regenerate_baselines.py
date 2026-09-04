"""Regenerate scripts/baselines/convert_value.json and conversion_latex.json
from a freshly-initialised database.

Run: PYTHONPATH=. python3 scripts/regenerate_baselines.py
"""
import os, sys, json
os.environ.setdefault("SCIFIND_DB", "/tmp/scifind_compare.db")
sys.path.insert(0, ".")

if os.path.exists(os.environ["SCIFIND_DB"]):
    os.remove(os.environ["SCIFIND_DB"])

from scifind_lib import initialize_database, open_database
from scifind_lib.conversion import UnitGraph, precompute_latex_map, convert_value
initialize_database()
conn = open_database()

quantities = [
    q["quantity_id"] for q in conn.execute(
        "SELECT DISTINCT quantity_id FROM unit UNION "
        "SELECT DISTINCT quantity_id FROM compound_unit"
    )
    if q["quantity_id"]
]

base_cv = {}
for qid in quantities:
    g = UnitGraph(conn, qid)
    ids = list(g.unit_rows) + list(g.compound_rows)
    for fid in ids:
        for tid in ids:
            if fid == tid:
                continue
            v = convert_value(1, fid, tid, g)
            if v is not None:
                base_cv[f"{qid}|1|{fid}|{tid}"] = v

base_lx = {}
for qid in quantities:
    g = UnitGraph(conn, qid)
    m = precompute_latex_map(g)
    for k, vs in m.items():
        for k2, v in vs.items():
            base_lx[f"{qid}|{k}|{k2}"] = v

for path, data in (("scripts/baselines/convert_value.json", base_cv),
                   ("scripts/baselines/conversion_latex.json", base_lx)):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"wrote {path}: {len(data)} entries")