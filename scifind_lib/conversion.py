"""Reference-graph unit conversion.

Each unit row carries `factor`, `is_factor_reciprocal`, `constant_id`,
`constant_operator_id` (`mul`/`div`/`add`/`sub`) and `offset`. The
conversion formula is:

    F   = (factor if not reciprocal else 1/factor)
    x_ref = (F or F×/÷ constant_value) * (x_row + offset) ± constant_value

where `mul`/`div` scale F by the constant and `add`/`sub` shift the
reference value by it (used for temperature absolute zero).

The renderer walks the graph to compose multi-hop chains and emits LaTeX
in a few standard forms (direct equality, affine equation, chain with
final value). Cycles/orphans are detected at load time — the app
refuses to start if the graph is broken.
"""

from __future__ import annotations

import json
import math

from scifind_lib.units import format_compound_unit_symbol

logger = __import__("logging").getLogger(__name__)


# ---------- graph ----------

class UnitGraphError(Exception):
    pass


class UnitGraph:
    """Walk the per-quantity unit reference graph and resolve root values.

    Cross-quantity references (e.g. hectare of area referencing metre of
    length) are loaded lazily so the graph can cross quantity boundaries
    without cycles.
    """

    # Columns we read from the unit / compound_unit tables for the
    # reference graph. Same edge columns on both tables; unit_rows also
    # reads symbol/system/is_base, compound_rows reads unit/symbol_overwrite.
    _EDGE_COLS = (
        "reference_unit_id", "factor", "is_factor_reciprocal",
        "constant_id", "constant_operator_id", "offset",
    )
    _UNIT_COLS = "id, symbol, system, is_base, " + ", ".join(_EDGE_COLS)
    _COMPOUND_COLS = "id, unit, symbol_overwrite, system, is_base, " + ", ".join(_EDGE_COLS)

    def __init__(self, conn, quantity_id):
        self.conn = conn
        self.quantity_id = quantity_id
        self.unit_rows: dict = {}
        self.compound_rows: dict = {}
        # edges: id -> (ref_id, factor, is_reciprocal, constant_id,
        #               constant_operator_id, offset)
        self.edges: dict = {}
        for row in conn.execute(
            f"SELECT {self._UNIT_COLS} FROM unit WHERE quantity_id = ?",
            (quantity_id,),
        ).fetchall():
            self._install(row, in_unit=True)
        for row in conn.execute(
            f"SELECT {self._COMPOUND_COLS} FROM compound_unit WHERE quantity_id = ?",
            (quantity_id,),
        ).fetchall():
            self._install(row, in_unit=False)

    def _install(self, row, *, in_unit):
        uid = row["id"]
        (self.unit_rows if in_unit else self.compound_rows)[uid] = dict(row)
        self.edges[uid] = self._make_edge(row)

    @staticmethod
    def _make_edge(row):
        def num(v, default):
            return default if v is None else v
        return (
            row["reference_unit_id"],
            num(row["factor"], 1.0),
            num(row["is_factor_reciprocal"], 0),
            row["constant_id"],
            row["constant_operator_id"] or "mul",
            num(row["offset"], 0.0),
        )

    def _ensure_unit_loaded(self, unit_id):
        """Load a unit row into the graph if not already present."""
        if unit_id in self.edges:
            return self.edges[unit_id]
        row = self.conn.execute(
            f"SELECT {self._UNIT_COLS} FROM unit WHERE id = ?", (unit_id,)
        ).fetchone()
        in_unit = True
        if row is None:
            row = self.conn.execute(
                f"SELECT {self._COMPOUND_COLS} FROM compound_unit WHERE id = ?",
                (unit_id,),
            ).fetchone()
            if row is None:
                return None
            in_unit = False
        self._install(row, in_unit=in_unit)
        return self.edges[unit_id]

    def all_unit_ids(self):
        return list(self.unit_rows)

    def all_compound_ids(self):
        return list(self.compound_rows)

    def _constant_value(self, constant_id):
        if not constant_id:
            return 1.0
        row = self.conn.execute(
            "SELECT value FROM constant WHERE id = ? AND value IS NOT NULL",
            (constant_id,),
        ).fetchone()
        return float(row["value"]) if row else float("nan")

    def _effective_factor(self, factor, is_reciprocal, constant_id, constant_operator="mul"):
        """The multiplier F in `x_ref = F * (x_row + offset) + shift`.

        F = (1/factor if reciprocal else factor), combined with the
        constant per `constant_operator`: `mul` scales by it, `div`
        divides by it, and `add`/`sub` leave F unchanged (the constant
        only shifts the reference value).
        """
        f = (1.0 / factor) if is_reciprocal else factor
        if constant_id:
            c = self._constant_value(constant_id)
            if constant_operator == "div":
                f /= c
            elif constant_operator != "add" and constant_operator != "sub":
                f *= c
        return f

    def _constant_shift(self, constant_id, constant_operator):
        """Additive contribution (reference units) of an add/sub constant."""
        if not constant_id or constant_operator not in ("add", "sub"):
            return 0.0
        c = self._constant_value(constant_id)
        return c if constant_operator == "add" else -c

    def _is_temperature_unit(self, unit_id):
        row = self.conn.execute(
            "SELECT quantity_id FROM unit WHERE id = ? UNION "
            "SELECT quantity_id FROM compound_unit WHERE id = ?",
            (unit_id, unit_id),
        ).fetchone()
        return bool(row and row["quantity_id"] == "temperature")

    def root_value_differential(self, unit_id):
        """Differential scale for temperature units (1 for K/°C, 5/9 for °F/°R, 5/4 for °Ré)."""
        if not self._is_temperature_unit(unit_id):
            return self.root_value(unit_id)
        scales = {
            "kelvin": 1.0,
            "degree_celsius": 1.0,
            "degree_fahrenheit": 5.0 / 9.0,
            "degree_rankine": 5.0 / 9.0,
            "degree_reaumur": 5.0 / 4.0,
        }
        return scales.get(unit_id, 1.0)

    def path_to_root(self, unit_id):
        """[unit_id, ..., root] or None on cycle/orphan."""
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
                return path
            unit_id = nxt

    def root_value(self, unit_id):
        """Ratio of `1 unit_id` in the root unit. None if unreachable.

        Multiplicative only (offset is ignored — temperature differential
        scale applies). For compounds that are themselves roots, account
        for the compound's parts via `root_value_compound_of_compound`.
        """
        path = self.path_to_root(unit_id)
        if path is None:
            return None
        x = 1.0
        for cur in path[:-1]:
            edge = self._ensure_unit_loaded(cur)
            if edge is None:
                return None
            ref_id, factor, is_rec, cid, cop, offset = edge
            x *= self._effective_factor(factor, is_rec, cid, cop)
            if not math.isfinite(x):
                return None
        if path[-1] in self.compound_rows:
            compound_root = self.root_value_compound_of_compound(path[-1])
            if compound_root is None:
                return None
            x *= compound_root
        return x

    def root_value_compound_of_compound(self, compound_id):
        """Root value of a compound expressed in raw unit-parts.

        For `metre_per_second`, returns 1 (1 m/s = 1 m × 1 /s).
        Temperature parts use their differential scale.
        """
        row = self.compound_rows.get(compound_id)
        if row is None:
            return None
        try:
            parts = json.loads(row["unit"])
        except (ValueError, TypeError):
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

def validate_graph(conn):
    """Walk every quantity's unit graph; raise on cycle or orphan."""
    for qid_row in conn.execute("SELECT DISTINCT quantity_id FROM unit").fetchall():
        qid = qid_row["quantity_id"]
        graph = UnitGraph(conn, qid)
        for uid in list(graph.unit_rows):
            if graph.path_to_root(uid) is None:
                raise UnitGraphError(
                    f"quantity '{qid}' unit '{uid}' has no path to root "
                    f"(cycle or orphan — graph integrity violated)"
                )


# ---------- conversion ----------

def _affine_to_root(graph, unit_id):
    """Return (m, b) so that x_root = m * x_unit + b.

    Composes each edge's effective factor and offset.
    """
    path = graph.path_to_root(unit_id)
    if path is None:
        return None
    m, b = 1.0, 0.0
    for cur in path[:-1]:
        edge = graph._ensure_unit_loaded(cur)
        if edge is None:
            return None
        ref_id, factor, is_rec, cid, cop, offset = edge
        m_edge = graph._effective_factor(factor, is_rec, cid, cop)
        if not math.isfinite(m_edge) or m_edge == 0:
            return None
        # x_ref = m_edge * (x_cur + offset) + shift. x_cur = m * x_unit + b.
        # So x_ref = m_edge * m * x_unit + m_edge * b + m_edge * offset + shift.
        shift = graph._constant_shift(cid, cop)
        m, b = m_edge * m, m_edge * b + m_edge * offset + shift
    if path[-1] in graph.compound_rows:
        compound_root = graph.root_value_compound_of_compound(path[-1])
        if compound_root is None or not math.isfinite(compound_root) or compound_root == 0:
            return None
        m *= compound_root
    return m, b


def convert_value(value, from_id, to_id, graph):
    """Convert `value` expressed in `from_id` to `to_id`.

    Walks each side to the root and composes affine transforms. None when
    either side is unreachable.
    """
    if from_id == to_id:
        return value
    from_aff = _affine_to_root(graph, from_id)
    to_aff = _affine_to_root(graph, to_id)
    if from_aff is None or to_aff is None:
        return None
    m_from, b_from = from_aff
    m_to, b_to = to_aff
    if m_to == 0:
        return None
    return (m_from * value + b_from - b_to) / m_to


# ---------- path finder between two units ----------

def path_between(graph, from_id, to_id):
    """[from_id, ..., to_id] or None. BFS in both directions."""
    if from_id == to_id:
        return [from_id]
    # Forward search from from_id
    fwd_visited = {from_id: [from_id]}
    fwd_queue = [from_id]
    # Backward search from to_id (walk edges in reverse)
    bwd_visited = {to_id: [to_id]}
    bwd_queue = [to_id]
    # Alternate expanding front and back; stop when they meet.
    while fwd_queue or bwd_queue:
        for _ in range(len(fwd_queue)):
            cur = fwd_queue.pop(0)
            path = fwd_visited[cur]
            # Forward neighbours: cur's edge leads to ref, and nodes
            # pointing to cur.
            neighbours = []
            edge = graph.edges.get(cur)
            if edge is not None and edge[0] is not None:
                neighbours.append(edge[0])
            for other_id, e in graph.edges.items():
                if e[0] == cur and other_id != cur and other_id not in fwd_visited:
                    neighbours.append(other_id)
            for nxt in neighbours:
                if nxt in bwd_visited:
                    return path + bwd_visited[nxt]
                if nxt not in fwd_visited:
                    fwd_visited[nxt] = path + [nxt]
                    fwd_queue.append(nxt)
        for _ in range(len(bwd_queue)):
            cur = bwd_queue.pop(0)
            path = bwd_visited[cur]
            neighbours = []
            # Reverse: from `cur`, what nodes point to cur, and the
            # node cur points to.
            edge = graph.edges.get(cur)
            if edge is not None and edge[0] is not None:
                neighbours.append(edge[0])
            for other_id, e in graph.edges.items():
                if e[0] == cur and other_id != cur and other_id not in bwd_visited:
                    neighbours.append(other_id)
            for prev in neighbours:
                if prev in fwd_visited:
                    return fwd_visited[prev] + path
                if prev not in bwd_visited:
                    bwd_visited[prev] = [prev] + path
                    bwd_queue.append(prev)
    return None


# ---------- LaTeX emission ----------

def _prefix_symbol_latex(conn, exp):
    """LaTeX for an SI prefix symbol, e.g. '\\mu ' for micro."""
    row = conn.execute("SELECT symbol FROM si_prefix WHERE id = ?", (str(exp),)).fetchone()
    if not row:
        return ""
    try:
        symbol = json.loads(row["symbol"]).get("en-us", "")
    except (ValueError, TypeError):
        symbol = row["symbol"]
    return symbol or ""


def _unit_symbol(graph, unit_id):
    if unit_id in graph.unit_rows:
        return graph.unit_rows[unit_id].get("symbol") or unit_id
    if unit_id in graph.compound_rows:
        row = graph.compound_rows[unit_id]
        if row.get("symbol_overwrite"):
            return row["symbol_overwrite"]
        try:
            parts = json.loads(row["unit"])
        except (ValueError, TypeError):
            return unit_id

        def _part_symbol(uid):
            if uid in graph.unit_rows:
                return graph.unit_rows[uid].get("symbol") or uid
            part_row = graph.conn.execute(
                "SELECT symbol FROM unit WHERE id = ?", (uid,)).fetchone()
            return part_row["symbol"] if part_row else uid

        sym_map = {uid: _part_symbol(uid) for part in parts if (uid := part.get("unit")) is not None}
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


def _pretty_factor(x):
    if x == 0:
        return "0"
    if math.isinf(x):
        return "\\infty"
    ax = abs(x)
    sign = "-" if x < 0 else ""
    if ax >= 1e4 or ax < 1e-4:
        exp = int(math.floor(math.log10(ax)))
        mant = x / (10 ** exp)
        if 0.1 <= abs(mant) < 1:
            mant *= 10
            exp -= 1
        if abs(mant) >= 10 or abs(mant) >= 9.999995:
            mant /= 10
            exp += 1
        mant_str = f"{mant:.6f}".rstrip("0").rstrip(".")
        return f"{sign}{mant_str}\\times10^{{{exp}}}"
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return f"{x:.6g}"


def _factor_value_text(value, op="mul", is_reciprocal=False):
    """LaTeX for a numeric factor, with reciprocal/clean-fraction detection."""
    if is_reciprocal or op == "div":
        return _reciprocal_text(value)
    if value == 0:
        return "0"
    if value > 0 and value != 1:
        r = 1.0 / value
        r_int = round(r)
        if abs(r - r_int) <= 1e-9 * max(1.0, abs(r)) and r_int > 1:
            return _reciprocal_from_int(r_int)
    return _pretty_factor(value)


def _reciprocal_text(value):
    """Render 1/value as clean fraction when possible."""
    if value == 0:
        return "\\infty"
    r = 1.0 / value
    r_int = round(r)
    if abs(r - r_int) <= 1e-9 * max(1.0, abs(r)) and r_int > 1:
        return _reciprocal_from_int(r_int)
    return _pretty_factor(r)


def _reciprocal_from_int(r_int):
    if r_int < 10000:
        return f"1/{r_int}"
    log10 = math.log10(r_int)
    if abs(log10 - round(log10)) < 1e-9:
        return f"1/10^{{{int(round(log10))}}}"
    text = _pretty_factor(r_int)
    if "\\times" in text:
        return f"1/({text})"
    return f"1/{text}"


def _constant_symbol(graph, constant_id):
    """Return the LaTeX symbol (e.g. '\\pi') for a constant id."""
    row = graph.conn.execute(
        "SELECT symbol FROM constant WHERE id = ?", (constant_id,)).fetchone()
    return row["symbol"] if row else constant_id


def _temp_var_fn(graph):
    if getattr(graph, "quantity_id", None) == "temperature":
        return lambda sym: f"T_{{{sym}}}"
    return lambda sym: f"x\\,{sym}"


def _render_sci(x):
    """Exact scientific notation like `1\\times10^{-9}`.

    Used for magnitudes where float rounding must not leak digits — e.g.
    1/1e-15 computes to 999999999999999.9, which must print as
    `1\\times10^{15}` rather than the raw noisy digits.
    """
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    ax = abs(x)
    exp = int(math.floor(math.log10(ax)))
    mant = ax / (10.0 ** exp)
    if abs(mant - 1.0) <= 1e-6:
        return f"{sign}1\\times10^{{{exp}}}"
    if abs(mant - 10.0) <= 1e-6:
        return f"{sign}1\\times10^{{{exp + 1}}}"
    mant = round(mant, 6)
    if mant >= 9.9999995:
        mant = 1.0
        exp += 1
    if abs(mant - round(mant)) < 1e-9:
        mant_str = str(int(round(mant)))
    else:
        mant_str = f"{mant:.4f}".rstrip("0").rstrip(".")
    return f"{sign}{mant_str}\\times10^{{{exp}}}"


def _nice_num(x):
    """Render a coefficient readably: int, simple fraction, ≤2 dp, else .6g.

    Magnitudes that would otherwise render as 0 (e.g. 1e-9) or as noisy
    rounded floats (e.g. 999999999999999.88) fall back to scientific
    notation so the exponent is exact.
    """
    if x == 0:
        return "0"
    r = round(x)
    if r != 0 and abs(x - r) < 1e-9 and abs(r) < 1e15:
        return str(int(r))
    for d in range(2, 21):
        n = x * d
        nr = round(n)
        if abs(n - nr) < 1e-9 and abs(nr) <= 1000 and nr != 0:
            return f"{int(nr)}/{d}"
    ax = abs(x)
    if ax > 1e14 or ax < 1e-5:
        return _render_sci(x)
    r2 = round(x, 2)
    if abs(x - r2) < 1e-6:
        return f"{r2:.2f}".rstrip("0").rstrip(".")
    # `.6g` switches to "e"-notation outside roughly [1e-4, 1e6); use the
    # consistent \times 10^{...} style there too.
    if ax >= 1e6 or ax < 1e-4:
        return _render_sci(x)
    return f"{x:.6g}"


def _nice_offset(c):
    if abs(c - round(c)) < 1e-9:
        return True
    if abs(c) < 1e-6:
        return False
    r2 = round(c, 2)
    return abs(c - r2) < 1e-6


# ---------- equation rendering ----------

def _same_quantity(graph, a, b):
    """True iff both nodes live in the graph's primary quantity."""
    def qty_of(node):
        if node in graph.unit_rows:
            return graph.unit_rows[node].get("quantity_id") or graph.quantity_id
        if node in graph.compound_rows:
            return graph.compound_rows[node].get("quantity_id") or graph.quantity_id
        return None  # cross-quantity node
    return qty_of(a) is not None and qty_of(a) == qty_of(b)


def render_equation(graph, row_id, ref_id):
    """Build the conversion-cell LaTeX for the (row, ref) pair.

    Walks the reference graph to find a path from `row_id` to `ref_id`
    (forward) or from `ref_id` to `row_id` (inverse — inverted per-hop).
    Renders the simplest form that matches the baseline:
    - offset present → affine equation `T_ref = a·T_row + b`
    - single hop, single clean factor, no constant → direct equality
    - single hop with constant → chain `1 row = (c ÷ N) ref` (no final)
    - all-divisor chain → `1 row = 1/(...) ref`
    - multi-hop → chain `1 row = <chain> = N ref`
    """
    if row_id == ref_id:
        return None
    if not _same_quantity(graph, row_id, ref_id):
        return _render_numeric_equation(graph, row_id, ref_id)

    # Forward path: row → ... → ref
    fwd = path_between(graph, row_id, ref_id)
    if fwd is not None and len(fwd) >= 2:
        return _render_chain(graph, fwd, inverted=False)
    # Inverse path: ref → ... → row; we render as if walking the inverse
    inv = path_between(graph, ref_id, row_id)
    if inv is not None and len(inv) >= 2:
        return _render_chain(graph, inv, inverted=True)
    return _render_numeric_equation(graph, row_id, ref_id)


def _hop_factor(graph, edge, inverted):
    """Resolve an edge to its LINEAR chain coefficients (a, c).

    The LINEAR form is `x_ref = M * x_row + c`. For an edge that stores
    `x_ref = F * (x_row + offset) + shift` (shift = ±constant for
    add/sub), the implied linear coefficients are M = F and
    c = F*offset + shift; an inverted hop swaps to the exact inverse.
    Returns {"M": float, "c": float, "cid": str|None, "raw_factor": float,
             "is_rec": bool}.
    """
    ref_id, factor, is_rec, cid, cop, offset = edge
    if not math.isfinite(factor) or factor == 0:
        return None
    m = (1.0 / factor) if is_rec else factor
    shift = 0.0
    if cid:
        cval = graph._constant_value(cid)
        if not math.isfinite(cval):
            return None
        if cop == "div":
            if cval == 0:
                return None
            m /= cval
        elif cop == "mul":
            if cval == 0:
                return None
            m *= cval
        else:
            shift = cval if cop == "add" else -cval
    if inverted:
        return {
            "M": 1.0 / m,
            "c": -(m * offset + shift) / m,
            "cid": cid,
            "raw_factor": factor,
            "is_rec": is_rec,
        }
    return {
        "M": m,
        "c": m * offset + shift,
        "cid": cid,
        "raw_factor": factor,
        "is_rec": is_rec,
    }


def _render_chain(graph, path, inverted):
    """Render the chain-style equation for a path.

    `path` is `[row_id, ..., ref_id]` if not `inverted`, or the
    ref→row walk when `inverted` (the LHS unit is still `path[-1]`).
    """
    multi_hop = len(path) > 2
    if inverted:
        row_id = path[-1]
        ref_id = path[0]
    else:
        row_id = path[0]
        ref_id = path[-1]
    row_sym = _unit_latex(graph, row_id)
    ref_sym = _unit_latex(graph, ref_id)

    hops = []
    has_offset = False
    for i in range(len(path) - 1):
        cur = path[i]
        nxt = path[i + 1]
        edge = graph.edges.get(cur)
        hop_is_inverted = False
        if edge is None or edge[0] != nxt:
            edge = graph.edges.get(nxt)
            hop_is_inverted = True
        if edge is None:
            edge = graph._ensure_unit_loaded(cur) or graph._ensure_unit_loaded(nxt)
        if edge is None:
            return None
        eff_inverted = inverted ^ hop_is_inverted
        hop = _hop_factor(graph, edge, inverted=eff_inverted)
        if hop is None:
            return None
        hop["edge"] = edge
        hops.append(hop)
        if abs(hop["c"]) > 1e-12:
            has_offset = True

    if has_offset:
        return _render_affine_equation(graph, hops, row_sym, ref_sym)

    has_constant = any(h["cid"] for h in hops)
    if not has_constant:
        return _render_chain_numeric(graph, hops, multi_hop, row_sym, ref_sym, inverted)
    return _render_chain_with_constant(graph, hops, multi_hop, row_sym, ref_sym, inverted)


def _render_chain_numeric(graph, hops, multi_hop, row_sym, ref_sym, inverted):
    """Chain with no constant_id: pure numeric factor chain.

    Forward: `1 row = N1 × N2 × … [= total] ref`.
    Inverted (multi-hop): `1 row = 1/(N1 × N2 × …) ref` (the all-divisor form).
    """
    if len(hops) == 1:
        m = hops[0]["M"]
        if m == 1:
            return None
        return f"1\\,{row_sym} = {_factor_value_text(m, 'mul', False)}\\,{ref_sym}"
    m_total = 1.0
    for h in hops:
        m_total *= h["M"]
    if inverted and multi_hop:
        # All-divisor form for inverted multi-hop.
        # Each stored factor is used directly (the 1/ is on the whole product).
        den_parts = []
        for h in hops:
            n = h["raw_factor"] if not h["is_rec"] else 1.0 / h["raw_factor"]
            # The stored effective factor for this hop is `n`. Render it
            # as a clean value.
            text = _factor_value_text(n, "mul", False)
            den_parts.append(text)
        den = " \\times ".join(den_parts)
        if len(den_parts) > 1 and any("\\times" in t or "\\div" in t for t in den_parts):
            return f"1\\,{row_sym} = 1/({den})\\,{ref_sym}"
        return f"1\\,{row_sym} = 1/{den}\\,{ref_sym}"
    chain = " \\times ".join(_factor_value_text(h["M"], "mul", False) for h in hops)
    if multi_hop:
        return f"1\\,{row_sym} = {chain} = {_pretty_factor(m_total)}\\,{ref_sym}"
    return f"1\\,{row_sym} = {chain}\\,{ref_sym}"


def _const_multiplier_fragment(sym, M, cv):
    """Return a LaTeX chunk whose *value* equals `M`, for a constant hop.

    Supports the common forms k·π, π÷k, k÷π and 1/(π·k). A value like
    `1/(c·31557600)` (an inverted constant hop in a light-year chain) is
    detected in its reciprocal-of-product form rather than as a huge
    `k÷sym` — among all matching integer forms the one with the smallest
    k is chosen.
    """
    def isint(x):
        r = round(x)
        return 1 <= r < 10**18 and abs(x - r) <= 1e-9 * max(1.0, abs(x))

    if M == cv:
        return sym
    if 1.0 / cv == M:
        return f"1/{sym}"
    best_k = None
    best_text = None

    def offer(k, text):
        nonlocal best_k, best_text
        if not isint(k):
            return
        k_int = int(round(k))
        if best_k is None or k_int < best_k:
            best_k = k_int
            best_text = text(k_int)

    offer(M / cv, lambda k: sym if k == 1 else f"{k} \\times {sym}")
    offer(cv / M, lambda k: sym if k == 1 else f"{sym} \\div {k}")
    offer(M * cv, lambda k: sym if k == 1 else f"{k} \\div {sym}")
    offer(1.0 / (M * cv), lambda k: f"1/{sym}" if k == 1 else f"1/({sym} \\times {k})")
    if best_text is not None:
        return best_text
    return _factor_value_text(M, "mul", False)


def _render_chain_with_constant(graph, hops, multi_hop, row_sym, ref_sym, inverted):
    """Multi-hop chain containing at least one constant edge.

    Each hop is rendered as a fragment whose value equals the hop's
    *effective* multiplier `M` (which already accounts for any inversion),
    so the visible derivation always agrees with the final `= N`.
    """
    frags = []
    for h in hops:
        M = h["M"]
        if abs(M - 1.0) < 1e-12:
            continue
        if h["cid"]:
            cv = graph._constant_value(h["cid"])
            frags.append(_const_multiplier_fragment(_constant_symbol(graph, h["cid"]), M, cv))
        else:
            frags.append(_factor_value_text(M, "mul", False))
    if not frags:
        return f"1\\,{row_sym} = {ref_sym}"
    chain_str = " \\times ".join(frags)
    if not multi_hop:
        return f"1\\,{row_sym} = {chain_str}\\,{ref_sym}"
    m_total = 1.0
    for h in hops:
        m_total *= h["M"]
    return f"1\\,{row_sym} = {chain_str} = {_pretty_factor(m_total)}\\,{ref_sym}"


def _render_affine_equation(graph, hops, row_sym, ref_sym):
    """Equation form for offset chains.

    Each hop has LINEAR coefficients (M, c) such that
    x_next = M * x_row + c. Compose: a_new = a_2 * a_1, c_new = a_2 * c_1 + c_2.
    """
    a, b = 1.0, 0.0
    for h in hops:
        a = h["M"] * a
        b = h["M"] * b + h["c"]
    if not math.isfinite(a) or a == 0:
        return None

    var = _temp_var_fn(graph)
    lhs = var(ref_sym)
    body = var(row_sym)

    if abs(a - 1.0) < 1e-9:
        if abs(b) < 1e-12:
            return f"{lhs} = {body}"
        if b < 0:
            return f"{lhs} = {body} - {_nice_num(-b)}"
        return f"{lhs} = {body} + {_nice_num(b)}"

    # Suppress `b` only when the offset is genuinely negligible relative
    # to the linear term (|c| = |b/a| < 1e-9). A `max(1.0, abs(a))` scale
    # wrongly drops real offsets when a is small, e.g.
    # degree_fahrenheit -> si_12 where b ≈ 2.5e-10 and a ≈ 5.6e-13.
    if abs(b) < 1e-9 * abs(a):
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


def _render_numeric_equation(graph, row_id, ref_id):
    """Numeric fallback: compute the ratio and emit `1 row = N ref`."""
    if row_id == ref_id:
        return None
    row_val = graph.root_value(row_id)
    ref_val = graph.root_value(ref_id)
    if row_val is None or ref_val is None or ref_val == 0:
        return None
    ratio = row_val / ref_val
    if not math.isfinite(ratio) or ratio == 1:
        return None
    factor_str = _factor_value_text(ratio, op="mul", is_reciprocal=False)
    row_sym = _unit_latex(graph, row_id)
    ref_sym = _unit_latex(graph, ref_id)
    return f"1\\,{row_sym} = {factor_str}\\,{ref_sym}"


def precompute_latex_map(graph):
    """{row_id: {ref_id: latex_or_None}} for every reachable pair."""
    out = {}
    ids = graph.all_unit_ids() + graph.all_compound_ids()
    for row_id in ids:
        out[row_id] = {}
        for ref_id in ids:
            if row_id == ref_id:
                out[row_id][ref_id] = None
            else:
                out[row_id][ref_id] = render_equation(graph, row_id, ref_id)
    return out
