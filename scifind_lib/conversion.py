"""Reference-graph unit conversion.

Each unit row carries `reference_unit_id` (FK to another unit in the same
quantity) and `reference_expr` (JSON: how to convert THIS unit's value
into the reference unit's value, i.e. `x_ref = f(x_this)`).

Expression grammar (JSON, normalised to a list of steps):

    [{"op": "mul", "value": <number>}, ...]
    [{"op": "div", "value": <number>}, ...]
    [{"op": "add", "value": <number>}, ...]
    [{"op": "sub", "value": <number>}, ...]
    [{"constant": "<id>"}]
    [{"unit": "<id>", "exp": <int>}, ...]    # recursive unit ref, applied at exponent

Steps are applied left-to-right, threading x through each. A `unit` step
contributes (x_root_at_unit)^exp to the multiplier; constants contribute
their numeric value.

The renderer walks the declared graph (no heuristics) and produces LaTeX
for either the row→ref or ref→row direction. Cycles/orphans are detected
at load time — the app refuses to start if the graph is broken.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from scifind_lib.units import format_default_unit_symbol

logger = logging.getLogger(__name__)

# ---------- expression evaluation ----------

def _fraction(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        m = re.fullmatch(r"-?\d+(?:\.\d+)?/-?\d+(?:\.\d+)?", s)
        if m:
            n, d = s.split("/")
            return float(n) / float(d)
        try:
            return float(s)
        except ValueError:
            return float("nan")
    return float("nan")


def _step_operand(step, constants):
    """Resolve a step's operand as a float."""
    if "constant" in step:
        return constants.get(step["constant"], float("nan"))
    return _fraction(step.get("value"))


def _apply(expr, x, constants, ctx=None):
    """Thread x through a (list of) step(s). ctx is unused (kept for API stability)."""
    steps = expr if isinstance(expr, list) else [expr]
    for step in steps:
        op = step.get("op")
        if "constant" in step:
            operand = constants.get(step["constant"], float("nan"))
        else:
            operand = _fraction(step.get("value"))
        if not math.isfinite(operand):
            return float("nan")
        if op is None:
            x *= operand
        elif op == "mul":
            x *= operand
        elif op == "div":
            x /= operand
        elif op == "add":
            x += operand
        elif op == "sub":
            x -= operand
        else:
            return float("nan")
    return x


# ---------- reference graph ----------

class UnitGraph:
    """Walk the per-quantity unit reference graph and resolve root values.

    When a unit's reference points outside its quantity (e.g. `hectare`
    of `area` references `metre` of `length`), the cross-quantity target
    is loaded lazily and cached in `extra_edges`. This lets the graph
    be acyclic while still crossing quantity boundaries.
    """

    def __init__(self, conn, quantity_id):
        self.conn = conn
        self.quantity_id = quantity_id
        self.unit_rows = {}
        self.compound_rows = {}
        self.edges = {}  # id -> (ref_id, expr)
        for row in conn.execute(
            "SELECT id, quantity_id, symbol, system, is_base, reference_unit_id, reference_expr "
            "FROM unit WHERE quantity_id = ?",
            (quantity_id,),
        ).fetchall():
            self.unit_rows[row["id"]] = dict(row)
            ref = row["reference_unit_id"]
            expr_raw = row["reference_expr"]
            expr = None
            if expr_raw:
                try:
                    expr = json.loads(expr_raw)
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning("unit %s reference_expr: bad JSON: %s", row["id"], exc)
            self.edges[row["id"]] = (ref, expr)
        for row in conn.execute(
            "SELECT id, quantity_id, unit, symbol_overwrite, system, is_base, "
            "reference_unit_id, reference_expr "
            "FROM compound_unit WHERE quantity_id = ?",
            (quantity_id,),
        ).fetchall():
            self.compound_rows[row["id"]] = dict(row)
            ref = row["reference_unit_id"]
            expr_raw = row["reference_expr"]
            expr = None
            if expr_raw:
                try:
                    expr = json.loads(expr_raw)
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning("compound %s reference_expr: bad JSON: %s",
                                   row["id"], exc)
            self.edges[row["id"]] = (ref, expr)

    def _ensure_unit_loaded(self, unit_id):
        """Load a unit row into the graph if it's not already present
        (and not a compound row). Returns the edge (ref_id, expr) or None
        if the unit doesn't exist or is compound. Also adds the row's
        full data to unit_rows so cross-quantity detection works.
        """
        if unit_id in self.edges or unit_id in self.unit_rows:
            return self.edges.get(unit_id)
        if unit_id in self.compound_rows:
            return None  # compound unit = root, no edge
        row = self.conn.execute(
            "SELECT id, quantity_id, symbol, reference_unit_id, reference_expr "
            "FROM unit WHERE id = ?",
            (unit_id,),
        ).fetchone()
        if row is None:
            return None
        expr_raw = row["reference_expr"]
        expr = None
        if expr_raw:
            try:
                expr = json.loads(expr_raw)
            except (json.JSONDecodeError, TypeError):
                expr = None
        self.edges[unit_id] = (row["reference_unit_id"], expr)
        # Also remember the row's data so renderers (which use symbol,
        # system, etc.) work for cross-quantity hops.
        if unit_id not in self.unit_rows:
            self.unit_rows[unit_id] = dict(row)
        return self.edges[unit_id]

    def all_unit_ids(self):
        return list(self.unit_rows)

    def all_compound_ids(self):
        return list(self.compound_rows)

    def constants_dict(self):
        out = {}
        for row in self.conn.execute(
            "SELECT id, value FROM constant WHERE value IS NOT NULL"
        ).fetchall():
            out[row["id"]] = float(row["value"])
        return out

    def path_to_root(self, unit_id):
        """Return [unit_id, ..., root] or None on cycle / orphan.

        The root is whichever node has no outgoing reference edge —
        i.e. either a unit row with reference_unit_id IS NULL, or a
        compound_unit row that itself has no reference edge (acts as
        the SI base for its quantity). For compound_unit roots, the
        caller should account for the compound's parts via
        root_value_compound_of_compound.
        """
        seen = set()
        path = []
        while True:
            if unit_id in seen:
                return None
            seen.add(unit_id)
            path.append(unit_id)
            edge = self._ensure_unit_loaded(unit_id)
            if edge is None:
                return None
            nxt = edge[0]
            if nxt is None:
                break
            unit_id = nxt
        return path

    def root_value(self, unit_id):
        """Compute the ratio of `1 unit_id` in the root unit.

        The root is the last node of `path_to_root`. Works for both
        unit rows and compound_unit rows: if the path ends at a unit
        row we return the chain product; if it ends at a compound row
        we additionally account for the compound's parts.
        """
        path = self.path_to_root(unit_id)
        if path is None:
            return None
        constants = self.constants_dict()
        x = 1.0
        for cur in path[:-1]:
            edge = self._ensure_unit_loaded(cur)
            if edge is None:
                return None
            expr = edge[1]
            x = _apply(expr, x, constants)
            if not math.isfinite(x):
                return None
        # If path[-1] is a compound row, multiply by its root value.
        if path[-1] in self.compound_rows:
            compound_root = self.root_value_compound_of_compound(path[-1])
            if compound_root is None:
                return None
            x *= compound_root
        return x

    def root_value_compound(self, unit_id):
        """Like root_value, but works when the path ends at a compound.

        Walks to the compound, then evaluates the compound's value in
        terms of its underlying unit parts. Returns None if any step
        is unreachable.
        """
        path = self.path_to_root(unit_id)
        if path is None:
            return None
        constants = self.constants_dict()
        x = 1.0
        for cur in path[:-1]:
            edge = self._ensure_unit_loaded(cur)
            if edge is None:
                return None
            expr = edge[1]
            x = _apply(expr, x, constants)
            if not math.isfinite(x):
                return None
        # path[-1] is the root (unit or compound). If unit, return x.
        if path[-1] in self.unit_rows:
            return x
        # Compound: multiply x by the compound's root value.
        compound_root = self.root_value_compound_of_compound(path[-1])
        if compound_root is None:
            return None
        return x * compound_root

    def root_value_compound_of_compound(self, compound_id):
        """The root_value of a compound row expressed in raw unit-parts.

        For `metre_per_second`, returns 1 (since 1 m/s = 1 m × 1 /s, both
        of which are unit rows). For `metre_squared`, returns 1 (1 m²
        involves 1 m, no second unit).
        """
        row = self.compound_rows.get(compound_id)
        if row is None:
            return None
        try:
            parts = json.loads(row["unit"])
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(parts, list):
            return None
        result = 1.0
        for part in parts:
            uid = part.get("unit")
            exp = part.get("exponent", 1)
            v = self.root_value(uid)
            if v is None or not math.isfinite(v):
                return None
            result *= v ** exp
        return result


# ---------- validation ----------

class UnitGraphError(Exception):
    pass


def validate_graph(conn):
    """Walk every quantity's unit graph; raise on cycle or orphan.

    A unit's reference chain may hop into another quantity (e.g.
    `hectare → metre`); the graph lazily loads cross-quantity targets,
    so a successful root resolution means the entire chain is sound.
    """
    for qid_row in conn.execute("SELECT DISTINCT quantity_id FROM unit").fetchall():
        qid = qid_row["quantity_id"]
        graph = UnitGraph(conn, qid)
        # Snapshot keys: path_to_root() lazily adds cross-quantity units
        # to graph.unit_rows, which would otherwise mutate during iteration.
        for uid in list(graph.unit_rows):
            if graph.path_to_root(uid) is None:
                raise UnitGraphError(
                    f"quantity '{qid}' unit '{uid}' has no path to root "
                    f"(cycle or orphan — graph integrity violated)"
                )


# ---------- path finder between two units ----------

def path_between(graph, from_id, to_id):
    """Return [from_id, ..., to_id] along the reference graph, or None.

    Walks edges in either direction. The graph is stored as directed
    edges (`A → B` means B is A's reference), but the renderer needs to
    go both ways to display "row R, ref F" for any (R, F) pair.

    Uses BFS so the returned path is the shortest in hops.
    """
    if from_id == to_id:
        return [from_id]
    visited = {from_id}
    queue = [(from_id, [from_id])]
    while queue:
        cur, path = queue.pop(0)
        # Walk forward (cur → its reference)
        fwd = graph.edges.get(cur)
        if fwd is not None:
            nxt = fwd[0]
            if nxt == to_id:
                return path + [nxt]
            if nxt and nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [nxt]))
        # Walk backward (cur ← who references cur)
        for other_id, (other_ref, _) in graph.edges.items():
            if other_ref == cur and other_id != cur and other_id not in visited:
                if other_id == to_id:
                    return path + [other_id]
                visited.add(other_id)
                queue.append((other_id, path + [other_id]))
    return None


def path_between_with_direction(graph, from_id, to_id):
    """Like path_between, but also returns the direction of each hop.

    Each hop in the returned path is annotated with how to traverse it:
    "fwd" means `cur → edges[cur]` (use that expression); "bwd" means
    `cur` is the target of someone else's edge, so the relationship is
    inverted.

    Returns (path, directions) where path = [n0, n1, ..., nk] and
    directions = ["fwd" | "bwd", ...] of length k-1, telling how to walk
    n0 → n1 → ... → nk.
    """
    if from_id == to_id:
        return [from_id], []
    visited = {from_id: ([from_id], [])}
    queue = [(from_id, [from_id], [])]
    while queue:
        cur, path, dirs = queue.pop(0)
        # Forward
        fwd = graph.edges.get(cur)
        if fwd is not None:
            nxt = fwd[0]
            if nxt == to_id:
                return path + [nxt], dirs + ["fwd"]
            if nxt and nxt not in visited:
                visited[nxt] = (path + [nxt], dirs + ["fwd"])
                queue.append((nxt, path + [nxt], dirs + ["fwd"]))
        # Backward: who references cur?
        for other_id, (other_ref, _) in graph.edges.items():
            if other_ref == cur and other_id != cur and other_id not in visited:
                if other_id == to_id:
                    return path + [other_id], dirs + ["bwd"]
                visited[other_id] = (path + [other_id], dirs + ["bwd"])
                queue.append((other_id, path + [other_id], dirs + ["bwd"]))
    return None, None


def value_at_root(unit_or_compound_id, graph):
    """Return 1 unit_or_compound expressed in the root unit. Alias for clarity."""
    return _root_value(graph, unit_or_compound_id)


def convert_value(value, from_id, to_id, graph):
    """Convert `value` expressed in `from_id` units to `to_id` units.

    Returns None when from_id or to_id is unreachable from the root, or
    when the conversion isn't defined.
    """
    if from_id == to_id:
        return value
    from_root = _root_value(graph, from_id)
    to_root = _root_value(graph, to_id)
    if from_root is None or to_root is None or to_root == 0:
        return None
    return value * from_root / to_root


def precompute_latex_map(graph):
    """Return {row_id: {ref_id: latex_or_None}} for every reachable pair.

    The map is small (N² entries per quantity, ~10x10 typical) so the cost
    is negligible. The renderer uses it to look up the cell LaTeX on the
    client without re-walking the graph.

    For each (row, ref) pair we try the forward walk (row → root → ... →
    ref) first; if there's no forward path we try walking in the
    inverse direction (ref → ... → row) and invert the equation. The
    reference graph is stored as directed edges (each unit points to
    its reference), so "row→ref" only works when ref is downstream of
    row; the inverse case is the common one for the user-picked
    reference scenario.
    """
    out = {}
    ids = graph.all_unit_ids() + graph.all_compound_ids()
    for row_id in ids:
        out[row_id] = {}
        for ref_id in ids:
            if row_id == ref_id:
                out[row_id][ref_id] = None
            else:
                latex = render_equation(graph, row_id, ref_id)
                if latex is None:
                    latex = _render_inverse_or_numeric(graph, row_id, ref_id)
                out[row_id][ref_id] = latex
    return out


def _render_inverse_or_numeric(graph, row_id, ref_id):
    """Try the inverse chain (ref → row), then fall back to numeric."""
    # If ref has a chain leading to row, we can build an equation by
    # walking that chain backwards.
    forward = path_between(graph, ref_id, row_id)
    if forward is not None and len(forward) >= 2:
        # forward = [ref_id, ..., row_id]; we need to emit "1 row = N ref".
        # We do that by walking ref→row, accumulating inverses.
        # For an affine expression, inverting step-by-step works as
        # long as the chain has no divides (mul/div is its own inverse
        # under swap). Offsets invert trivially.
        latex = _render_inverse_chain_equation(graph, forward, row_id, ref_id)
        if latex is not None:
            return latex
    return _render_numeric_equation(graph, row_id, ref_id)


def _render_inverse_chain_equation(graph, path, row_id, ref_id):
    """Walk the chain ref → ... → row and emit '1 row = ... ref'.

    path = [ref_id, ..., row_id]. We traverse each edge forward and
    invert the expression to map "x_target = f(x_source)" to
    "x_source = g(x_target)". For pure mul/div the inversion is
    trivial; for affine expressions we just emit the symbolic form.
    """
    constants = graph.constants_dict()
    row_sym = _unit_latex(graph, row_id)
    ref_sym = _unit_latex(graph, ref_id)

    # Detect constants/offsets across the path for symbol-vs-numeric choice.
    has_constant = False
    has_offset = False
    for cur in path[:-1]:
        expr = graph.edges.get(cur, (None, None))[1]
        if expr is None:
            return None
        for step in (expr if isinstance(expr, list) else [expr]):
            if "constant" in step:
                has_constant = True
            if step.get("op") in ("add", "sub"):
                has_offset = True

    if has_offset:
        # Offset chains: only the leading edge is meaningful (we don't
        # implement multi-edge offset inversion well). Emit it.
        cur = path[0]
        expr = graph.edges[cur][1]
        return _render_offset_equation(graph, [cur, path[1]], row_sym, ref_sym, constants)
    if has_constant:
        return _render_symbolic_factor(graph, path, ref_sym, row_sym)
    # Pure multiplicative — compute the numeric ratio.
    return _render_numeric_equation(graph, row_id, ref_id)


def _render_numeric_equation(graph, row_id, ref_id):
    """Numeric fallback when there's no forward chain.

    Computes the ratio between the two units and emits a numeric equation.
    """
    if row_id == ref_id:
        return None
    row_val = _root_value(graph, row_id)
    ref_val = _root_value(graph, ref_id)
    if row_val is None or ref_val is None or ref_val == 0:
        return None
    ratio = row_val / ref_val
    if not math.isfinite(ratio) or ratio == 1:
        return None
    factor_str = _pretty_factor(ratio)
    row_sym = _unit_latex(graph, row_id)
    ref_sym = _unit_latex(graph, ref_id)
    return f"1\\,{row_sym} = {factor_str}\\,{ref_sym}"


# ---------- LaTeX emission ----------

def _unit_symbol(graph, unit_id):
    if unit_id in graph.unit_rows:
        return graph.unit_rows[unit_id].get("symbol") or unit_id
    if unit_id in graph.compound_rows:
        row = graph.compound_rows[unit_id]
        if row.get("symbol_overwrite"):
            return row["symbol_overwrite"]
        try:
            parts = json.loads(row["unit"])
        except (json.JSONDecodeError, TypeError):
            return unit_id
        sym_map = {uid: graph.unit_rows[uid]["symbol"]
                   for uid in graph.unit_rows if uid in graph.unit_rows}
        return format_default_unit_symbol(
            json.dumps(parts),
            unit_symbol=lambda uid: sym_map.get(uid, uid),
        )
    return unit_id


def _unit_latex(graph, unit_id):
    sym = _unit_symbol(graph, unit_id)
    if not sym:
        return ""
    if "\\" in sym or "{" in sym:
        return sym
    return f"\\mathrm{{{sym}}}"


def _step_latex(step, constants):
    """LaTeX for a step's operand (no threading, just the value)."""
    if "constant" in step:
        cid = step["constant"]
        row = constants.get(cid) if isinstance(constants, dict) and "cid" in constants else None
        # Pull from DB (constants dict is just numeric; we need symbols):
        return _constant_symbol(constants, cid)
    val = step.get("value")
    if isinstance(val, str) and "/" in val and re.fullmatch(r"-?\d+(?:\.\d+)?/-?\d+(?:\.\d+)?", val):
        n, d = val.split("/")
        return f"\\frac{{{n}}}{{{d}}}"
    try:
        v = _fraction(val)
        if not math.isfinite(v):
            return "?"
        if isinstance(val, (int, float)) and v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return f"{v:.6g}"
    except (ValueError, TypeError):
        return str(val)


def _constant_symbol(conn, cid):
    """Look up a constant's symbol LaTeX from DB."""
    if hasattr(conn, "execute"):
        row = conn.execute("SELECT symbol FROM constant WHERE id = ?", (cid,)).fetchone()
        if row:
            return row["symbol"]
    return cid


def _pretty_factor(x):
    if x == 0:
        return "0"
    ax = abs(x)
    sign = "-" if x < 0 else ""
    if ax >= 1e15 or ax < 1e-4:
        exp = int(math.floor(math.log10(ax)))
        mant = x / (10 ** exp)
        # If mant is in [0.1, 1) bump up (so mantissa is in [1, 10)).
        if 0.1 <= abs(mant) < 1:
            mant *= 10
            exp -= 1
        # If mant is exactly 10 (rounding put it over), bump back.
        if abs(mant) >= 10:
            mant /= 10
            exp += 1
        return f"{sign}{mant:.4g}\\times10^{{{exp}}}"
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return f"{x:.6g}"


def render_equation(graph, row_id, ref_id):
    """Build the conversion-cell LaTeX: '1 row = N ref'.

    Picks the path that yields the cleanest display:
    - If row and ref are in the same quantity, walk the reference graph
      (forward or inverse) for symbolic / offset / numeric forms.
    - If cross-quantity (e.g. `hectare` ↔ `square_foot`), compute the
      ratio numerically from root values and emit a numeric form.
    """
    if row_id == ref_id:
        return None

    if _same_quantity(graph, row_id, ref_id):
        path_fwd, dirs_fwd = path_between_with_direction(graph, row_id, ref_id)
        path_inv, dirs_inv = path_between_with_direction(graph, ref_id, row_id)
        if path_fwd is not None and len(path_fwd) >= 2:
            return _emit_path_equation(graph, path_fwd, dirs_fwd)
        if path_inv is not None and len(path_inv) >= 2:
            return _emit_inverse_path_equation(graph, path_inv, dirs_inv)
        # Both quantities in same table but no path? Numeric fallback.
    return _render_numeric_equation(graph, row_id, ref_id)


def _same_quantity(graph, a, b):
    """True iff both nodes live in the graph's primary quantity."""
    def qty_of(node):
        if node in graph.unit_rows:
            return graph.unit_rows[node]["quantity_id"]
        if node in graph.compound_rows:
            return graph.compound_rows[node]["quantity_id"]
        return None  # cross-quantity node
    return qty_of(a) is not None and qty_of(a) == qty_of(b)


def _emit_path_equation(graph, path, directions):
    """Emit the equation for a path: path = [row, ..., ref].

    `directions` has the same length as `path - 1`. Each entry is "fwd"
    or "bwd": "fwd" means use `edges[cur][1]` (cur → ref); "bwd" means
    the connection runs in reverse (someone else points to cur with that
    expression, so to invert we take 1/x).
    """
    row_sym = _unit_latex(graph, path[0])
    ref_sym = _unit_latex(graph, path[-1])

    has_constant = False
    has_offset = False
    # Compose the chain product: for each hop, multiply by the edge
    # expression (or its inverse if direction is "bwd").
    x = 1.0
    for i, cur in enumerate(path[:-1]):
        direction = directions[i]
        if direction == "fwd":
            expr = graph.edges.get(cur, (None, None))[1]
        else:
            pred = path[i + 1]
            expr = graph.edges.get(pred, (None, None))[1]
        if expr is None:
            return None
        for step in (expr if isinstance(expr, list) else [expr]):
            if "constant" in step:
                has_constant = True
            if step.get("op") in ("add", "sub"):
                has_offset = True
        if direction == "fwd":
            x = _apply(expr, x, graph.constants_dict())
        else:
            v = _apply(expr, 1.0, graph.constants_dict())
            if not math.isfinite(v) or v == 0:
                return None
            x /= v
        if not math.isfinite(x):
            return None

    if has_offset:
        return _render_offset_equation_directed(graph, path, directions,
                                                row_sym, ref_sym, graph.conn)
    if has_constant:
        return _render_symbolic_factor(graph, path, row_sym, ref_sym)
    factor_str = _pretty_factor(x)
    if factor_str == "1":
        return f"1\\,{row_sym} = 1\\,{ref_sym}"
    return f"1\\,{row_sym} = {factor_str}\\,{ref_sym}"


def _emit_inverse_path_equation(graph, path, directions):
    """Emit the equation when path was computed `from_id=ref_id, to_id=row_id`.

    `path = [ref, ..., row]`. The first hop is from `ref` toward `row`.
    For each hop we want the equation in the form `x_row = f(x_ref)`,
    so the path is traversed in reverse: for hop i (going from
    `path[i]` to `path[i+1]` in the original forward direction),
    we invert if `directions[i]` was "fwd" (the chain was stored forward
    but we want the inverse direction), and keep "bwd" hops as-is
    (they already represent the inverse).
    """
    row_id = path[-1]
    ref_id = path[0]
    row_sym = _unit_latex(graph, row_id)
    ref_sym = _unit_latex(graph, ref_id)

    has_constant = False
    has_offset = False
    # Walk path in reverse: from path[-1] (row) back to path[0] (ref).
    # Each step corresponds to an original hop. If the original hop was
    # "fwd" (path[i] → edges[path[i]]), we now invert it: 1 / f.
    # If the original hop was "bwd", the relationship was already
    # inverse, so we apply it directly.
    x = 1.0
    for i in range(len(path) - 1, 0, -1):
        original_idx = i - 1
        direction = directions[original_idx]
        cur = path[i]
        prev = path[i - 1]
        if direction == "fwd":
            expr = graph.edges.get(prev, (None, None))[1]
        else:
            expr = graph.edges.get(cur, (None, None))[1]
        if expr is None:
            return None
        for step in (expr if isinstance(expr, list) else [expr]):
            if "constant" in step:
                has_constant = True
            if step.get("op") in ("add", "sub"):
                has_offset = True
        if direction == "fwd":
            v = _apply(expr, 1.0, graph.constants_dict())
            if not math.isfinite(v) or v == 0:
                return None
            x /= v
        else:
            x = _apply(expr, x, graph.constants_dict())
            if not math.isfinite(x):
                return None

    if has_offset:
        return _render_offset_equation_inverse(graph, path, row_id, ref_id, directions)
    if has_constant:
        return _render_symbolic_factor(graph, path, ref_sym, row_sym)

    factor_str = _pretty_factor(x)
    if factor_str == "1":
        return f"1\\,{row_sym} = 1\\,{ref_sym}"
    return f"1\\,{row_sym} = {factor_str}\\,{ref_sym}"


def _render_offset_equation(graph, path, row_sym, ref_sym, constants):
    """Symbolic form for chains with offsets: 'x ref = (f x row) + k'.

    Walks the chain and for any edge that contains add/sub, builds an
    inline equation. For an edge with steps [sub 32, mul 5/9] (°F→°C),
    the form is: x °C = (x °F − 32) × 5/9. Parens wrap the add/sub
    subchain so multiplication binds tightly.

    Used when the path is pure-forward (every hop direction is "fwd").
    """
    for cur in path[:-1]:
        expr = graph.edges.get(cur, (None, None))[1]
        if expr is None:
            continue
        steps = expr if isinstance(expr, list) else [expr]
        ops = [s.get("op") for s in steps]
        if not any(op in ("add", "sub") for op in ops):
            continue
        # Partition: additive subchain (add/sub) vs multiplicative tail.
        additive = [s for s in steps if s.get("op") in ("add", "sub")]
        tail = [s for s in steps if s.get("op") not in ("add", "sub")]
        # Build inner string for the additive subchain, starting with x row.
        inner = f"x\\,{_unit_latex(graph, cur)}"
        for s in additive:
            inner += f" {'+' if s.get('op') == 'add' else '-'} {_operand_latex(s, constants)}"
        # Multiplicative tail
        tail_str = ""
        for s in tail:
            tail_str += f" \\times {_operand_latex(s, constants)}"
        # Wrap inner in parens if followed by multiplication
        if tail_str:
            return f"x\\,{_unit_latex(graph, path[-1])} = ({inner}){tail_str}"
        return f"x\\,{_unit_latex(graph, path[-1])} = {inner}"
    return None


def _render_offset_equation_directed(graph, path, directions, row_sym, ref_sym, constants):
    """Offset-equation form honouring per-hop directions.

    For a "fwd" hop the stored relation is `x_next = f(x_cur)` and we
    display `x_next = (...)`. For a "bwd" hop the stored relation on
    `pred` is `x_pred = f(x_cur)` (i.e., `x_cur = f^{-1}(x_pred)`);
    the equation form has cur on the left.

    For multi-hop chains this picks the first offset edge it finds and
    emits the equation form for that single edge.
    """
    for i, cur in enumerate(path[:-1]):
        direction = directions[i]
        if direction == "fwd":
            expr = graph.edges.get(cur, (None, None))[1]
        else:
            pred = path[i + 1]
            expr = graph.edges.get(pred, (None, None))[1]
        if expr is None:
            continue
        steps = expr if isinstance(expr, list) else [expr]
        ops = [s.get("op") for s in steps]
        if not any(op in ("add", "sub") for op in ops):
            continue
        additive = [s for s in steps if s.get("op") in ("add", "sub")]
        tail = [s for s in steps if s.get("op") not in ("add", "sub")]
        if direction == "bwd":
            # x_pred = f(x_cur) is already in our preferred form.
            inner = f"x\\,{_unit_latex(graph, cur)}"
            for s in additive:
                op = s.get("op")
                inner += f" {'+' if op == 'add' else '-'} {_operand_latex(s, constants)}"
            tail_str = ""
            for s in tail:
                op = s.get("op")
                tail_str += (f" \\times {_operand_latex(s, constants)}"
                              if op == "mul" else
                              f" \\div {_operand_latex(s, constants)}")
            if additive and tail_str:
                return f"x\\,{_unit_latex(graph, pred)} = ({inner}){tail_str}"
            if additive:
                return f"x\\,{_unit_latex(graph, pred)} = {inner}"
            return f"x\\,{_unit_latex(graph, pred)} = {inner}"
        # "fwd": x_next = f(x_cur); emit x_next = ... x_cur ...
        inner = f"x\\,{_unit_latex(graph, cur)}"
        for s in additive:
            op = s.get("op")
            inner += f" {'+' if op == 'add' else '-'} {_operand_latex(s, constants)}"
        tail_str = ""
        for s in tail:
            op = s.get("op")
            tail_str += (f" \\times {_operand_latex(s, constants)}"
                          if op == "mul" else
                          f" \\div {_operand_latex(s, constants)}")
        if tail_str:
            return f"x\\,{_unit_latex(graph, path[-1])} = ({inner}){tail_str}"
        return f"x\\,{_unit_latex(graph, path[-1])} = {inner}"
    return None


def _render_offset_equation_inverse(graph, path, row_id, ref_id, directions):
    """Invert an offset chain and emit 'x row = f⁻¹(x ref)' symbolically.

    The stored chain path = [ref, ..., row] encodes x_next = f(x_cur)
    for each edge (where direction is "fwd"); for "bwd" hops the
    relationship is inverted (x_cur = f(x_next)).
    """
    constants = graph.constants_dict()
    row_sym = _unit_latex(graph, row_id)
    ref_sym = _unit_latex(graph, ref_id)

    # Take the first offset edge (forward or backward).
    for i, cur in enumerate(path[:-1]):
        direction = directions[i]
        if direction == "fwd":
            expr = graph.edges.get(cur, (None, None))[1]
        else:
            pred = path[i + 1]
            expr = graph.edges.get(pred, (None, None))[1]
        if expr is None:
            return None
        steps = expr if isinstance(expr, list) else [expr]
        ops = [s.get("op") for s in steps]
        if not any(op in ("add", "sub") for op in ops):
            continue
        # Partition additive vs multiplicative.
        additive = [s for s in steps if s.get("op") in ("add", "sub")]
        mul_tail = [s for s in steps if s.get("op") == "mul"]
        div_tail = [s for s in steps if s.get("op") == "div"]

        # For a "bwd" hop the chain is already inverted (x_cur = f(x_pred)),
        # so we don't need to apply the algebraic inversion.
        if direction == "bwd":
            # x_row = f(x_ref) directly. Compose additive + mul + div.
            inner = f"x\\,{ref_sym}"
            for s in additive:
                op = s.get("op")
                inner += f" {'+' if op == 'add' else '-'} {_operand_latex(s, constants)}"
            tail_str = ""
            for s in mul_tail:
                tail_str += f" \\times {_operand_latex(s, constants)}"
            for s in div_tail:
                tail_str += f" \\div {_operand_latex(s, constants)}"
            if additive and tail_str:
                return f"x\\,{row_sym} = ({inner}){tail_str}"
            if additive:
                return f"x\\,{row_sym} = {inner}"
            return f"x\\,{row_sym} = {inner}"

        # "fwd" hop: invert. x_cur = f(x_next) means x_ref = f^{-1}(x_row).
        additive_inv = []
        for s in additive:
            new = dict(s)
            new["op"] = "sub" if s.get("op") == "add" else "add"
            additive_inv.append(new)
        mul_tail_inv = [{"op": "div", "value": s["value"]} for s in mul_tail]
        div_tail_inv = [{"op": "mul", "value": s["value"]} for s in div_tail]

        inner = f"x\\,{ref_sym}"
        for s in additive_inv:
            op = s.get("op")
            inner += f" {'+' if op == 'add' else '-'} {_operand_latex(s, constants)}"
        for s in mul_tail_inv:
            inner += f" \\div {_operand_latex(s, constants)}"
        for s in div_tail_inv:
            inner += f" \\times {_operand_latex(s, constants)}"
        if additive and (mul_tail_inv or div_tail_inv):
            return f"x\\,{row_sym} = ({inner})"
        if additive:
            return f"x\\,{row_sym} = {inner}"
        return f"x\\,{row_sym} = {inner}"
    return None


def _render_symbolic_factor(graph, path, row_sym, ref_sym):
    """Symbolic factor form for chains that touch a constant.

    e.g. degree → radian via [pi, div 180] yields '1° = π/180 rad'.
    """
    # Compose the factor symbolically, substituting constants inline.
    numerator_parts = []
    denominator_parts = []
    for cur in path[:-1]:
        expr = graph.edges[cur][1]
        steps = expr if isinstance(expr, list) else [expr]
        for s in steps:
            if "constant" in s:
                sym = _constant_symbol(graph.conn, s["constant"])
                numerator_parts.append(sym)
            elif s.get("op") == "div":
                d = s.get("value")
                if isinstance(d, str) and "/" in d:
                    n, dn = d.split("/")
                    numerator_parts.append(n)
                    denominator_parts.append(dn)
                else:
                    denominator_parts.append(str(int(_fraction(d))))
            elif s.get("op") == "mul":
                v = s.get("value")
                if isinstance(v, str) and "/" in v:
                    n, d = v.split("/")
                    numerator_parts.append(n)
                    denominator_parts.append(d)
                else:
                    v_int = int(_fraction(v))
                    if v_int == 1:
                        pass
                    else:
                        numerator_parts.append(str(v_int))
            elif s.get("op") is None and "value" in s:
                v = s.get("value")
                if isinstance(v, str) and "/" in v:
                    n, d = v.split("/")
                    numerator_parts.append(n)
                    denominator_parts.append(d)
                else:
                    numerator_parts.append(str(_fraction(v)))

    num_str = " \\cdot ".join(numerator_parts) if numerator_parts else "1"
    den_str = " \\cdot ".join(denominator_parts) if denominator_parts else None
    if den_str:
        factor = f"\\frac{{{num_str}}}{{{den_str}}}"
    else:
        factor = num_str
    return f"1\\,{row_sym} = {factor}\\,{ref_sym}"


def _operand_latex(step, conn_or_constants):
    """Render a single step's operand as LaTeX.

    Pulls constant symbols from the DB if a connection is available;
    otherwise falls back to the constant id string.
    """
    if "constant" in step:
        cid = step["constant"]
        if hasattr(conn_or_constants, "execute"):
            row = conn_or_constants.execute(
                "SELECT symbol FROM constant WHERE id = ?", (cid,)
            ).fetchone()
            if row:
                return row["symbol"]
        return cid
    val = step.get("value")
    if isinstance(val, str) and "/" in val:
        n, d = val.split("/", 1)
        return f"\\frac{{{n}}}{{{d}}}"
    try:
        v = _fraction(val)
        if not math.isfinite(v):
            return "?"
        if isinstance(val, (int, float)) and v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return f"{v:.6g}"
    except (ValueError, TypeError):
        return str(val)


def _root_value(graph, unit_or_compound_id):
    if unit_or_compound_id in graph.unit_rows:
        return graph.root_value(unit_or_compound_id)
    if unit_or_compound_id in graph.compound_rows:
        return graph.root_value_compound(unit_or_compound_id)
    return None