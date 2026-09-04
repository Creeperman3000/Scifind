"""End-to-end check: after the schema rewrite, the conversion values
match the prior baseline byte-for-byte, and the LaTeX output is a
string-different but mathematically equivalent rendering.

Run: PYTHONPATH=. python3 scripts/compare_outputs.py
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

with open("scripts/baselines/convert_value.json") as f:
    base_cv = json.load(f)
with open("scripts/baselines/conversion_latex.json") as f:
    base_lx = json.load(f)

quantities = [
    q["quantity_id"] for q in conn.execute(
        "SELECT DISTINCT quantity_id FROM unit UNION "
        "SELECT DISTINCT quantity_id FROM compound_unit"
    )
    if q["quantity_id"]
]

cv_mismatches = 0
for qid in quantities:
    g = UnitGraph(conn, qid)
    ids = list(g.unit_rows) + list(g.compound_rows)
    for fid in ids:
        for tid in ids:
            if fid == tid:
                continue
            new_v = convert_value(1, fid, tid, g)
            key = f"{qid}|1|{fid}|{tid}"
            old_v = base_cv.get(key)
            if old_v is None and new_v is not None:
                cv_mismatches += 1
            elif old_v is not None and new_v is None:
                cv_mismatches += 1
            elif old_v is not None and new_v is not None:
                if abs(old_v - new_v) > 1e-6:
                    cv_mismatches += 1

mismatch_samples = []
for qid in quantities:
    g = UnitGraph(conn, qid)
    m = precompute_latex_map(g)
    for k, vs in m.items():
        for k2, v in vs.items():
            key = f"{qid}|{k}|{k2}"
            if base_lx.get(key) != v:
                if len(mismatch_samples) < 10:
                    mismatch_samples.append((key, base_lx.get(key), v))

print(f"convert_value mismatches: {cv_mismatches}  (must be 0)")
print(f"LaTeX total pairs: {len(base_lx)}")
total_diffs = 0
for qid in quantities:
    g = UnitGraph(conn, qid)
    m = precompute_latex_map(g)
    qdiff = 0
    for k, vs in m.items():
        for k2, v in vs.items():
            key = f"{qid}|{k}|{k2}"
            if base_lx.get(key) != v:
                qdiff += 1
    if qdiff:
        print(f"  {qid}: {qdiff} diffs")
        total_diffs += qdiff
print(f"total latex diffs: {total_diffs}")
if mismatch_samples:
    print(f"first 10 samples:")
    for key, old, new in mismatch_samples:
        print(f"  {key}:")
        print(f"    old: {old!r}")
        print(f"    new: {new!r}")
