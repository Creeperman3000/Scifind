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

from scifind_lib.units import format_compound_unit_symbol

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
        """Load a unit row into the graph if it's not already present.

        Returns the edge (ref_id, expr) or None if the unit doesn't exist.
        A compound_unit row is treated as a graph root (no outgoing edge):
        when it belongs to this quantity it was captured by the constructor;
        a *cross-quantity* compound (e.g. `kilogram`, `metre_cubed`) is loaded
        lazily and registered here so references that pass through it, such as
        `pound → kilogram`, resolve instead of hitting an orphan.
        """
        if unit_id in self.edges or unit_id in self.unit_rows:
            return self.edges.get(unit_id)
        if unit_id in self.compound_rows:
            return None  # in-quantity compound = root, no edge
        row = self.conn.execute(
            "SELECT id, quantity_id, symbol, reference_unit_id, reference_expr "
            "FROM unit WHERE id = ?",
            (unit_id,),
        ).fetchone()
        if row is None:
            # Not a plain unit: it may be a compound belonging to another
            # quantity. Load it as a compound root so the chain continues.
            crow = self.conn.execute(
                "SELECT id, quantity_id, unit, symbol_overwrite, system, "
                "is_base, reference_unit_id, reference_expr "
                "FROM compound_unit WHERE id = ?",
                (unit_id,),
            ).fetchone()
            if crow is None:
                return None
            self.compound_rows[unit_id] = dict(crow)
            expr = None
            if crow["reference_expr"]:
                try:
                    expr = json.loads(crow["reference_expr"])
                except (json.JSONDecodeError, TypeError):
                    expr = None
            self.edges[unit_id] = (crow["reference_unit_id"], expr)
            return self.edges[unit_id]
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

    def _is_temperature_unit(self, unit_id):
        """Check if a unit_id is a temperature unit (any quantity)."""
        row = self.conn.execute(
            "SELECT quantity_id FROM unit WHERE id = ? UNION SELECT quantity_id FROM compound_unit WHERE id = ?",
            (unit_id, unit_id),
        ).fetchone()
        return row and row["quantity_id"] == "temperature"

    def root_value_differential(self, unit_id):
        """Return the differential scale factor for a temperature unit,
        or the normal root_value for non-temperature units.

        For temperature units, this returns the ratio of 1 unit step
        in the root temperature unit (kelvin/degree_celsius), e.g.:
        - kelvin, degree_celsius → 1
        - degree_fahrenheit, degree_rankine → 5/9
        - degree_reaumur → 5/4
        """
        if not self._is_temperature_unit(unit_id):
            return self.root_value(unit_id)
        # Temperature differential scales relative to kelvin/celsius (both step=1)
        diff_scales = {
            "kelvin": 1.0,
            "degree_celsius": 1.0,
            "degree_fahrenheit": 5.0 / 9.0,
            "degree_rankine": 5.0 / 9.0,
            "degree_reaumur": 5.0 / 4.0,
        }
        return diff_scales.get(unit_id, 1.0)

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

        Temperature parts use their differential scale (1 for K/°C, 5/9
        for °F/°R, 5/4 for °Ré) rather than the affine absolute value.
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
            v = self.root_value_differential(uid)
            if v is None or not math.isfinite(v):
                return None
            prefix = part.get("prefix")
            if prefix is not None:
                try:
                    v = v * (10.0 ** int(prefix))
                except (TypeError, ValueError):
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
        return _render_numeric_equation(graph, row_id, ref_id)
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
    factor_str = _single_factor_value(ratio)
    row_sym = _unit_latex(graph, row_id)
    ref_sym = _unit_latex(graph, ref_id)
    return f"1\\,{row_sym} = {factor_str}\\,{ref_sym}"


# ---------- LaTeX emission ----------

def _prefix_symbol_latex(conn, exp):
    """LaTeX for an SI prefix symbol (e.g. 'c', '\\mu ').

    Pulls the localized (en-us) symbol for a prefix exponent from the DB
    and returns it as a raw string: command-like symbols (e.g. micro) are
    returned verbatim (preserving any trailing spacing so they don't
    merge with the following unit symbol). The caller is expected to
    wrap the final joined symbol in \\mathrm{} (typically via
    ``format_compound_unit_symbol`` which now does so per-part).
    """
    row = conn.execute(
        "SELECT symbol FROM si_prefix WHERE id = ?", (str(exp),)
    ).fetchone()
    if not row:
        return ""
    try:
        symbol = json.loads(row["symbol"]).get("en-us", "")
    except (json.JSONDecodeError, TypeError):
        symbol = row["symbol"]
    if not symbol:
        return ""
    return symbol


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

        def _part_symbol(uid):
            if uid in graph.unit_rows:
                return graph.unit_rows[uid].get("symbol") or uid
            # Cross-quantity part not loaded into this graph yet — fall
            # back to the DB so we don't render the bare id.
            part_row = graph.conn.execute(
                "SELECT symbol FROM unit WHERE id = ?", (uid,)).fetchone()
            return part_row["symbol"] if part_row else uid

        sym_map = {uid: _part_symbol(uid)
                   for part in parts
                   if (uid := part.get("unit")) is not None}
        return format_compound_unit_symbol(
            json.dumps(parts),
            unit_symbol=lambda uid: sym_map.get(uid, uid),
            prefix_symbol=lambda exp: _prefix_symbol_latex(graph.conn, int(exp)),
        )
    return unit_id


def _unit_latex(graph, unit_id):
    sym = _unit_symbol(graph, unit_id)
    if not sym:
        return ""
    if "\\mathrm{" in sym:
        return sym
    return f"\\mathrm{{{sym}}}"


def _unit_latex_for_var(graph, unit_id):
    """Like _unit_latex but strips \\mathrm{} if present for use in subscripts/vars."""
    sym = _unit_latex(graph, unit_id)
    if sym.startswith("\\mathrm{") and sym.endswith("}"):
        return sym[len("\\mathrm{"):-1]
    return sym


def _pretty_factor(x):
    if x == 0:
        return "0"
    if math.isinf(x):
        return "\\infty"
    ax = abs(x)
    sign = "-" if x < 0 else ""
    if ax >= 1e4 or ax < 1e-4:
        # Normalise to mantissa in [1, 10). If the mantissa rounds to
        # 10.0 (or 1.0 in the case of a 0.99... value), bump to the next
        # decade so the display stays tidy.
        exp = int(math.floor(math.log10(ax)))
        mant = x / (10 ** exp)
        if 0.1 <= abs(mant) < 1:
            mant *= 10
            exp -= 1
        if abs(mant) >= 10 or abs(mant) >= 9.999995:
            mant /= 10
            exp += 1
        # Format the mantissa to 6 significant digits (no exponential),
        # then trim trailing zeros so e.g. 9.9999999999 displays as 9.99999.
        # This avoids the `:4g` rounding-up-to-10 problem.
        mant_str = f"{mant:.6f}".rstrip("0").rstrip(".")
        return f"{sign}{mant_str}\\times10^{{{exp}}}"
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return f"{x:.6g}"


def render_equation(graph, row_id, ref_id):
    """Build the conversion-cell LaTeX.

    Picks the form by walking the path between row and ref:
    - Offset chain → equation form: `x <ref> = x <row> ± k ...`
    - Single hop, single clean factor (no constant, no offset) → direct
      equality: `1 <row> = N <ref>`
    - Otherwise → chain form: `1 <row> = <chain> [= N] <ref>` where
      `<chain>` is the multiplicative walk with `×` between factors and
      `÷` for divisors, repeated same-value factors collapsed into
      powers (e.g. `× 60 × 60 → 60^2`).
    - Cross-quantity or no path → numeric fallback from root values.
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
    """Emit the chain-style equation for a path.

    `directions` is per-hop "fwd" or "bwd". A "bwd" hop means the
    stored edge is on the next node; we invert it: mul↔div, add↔sub.
    """
    return _render_chain(graph, path, directions, invert=False)


def _emit_inverse_path_equation(graph, path, directions):
    """Emit the chain-style equation for an inverse-direction path."""
    return _render_chain(graph, path, directions, invert=True)


def _render_chain(graph, path, directions, invert):
    """Core chain rendering. Used by both forward and inverse paths.

    Picks the form by path shape:
    - Offset present → affine equation form (temperature etc.).
    - Single hop, single clean factor → direct equality
      `1 row = N ref` (no chain notation).
    - Single hop with constant (1 or 2 factors) → chain form
      `1 row = <chain> ref` (no final value).
    - All-divisor chain → exact reciprocal `1 row = 1/(...) ref`.
    - Multi-hop → chain form `1 row = <chain> = N ref`.
    """
    row_id = path[0]
    ref_id = path[-1]
    row_sym = _unit_latex(graph, row_id)
    ref_sym = _unit_latex(graph, ref_id)

    groups, has_constant, has_offset = _collect_factors(
        graph, path, directions, invert)
    if has_offset:
        # Offset chain: affine equation form (preserves the offset).
        return _render_affine_equation(graph, path, directions, invert)

    factors = [f for group in groups for f in group]
    if not factors:
        return f"1\\,{row_sym} = 1\\,{ref_sym}"

    collapsed = _collapse_factors(factors)
    multi_hop = len(path) > 2
    n_collapsed = len(collapsed)

    if n_collapsed == 1 and not multi_hop:
        # Single factor, single hop → direct equality.
        f0 = collapsed[0]
        if f0["kind"] == "const":
            return f"1\\,{row_sym} = {_factor_text(f0, graph)}\\,{ref_sym}"
        v = _fraction(f0["value"])
        v = v if f0["op"] == "mul" else 1.0 / v
        v = v ** f0.get("count", 1)
        return f"1\\,{row_sym} = {_single_factor_value(v)}\\,{ref_sym}"

    # All-divisor chain → render as an exact reciprocal (no decimal).
    if all(f["op"] == "div" for f in collapsed):
        den = _denominator_latex(collapsed, graph)
        return f"1\\,{row_sym} = 1/{den}\\,{ref_sym}"

    chain_str = _format_chain(collapsed, has_constant, groups, graph)
    final = 1.0
    for f in collapsed:
        v = _fraction(f["value"]) if f["kind"] == "num" else f["value"]
        base = v if f["op"] == "mul" else 1.0 / v
        final *= base ** f.get("count", 1)
    if multi_hop:
        return (f"1\\,{row_sym} = {chain_str} = "
                f"{_pretty_factor_value(final)}\\,{ref_sym}")
    # Single-hop with constant: chain only, no final.
    return f"1\\,{row_sym} = {chain_str}\\,{ref_sym}"


def _collect_factors(graph, path, directions, invert):
    """Walk the path and return (edge_groups, has_constant, has_offset).

    `edge_groups` is a list (one entry per hop, in path order) of factor
    lists. Each factor is a dict: {"op": "mul"|"div", "kind": "num"|"const",
    "value": float}. The "value" is always positive (sign carried by op).

    A "bwd" hop inverts the stored edge (mul↔div, add↔sub). When `invert`
    is set (the whole path direction is inverted) every hop is flipped too.
    """
    groups = []
    has_constant = False
    has_offset = False
    constants = graph.constants_dict()
    for i, cur in enumerate(path[:-1]):
        direction = directions[i]
        if direction == "fwd":
            expr = graph.edges.get(cur, (None, None))[1]
        else:
            pred = path[i + 1]
            expr = graph.edges.get(pred, (None, None))[1]
        group = []
        if expr is not None:
            steps = expr if isinstance(expr, list) else [expr]
            for s in steps:
                if s is None:
                    continue
                op = s.get("op")
                if op in ("add", "sub"):
                    has_offset = True
                    continue
                # A constant-substitution step ({"constant": "pi"}) has no
                # explicit "op"; treat it as multiplication.
                if op is None and "constant" in s:
                    op = "mul"
                if direction == "bwd":
                    op = {"mul": "div", "div": "mul"}.get(op, op)
                if "constant" in s:
                    cid = s["constant"]
                    v = constants.get(cid)
                    if v is None or not math.isfinite(v):
                        continue
                    group.append({"op": op, "kind": "const",
                                  "value": v, "cid": cid})
                    has_constant = True
                elif op in ("mul", "div"):
                    v = _fraction(s.get("value"))
                    if not math.isfinite(v) or v == 0:
                        continue
                    group.append({"op": op, "kind": "num", "value": v})
        if invert:
            for f in group:
                f["op"] = "div" if f["op"] == "mul" else "mul"
        groups.append(group)
    return groups, has_constant, has_offset


def _factor_sig(f):
    """Identity for cancellation/consumption: (kind, op, canonical value)."""
    if f["kind"] == "num":
        v = f["value"]
        canon = int(v) if (isinstance(v, float) and v.is_integer() and abs(v) < 1e15) else repr(v)
        return ("num", f["op"], canon)
    return ("const", f["op"], f.get("cid", id(f)))


def _collapse_factors(factors):
    """Combine repeated same factors and cancel mul↔div pairs.

    Cancellation keys on (kind, canonical value) across BOTH op kinds so
    `× π` followed by `÷ π` cancels out (the old code keyed on the op,
    so it could never cancel across directions). Constants are keyed by
    `cid`; numerics by integer value when integral.
    """
    recs = {}    # key -> [n_mul, n_div, first_value]
    order = []   # keys in first-seen order (stable output ordering)
    for f in factors:
        if f["kind"] == "num":
            v = f["value"]
            canon = int(v) if (isinstance(v, float) and v.is_integer() and abs(v) < 1e15) else repr(v)
            key = ("num", canon)
        else:
            key = ("const", f.get("cid", id(f)))
        if key not in recs:
            recs[key] = [0, 0, f["value"]]
            order.append(key)
        rec = recs[key]
        if f["op"] == "mul":
            rec[0] += 1
        else:
            rec[1] += 1
    kept = []
    for key in order:
        n_mul, n_div, value = recs[key]
        diff = n_mul - n_div
        if diff == 0:
            continue
        out = {"op": "mul" if diff > 0 else "div",
               "kind": key[0], "value": value, "count": abs(diff)}
        if key[0] == "const":
            out["cid"] = key[1]
        kept.append(out)
    return kept


def _factor_text(f, graph):
    """LaTeX for a single (collapsed) factor's value, e.g. `60^{2}` or `π`."""
    if f["kind"] == "const":
        base = _constant_latex_for(f["value"], graph)
    else:
        v = f["value"]
        if isinstance(v, float) and v.is_integer() and abs(v) < 1e7:
            base = str(int(v))
        else:
            base = _pretty_factor(v)
    count = f.get("count", 1)
    if count > 1:
        return f"{base}^{{{count}}}"
    return base


def _render_factor_seq(factors, graph):
    """Render factors in order with ×/÷ separators (leading × omitted)."""
    parts = []
    for i, f in enumerate(factors):
        t = _factor_text(f, graph)
        op = "\\times" if f["op"] == "mul" else "\\div"
        if i == 0 and f["op"] == "mul":
            parts.append(t)
        else:
            parts.append(f"{op} {t}")
    return " ".join(parts)


def _format_chain(collapsed, has_constant, groups, graph):
    """Format a list of collapsed factors into a readable chain.

    With a constant (π etc.) the chain is reordered so the constant reads
    naturally at the head (forward: `π ÷ 180`) or at the tail when it is
    a divisor (inverted: `180 ÷ π`). Parens around the constant head are
    used only when the head contains a divisor AND a multiplying factor
    follows (the parsec case) — `1° = π ÷ 180 rad` and
    `1′ = π ÷ 180 ÷ 60 rad` stay unparenthesised.
    """
    cf = next((f for f in collapsed if f["kind"] == "const"), None)
    if cf is None:
        return _format_generic_chain(collapsed, graph)

    raw = None
    for g in groups:
        if any(fd.get("kind") == "const" and fd.get("cid") == cf.get("cid") for fd in g):
            raw = g
            break

    if raw is None:
        seg = [cf]
        rest = [f for f in collapsed if f is not cf]
    else:
        sigs = {}
        for f in collapsed:
            s = _factor_sig(f)
            sigs[s] = sigs.get(s, 0) + 1

        def avail(s):
            return sigs.get(s, 0) > 0

        def consume(s):
            sigs[s] = sigs.get(s, 0) - 1

        consume(_factor_sig(cf))
        seg = [cf]
        for fd in raw:
            if fd.get("kind") == "const" and fd.get("cid") == cf.get("cid"):
                continue
            if fd["op"] == "div":
                s = _factor_sig(fd)
                if avail(s):
                    seg.append(fd)
                    consume(s)
        rest = []
        for f in collapsed:
            s = _factor_sig(f)
            if avail(s):
                rest.append(f)
                consume(s)

    if cf["op"] == "mul":
        return _join_const_head(seg, rest, graph)
    rest = [f for f in collapsed if f is not cf]
    return _join_const_divisor(cf, rest, graph)


def _join_const_head(seg, rest, graph):
    """Const head first, then remaining muls and divs (parens rule)."""
    seg_str = _render_factor_seq(seg, graph)
    has_div = any(f["op"] == "div" for f in seg)
    rem_muls = [f for f in rest if f["op"] == "mul"]
    rem_divs = [f for f in rest if f["op"] == "div"]
    parts = []
    if has_div and rem_muls:
        parts.append(f"({seg_str})")
    else:
        parts.append(seg_str)
    for f in rem_muls + rem_divs:
        t = _factor_text(f, graph)
        op = "\\times" if f["op"] == "mul" else "\\div"
        parts.append(f"{op} {t}")
    return " ".join(parts)


def _join_const_divisor(cf, rest, graph):
    """Const is a divisor → emit muls first, then other divs, then ÷ const."""
    muls = [f for f in rest if f["op"] == "mul"]
    divs = [f for f in rest if f["op"] == "div"]
    items = [("\\times", _factor_text(f, graph)) for f in muls]
    items += [("\\div", _factor_text(f, graph)) for f in divs]
    items.append(("\\div", _factor_text(cf, graph)))
    parts = []
    for i, (op, t) in enumerate(items):
        if i == 0 and op == "\\times":
            parts.append(t)
        else:
            parts.append(f"{op} {t}")
    return " ".join(parts)


def _format_generic_chain(collapsed, graph):
    """Numeric chain without constants: muls first, then divs (no lead ÷)."""
    muls = [f for f in collapsed if f["op"] == "mul"]
    divs = [f for f in collapsed if f["op"] == "div"]
    parts = []
    for i, f in enumerate(muls):
        t = _factor_text(f, graph)
        parts.append(t if i == 0 else f"\\times {t}")
    for f in divs:
        parts.append(f"\\div {_factor_text(f, graph)}")
    return " ".join(parts)


def _single_factor_value(v):
    """Render a single-factor value, using exact forms when clean.

    `1/12`, `1/60`, `1/10^{8}`, `10^{8}` instead of `0.0833333`,
    `0.0166667`, `1e-08`, `100000000`.
    """
    if v == 0:
        return "0"
    if v > 0:
        r = 1.0 / v
        r_int = round(r)
        if abs(r - r_int) <= 1e-9 * max(1.0, abs(r)) and r_int > 1:
            if r_int < 10000:
                return f"1/{r_int}"
            log10 = math.log10(r_int)
            if abs(log10 - round(log10)) < 1e-9:
                return f"1/10^{{{int(round(log10))}}}"
            return f"1/{_pretty_factor(r_int)}"
    if v >= 1e4:
        log10 = math.log10(v)
        if abs(log10 - round(log10)) < 1e-9:
            return f"10^{{{int(round(log10))}}}"
    return _pretty_factor_value(v)


def _denominator_latex(collapsed, graph):
    """Render an all-divisor chain as the exact denominator of `1/(…)`."""
    texts = [_factor_text(f, graph) for f in collapsed]
    if len(texts) == 1:
        t = texts[0]
        if "\\times" in t or "\\div" in t:
            return "(" + t + ")"
        return t
    return "(" + " \\times ".join(texts) + ")"


def _constant_latex_for(value, graph):
    """Return the LaTeX symbol for the constant whose value matches.

    Looks up the constant table by numeric value and returns its symbol.
    """
    if graph is None or not hasattr(graph, "conn"):
        return f"{value:.6g}"
    row = graph.conn.execute(
        "SELECT symbol FROM constant WHERE value IS NOT NULL "
        "ORDER BY ABS(value - ?) LIMIT 1",
        (value,),
    ).fetchone()
    if row is None:
        return f"{value:.6g}"
    return row["symbol"]


def _pretty_factor_value(x):
    """Pretty-print a numeric value for the cell's final = N ref term."""
    if x == 0:
        return "0"
    if isinstance(x, float) and x.is_integer() and abs(x) < 1e15:
        return str(int(x))
    return _pretty_factor(x)


def _render_affine_equation(graph, path, directions, invert):
    """Equation form for offset chains: `T_ref = a·T_row + b`.

    Composes the affine mapping x_ref = a·x_row + b across the whole path
    (bwd hops invert the stored edge first), then picks the cleanest form:
    - a ≈ 1            → `T_ref = T_row ± b`
    - b ≈ 0            → `a × T_row`
    - −b/a nice        → `(T_row − c) × a`    (e.g. `(T_F − 32) × 5/9`)
    - otherwise        → `a × T_row + b`      (e.g. `9/5 × T_K − 459.67`)
    """
    constants = graph.constants_dict()
    a, b = 1.0, 0.0
    for i, cur in enumerate(path[:-1]):
        direction = directions[i]
        if direction == "fwd":
            expr = graph.edges.get(cur, (None, None))[1]
        else:
            pred = path[i + 1]
            expr = graph.edges.get(pred, (None, None))[1]
        if expr is None:
            return None
        m, c = _affine_of_steps(expr, constants)
        if not math.isfinite(m) or m == 0:
            return None
        if direction == "bwd":
            m, c = 1.0 / m, -c / m
        a, b = m * a, m * b + c
    if invert:
        if a == 0 or not math.isfinite(a):
            return None
        a, b = 1.0 / a, -b / a

    row_sym = _unit_latex(graph, path[0])
    ref_sym = _unit_latex(graph, path[-1])
    var = _temp_var_fn(graph)
    lhs = var(ref_sym)
    body = var(row_sym)

    if abs(a - 1.0) < 1e-9:
        if abs(b) < 1e-12:
            return f"{lhs} = {body}"
        if b < 0:
            return f"{lhs} = {body} - {_nice_num(-b)}"
        return f"{lhs} = {body} + {_nice_num(b)}"

    if abs(b) < 1e-9 * max(1.0, abs(a)):
        return f"{lhs} = {_nice_num(a)} \\times {body}"

    c = -b / a
    if _nice_offset(c):
        if c < 0:
            return f"{lhs} = ({body} + {_nice_num(-c)}) \\times {_nice_num(a)}"
        return f"{lhs} = ({body} - {_nice_num(c)}) \\times {_nice_num(a)}"
    out = f"{lhs} = {_nice_num(a)} \\times {body}"
    if abs(b) >= 1e-12:
        if b < 0:
            out += f" - {_nice_num(-b)}"
        else:
            out += f" + {_nice_num(b)}"
    return out


def _affine_of_steps(expr, constants):
    """Compute the affine (m, c) of a step list: f(x) = m·x + c."""
    m, c = 1.0, 0.0
    if expr is None:
        return m, c
    steps = expr if isinstance(expr, list) else [expr]
    for s in steps:
        if s is None:
            continue
        if "constant" in s:
            operand = constants.get(s["constant"], float("nan"))
        else:
            operand = _fraction(s.get("value"))
        if not math.isfinite(operand) or operand == 0:
            continue
        op = s.get("op")
        if op is None or op == "mul":
            m *= operand
            c *= operand
        elif op == "div":
            m /= operand
            c /= operand
        elif op == "add":
            c += operand
        elif op == "sub":
            c -= operand
    return m, c


def _temp_var_fn(graph):
    if getattr(graph, "quantity_id", None) == "temperature":
        return lambda sym: f"T_{{{sym}}}"
    return lambda sym: f"x\\,{sym}"


def _nice_num(x):
    """Render a coefficient readably: int, simple fraction, ≤2 dp, else .6g."""
    r = round(x)
    if abs(x - r) < 1e-9 and abs(r) < 1e15:
        return str(int(r))
    for d in range(2, 21):
        n = x * d
        nr = round(n)
        if abs(n - nr) < 1e-9 and abs(nr) <= 1000:
            return f"{int(nr)}/{d}"
    r2 = round(x, 2)
    if abs(x - r2) < 1e-6:
        return f"{r2:.2f}".rstrip("0").rstrip(".")
    return f"{x:.6g}"


def _nice_offset(c):
    """True when c = −b/a is a clean zero-point (int or ≤ 2 decimal places)."""
    if abs(c - round(c)) < 1e-9:
        return True
    r2 = round(c, 2)
    return abs(c - r2) < 1e-6


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