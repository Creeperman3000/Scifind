"""Reference-graph unit conversion."""

from __future__ import annotations

import json
import logging
import math
from collections import deque

from scifind_lib.units import (
    compound_unit_by_slug, compound_unit_slug,
    format_compound_unit_symbol,
    parse_compound_unit_parts, si_prefix_factor,
)

logger = logging.getLogger(__name__)


class UnitGraphError(Exception):
    pass


class UnitGraph:
    """Per-quantity unit reference graph; cross-quantity refs load lazily."""

    _EDGE_COLS = (
        "reference_unit_id", "factor_numerator", "factor_denominator",
        "constant_id", "constant_power", "constant_shift", "offset",
    )
    _UNIT_COLS = "id, symbol, system, is_base, " + ", ".join(_EDGE_COLS)
    # No stored id: compound dict keys are slugs computed via compound_unit_slug.
    _COMPOUND_COLS = "quantity_id, unit, symbol_overwrite, system, is_base"

    def __init__(self, conn, quantity_id):
        self.conn = conn
        self.quantity_id = quantity_id
        self.unit_rows: dict = {}
        self.compound_rows: dict = {}
        # Only unit rows have reference edges. Compound rows live in
        # compound_rows and are evaluated from their parts.
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
        d = dict(row)
        if in_unit:
            self.unit_rows[d["id"]] = d
            self.edges[d["id"]] = self.make_edge(
                d["reference_unit_id"], d["factor_numerator"], d["factor_denominator"],
                d["constant_id"],
                1.0 if d["constant_power"] is None else d["constant_power"],
                0.0 if d["constant_shift"] is None else d["constant_shift"],
                0.0 if d["offset"] is None else d["offset"],
            )
        else:
            uid = d.get("id") or compound_unit_slug(
                self.conn, d.get("quantity_id"), d.get("unit"))
            d["id"] = uid
            self.compound_rows[uid] = d

    @staticmethod
    def make_edge(reference_unit_id, factor_numerator=None,
                  factor_denominator=None,
                  constant_id=None, constant_power=1.0, constant_shift=0.0,
                  offset=0.0):
        """Reference edge tuple in canonical layout (use for synthetic nodes)."""
        return (reference_unit_id, factor_numerator, factor_denominator,
                constant_id, constant_power, constant_shift, offset)

    def _ensure_unit_loaded(self, unit_id):
        """Return the reference edge for a unit, or None for compounds/unknown."""
        if unit_id in self.edges:
            return self.edges[unit_id]
        if unit_id in self.compound_rows:
            return None
        row = self.conn.execute(
            f"SELECT {self._UNIT_COLS} FROM unit WHERE id = ?", (unit_id,)
        ).fetchone()
        if row is not None:
            self._install(row, in_unit=True)
            return self.edges[unit_id]
        row = compound_unit_by_slug(self.conn, unit_id)
        if row is None:
            return None
        self._install(row, in_unit=False)
        return None

    def all_unit_ids(self):
        return list(self.unit_rows)

    def all_compound_slugs(self):
        return list(self.compound_rows)

    def _constant_value(self, constant_id):
        if not constant_id:
            return 1.0
        row = self.conn.execute(
            "SELECT value FROM constant WHERE id = ? AND value IS NOT NULL",
            (constant_id,),
        ).fetchone()
        return float(row["value"]) if row else float("nan")

    def _edge_coeffs(self, factor_numerator, factor_denominator,
                     constant_id, constant_power=1.0, constant_shift=0.0):
        """(M, shift) with `x_ref = M * (x_row + offset) + shift`, or None."""
        num = 1.0 if factor_numerator is None else factor_numerator
        den = 1.0 if factor_denominator is None else factor_denominator
        if not math.isfinite(num) or not math.isfinite(den) or num == 0 or den == 0:
            return None
        m, shift = num / den, 0.0
        if not constant_id:
            return m, shift
        c = self._constant_value(constant_id)
        if not math.isfinite(c):
            return None
        if constant_power:
            if c == 0 and constant_power < 0:
                return None
            scaled = c ** constant_power
            if not math.isfinite(scaled):
                return None
            m *= scaled
            if m == 0:
                return None
        if constant_shift:
            shift += constant_shift * c
        return m, shift

    def _quantity_of(self, unit_id):
        row = self.unit_rows.get(unit_id) or self.compound_rows.get(unit_id)
        return (row.get("quantity_id") or self.quantity_id) if row else None

    def path_to_root(self, unit_id):
        """[unit_id, ..., root] or None on cycle/orphan; compounds are terminals."""
        seen, path = set(), []
        while True:
            if unit_id in seen:
                return None
            seen.add(unit_id)
            path.append(unit_id)
            if unit_id in self.compound_rows:
                return path
            edge = self._ensure_unit_loaded(unit_id)
            if edge is None:
                # Unknown unit — unless the lookup just lazily installed a
                # cross-quantity compound, which is a valid terminal.
                return path if unit_id in self.compound_rows else None
            if edge[0] is None:
                return path
            unit_id = edge[0]

    def root_value(self, unit_id):
        """Ratio of `1 unit_id` in the root unit, multiplicative only; None if unreachable."""
        aff = _affine_to_root(self, unit_id)
        return aff[0] if aff else None

    def compound_parts_value(self, compound_slug):
        """Root value of a compound in raw unit-parts (offsets never apply)."""
        row = self.compound_rows.get(compound_slug)
        parts = parse_compound_unit_parts(row["unit"]) if row else None
        if not parts:
            return None
        result = 1.0
        for uid, exp, prefix in parts:
            v = self.root_value(uid)
            if v is None or not math.isfinite(v):
                return None
            if prefix is not None:
                try:
                    v *= float(si_prefix_factor(prefix))
                except (TypeError, ValueError):
                    return None
            result *= v ** exp
        return result


def validate_graph(conn):
    for (qid,) in conn.execute("SELECT DISTINCT quantity_id FROM unit").fetchall():
        graph = UnitGraph(conn, qid)
        for uid in list(graph.unit_rows):
            if graph.path_to_root(uid) is None:
                raise UnitGraphError(
                    f"quantity '{qid}' unit '{uid}' has no path to root "
                    f"(cycle or orphan — graph integrity violated)"
                )


def _affine_to_root(graph, unit_id):
    """Return (m, b) so that x_root = m * x_unit + b."""
    path = graph.path_to_root(unit_id)
    if path is None:
        return None
    m, b = 1.0, 0.0
    for cur in path[:-1]:
        edge = graph._ensure_unit_loaded(cur)
        if edge is None:
            return None
        _ref, fnum, fden, cid, cpower, cshift, offset = edge
        coeffs = graph._edge_coeffs(fnum, fden, cid, cpower, cshift)
        if coeffs is None:
            return None
        m_edge, shift = coeffs
        if not math.isfinite(m_edge) or m_edge == 0:
            return None
        # x_ref = m_edge * (x_cur + offset) + shift, with x_cur = m * x + b.
        m, b = m_edge * m, m_edge * b + m_edge * offset + shift
    if path[-1] in graph.compound_rows:
        compound_root = graph.compound_parts_value(path[-1])
        if not compound_root or not math.isfinite(compound_root):
            return None
        m *= compound_root
    return m, b


def convert_value(value, from_id, to_id, graph):
    """Convert `value` from `from_id` to `to_id`; None if a side is unreachable."""
    if from_id == to_id:
        return value
    from_aff = _affine_to_root(graph, from_id)
    to_aff = _affine_to_root(graph, to_id)
    if from_aff is None or to_aff is None or to_aff[0] == 0:
        return None
    return (from_aff[0] * value + from_aff[1] - to_aff[1]) / to_aff[0]


def _graph_neighbours(graph, node):
    """Direct neighbours of `node` in either edge direction."""
    out = []
    edge = graph.edges.get(node)
    if edge is not None and edge[0] is not None:
        out.append(edge[0])
    return out + [o for o, e in graph.edges.items() if e[0] == node and o != node]


def path_between(graph, from_id, to_id):
    """[from_id, ..., to_id] or None. BFS over both edge directions."""
    if from_id == to_id:
        return [from_id]
    prev = {from_id: None}
    queue = deque([from_id])
    while queue:
        cur = queue.popleft()
        for nxt in _graph_neighbours(graph, cur):
            if nxt not in prev:
                prev[nxt] = cur
                if nxt == to_id:
                    path, node = [to_id], to_id
                    while prev[node] is not None:
                        node = prev[node]
                        path.append(node)
                    return path[::-1]
                queue.append(nxt)
    return None


def _prefix_symbol_latex(conn, exp):
    row = conn.execute("SELECT symbol FROM si_prefix WHERE id = ?", (str(exp),)).fetchone()
    if not row:
        return ""
    try:
        return json.loads(row["symbol"]).get("en-us", "") or ""
    except (ValueError, TypeError):
        return row["symbol"] or ""


def _part_symbol(graph, uid):
    if uid in graph.unit_rows:
        return graph.unit_rows[uid].get("symbol") or uid
    part_row = graph.conn.execute(
        "SELECT symbol FROM unit WHERE id = ?", (uid,)).fetchone()
    return part_row["symbol"] if part_row else uid


def _unit_symbol(graph, unit_id):
    if unit_id in graph.unit_rows:
        return graph.unit_rows[unit_id].get("symbol") or unit_id
    if unit_id not in graph.compound_rows:
        return unit_id
    row = graph.compound_rows[unit_id]
    if row.get("symbol_overwrite"):
        return row["symbol_overwrite"]
    parts = parse_compound_unit_parts(row["unit"])
    if not parts:
        return unit_id
    sym_map = {uid: _part_symbol(graph, uid) for uid, _e, _p in parts}
    return format_compound_unit_symbol(
        row["unit"],
        unit_symbol=lambda uid: sym_map.get(uid, uid),
        prefix_symbol=lambda exp: _prefix_symbol_latex(graph.conn, int(exp)),
    )


def _unit_latex(graph, unit_id):
    sym = _unit_symbol(graph, unit_id)
    if not sym or "\\mathrm{" in sym:
        return sym
    return f"\\mathrm{{{sym}}}"


def _pretty_factor(x):
    if x == 0:
        return "0"
    if math.isinf(x):
        return "\\infty"
    ax = abs(x)
    if ax >= 1e4 or ax < 1e-4:
        return _render_sci(x, decimals=6)
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return f"{x:.6g}"


def _reciprocal_int(value):
    """Integer k > 1 with value ≈ 1/k, else None."""
    if value == 0:
        return None
    r = 1.0 / value
    r_int = round(r)
    if r_int > 1 and abs(r - r_int) <= 1e-9 * max(1.0, abs(r)):
        return int(r_int)
    return None


def _factor_value_text(value):
    if value == 0:
        return "0"
    if value > 0 and value != 1:
        k = _reciprocal_int(value)
        if k is not None:
            return _reciprocal_from_int(k)
    return _pretty_factor(value)


def _reciprocal_from_int(r_int):
    if r_int < 10000:
        return f"1/{r_int}"
    log10 = math.log10(r_int)
    if abs(log10 - round(log10)) < 1e-9:
        return f"1/10^{{{int(round(log10))}}}"
    text = _pretty_factor(r_int)
    return f"1/({text})" if "\\times" in text else f"1/{text}"


def _constant_symbol(graph, constant_id):
    row = graph.conn.execute(
        "SELECT symbol FROM constant WHERE id = ?", (constant_id,)).fetchone()
    return row["symbol"] if row else constant_id


def _render_sci(x, *, decimals=4):
    """Exact scientific notation like `10^{-9}`."""
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    exp = int(math.floor(math.log10(abs(x))))
    mant = abs(x) / (10.0 ** exp)
    if abs(mant - 1.0) <= 1e-6:
        return f"{sign}10^{{{exp}}}"
    if abs(mant - 10.0) <= 1e-6:
        return f"{sign}10^{{{exp + 1}}}"
    mant = round(mant, 6)
    if mant >= 9.9999995:
        mant = 1.0
        exp += 1
    if abs(mant - round(mant)) < 1e-9:
        mant_str = str(int(round(mant)))
    else:
        mant_str = f"{mant:.{decimals}f}".rstrip("0").rstrip(".")
    return f"{sign}{mant_str}\\times10^{{{exp}}}"


def _nice_num(x):
    """Render a coefficient readably: int, fraction, ≤2 dp, else .6g."""
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
    if ax >= 1e6 or ax < 1e-4:
        return _render_sci(x)
    return f"{x:.6g}"


def render_equation(graph, row_id, ref_id):
    """LaTeX for the (row, ref) conversion cell."""
    if row_id == ref_id:
        return None
    qa, qb = graph._quantity_of(row_id), graph._quantity_of(ref_id)
    if qa is None or qa != qb:
        return _render_numeric_equation(graph, row_id, ref_id)
    path = path_between(graph, row_id, ref_id)
    if path is not None:
        return _render_chain(graph, path)
    return _render_numeric_equation(graph, row_id, ref_id)


def _hop_factor(graph, edge, inverted):
    """Per-hop (M, c) with x_ref = M * x_row + c; inverted hops use the exact inverse."""
    coeffs = graph._edge_coeffs(edge[1], edge[2], edge[3], edge[4], edge[5])
    if coeffs is None:
        return None
    m, shift = coeffs
    offset = edge[6]
    if inverted:
        m, c = 1.0 / m, -(m * offset + shift) / m
    else:
        m, c = m, m * offset + shift
    return {"M": m, "c": c, "cid": edge[3],
            "raw_num": edge[1], "raw_den": edge[2]}


def _render_chain(graph, path):
    """Chain LaTeX for a row→ref path."""
    row_sym = _unit_latex(graph, path[0])
    ref_sym = _unit_latex(graph, path[-1])
    hops = []
    has_offset = False
    for i in range(len(path) - 1):
        cur, nxt = path[i], path[i + 1]
        edge = graph.edges.get(cur)
        hop_inverted = False
        if edge is None or edge[0] != nxt:
            edge = graph.edges.get(nxt)
            hop_inverted = True
        if edge is None:
            edge = graph._ensure_unit_loaded(cur) or graph._ensure_unit_loaded(nxt)
        if edge is None:
            return None
        hop = _hop_factor(graph, edge, hop_inverted)
        if hop is None:
            return None
        hops.append(hop)
        has_offset |= abs(hop["c"]) > 1e-12
    if has_offset:
        return _render_affine_equation(hops, row_sym, ref_sym)
    if any(h["cid"] for h in hops):
        return _render_chain_with_constant(graph, hops, row_sym, ref_sym)
    return _render_chain_numeric(hops, row_sym, ref_sym)


def _int_text(x):
    """Compact text for an int-like number, else None."""
    try:
        r = round(float(x))
    except (TypeError, ValueError):
        return None
    if abs(float(x) - r) <= 1e-9 * max(1.0, abs(float(x))) and abs(r) < 1e15:
        return str(int(r))
    return None


def _stored_fraction_text(raw_num, raw_den):
    """Literal `num/den` text for a stored factor (NULL = 1); None when trivial."""
    n = 1.0 if raw_num is None else raw_num
    d = 1.0 if raw_den is None else raw_den
    if n == 1.0 and d == 1.0:
        return None
    n_text, d_text = _int_text(n), _int_text(d)
    if n_text is None or d_text is None:
        return None
    return n_text if d_text == "1" else f"{n_text}/{d_text}"


def _hop_display_text(hop):
    """Per-hop text preferring the stored fraction (e.g. 5/9, 101325/760)."""
    return _stored_fraction_text(hop.get("raw_num"), hop.get("raw_den")) \
        or _factor_value_text(hop["M"])


def _render_chain_numeric(hops, row_sym, ref_sym):
    """Pure numeric factor chain."""
    if len(hops) == 1:
        m = hops[0]["M"]
        if m == 1:
            # Distinct ids with identical value: show the identity, not a dash.
            return f"1\\,{row_sym} = 1\\,{ref_sym}"
        return f"1\\,{row_sym} = {_hop_display_text(hops[0])}\\,{ref_sym}"
    chain = " \\times ".join(_hop_display_text(h) for h in hops)
    m_total = 1.0
    for h in hops:
        m_total *= h["M"]
    return f"1\\,{row_sym} = {chain} = {_pretty_factor(m_total)}\\,{ref_sym}"


def _const_multiplier_fragment(sym, M, cv):
    """LaTeX chunk whose value equals `M` for a constant hop."""
    def isint(x):
        r = round(x)
        return 1 <= r < 10**18 and abs(x - r) <= 1e-9 * max(1.0, abs(x))

    if M == cv:
        return sym
    if 1.0 / cv == M:
        return f"1/{sym}"
    best = None
    candidates = (
        (M / cv, lambda k: sym if k == 1 else f"{k} \\times {sym}"),
        (cv / M, lambda k: sym if k == 1 else f"{sym} \\div {k}"),
        (M * cv, lambda k: sym if k == 1 else f"{k} \\div {sym}"),
        (1.0 / (M * cv), lambda k: f"1/{sym}" if k == 1 else f"1/({sym} \\times {k})"),
    )
    for k, text in candidates:
        k_int = int(round(k))
        if isint(k) and (best is None or k_int < best[0]):
            best = (k_int, text(k_int))
    return best[1] if best else _factor_value_text(M)


def _render_chain_with_constant(graph, hops, row_sym, ref_sym):
    """Chain with ≥1 constant edge; each fragment equals the hop's effective M."""
    frags = []
    for h in hops:
        M = h["M"]
        if abs(M - 1.0) < 1e-12:
            continue
        if h["cid"]:
            cv = graph._constant_value(h["cid"])
            frags.append(_const_multiplier_fragment(_constant_symbol(graph, h["cid"]), M, cv))
        else:
            frags.append(_factor_value_text(M))
    if not frags:
        return f"1\\,{row_sym} = {ref_sym}"
    chain_str = " \\times ".join(frags)
    if len(hops) == 1:
        return f"1\\,{row_sym} = {chain_str}\\,{ref_sym}"
    m_total = 1.0
    for h in hops:
        m_total *= h["M"]
    return f"1\\,{row_sym} = {chain_str} = {_pretty_factor(m_total)}\\,{ref_sym}"


def _render_affine_equation(hops, row_sym, ref_sym):
    """Affine form for offset chains; composes each hop's (M, c) in path order."""
    a, b = 1.0, 0.0
    for h in hops:
        a, b = h["M"] * a, h["M"] * b + h["c"]
    if not math.isfinite(a) or a == 0:
        return None
    lhs, body = f"x\\,{ref_sym}", f"x\\,{row_sym}"
    if abs(a - 1.0) < 1e-9:
        if abs(b) < 1e-12:
            return f"{lhs} = {body}"
        return f"{lhs} = {body} - {_nice_num(-b)}" if b < 0 else f"{lhs} = {body} + {_nice_num(b)}"
    # Drop `b` only when negligible relative to the linear term (|b/a| < 1e-9);
    # a `max(1.0, abs(a))` scale would drop real offsets when a is tiny.
    if abs(b) < 1e-9 * abs(a):
        return f"{lhs} = {_nice_num(a)} \\times {body}"
    c = -b / a
    if abs(c - round(c)) < 1e-9 or (abs(c) >= 1e-6 and abs(c - round(c, 2)) < 1e-6):
        if c < 0:
            return f"{lhs} = ({body} + {_nice_num(-c)}) \\times {_nice_num(a)}"
        return f"{lhs} = ({body} - {_nice_num(c)}) \\times {_nice_num(a)}"
    out = f"{lhs} = {_nice_num(a)} \\times {body}"
    if abs(b) >= 1e-12:
        out += f" - {_nice_num(-b)}" if b < 0 else f" + {_nice_num(b)}"
    return out


def _render_numeric_equation(graph, row_id, ref_id):
    if row_id == ref_id:
        return None
    row_val = graph.root_value(row_id)
    ref_val = graph.root_value(ref_id)
    if row_val is None or ref_val is None or ref_val == 0:
        return None
    ratio = row_val / ref_val
    if not math.isfinite(ratio):
        return None
    row_sym, ref_sym = _unit_latex(graph, row_id), _unit_latex(graph, ref_id)
    if ratio == 1:
        # Distinct ids with identical value: show the identity, not a dash.
        return f"1\\,{row_sym} = 1\\,{ref_sym}"
    return f"1\\,{row_sym} = {_factor_value_text(ratio)}\\,{ref_sym}"


def precompute_latex_map(graph):
    ids = graph.all_unit_ids() + graph.all_compound_slugs()
    return {r: {c: None if r == c else render_equation(graph, r, c) for c in ids}
            for r in ids}
