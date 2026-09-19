"""Reference-graph unit conversion."""

from __future__ import annotations

import math
from collections import deque

from scifind_lib.i18n import localise, wrap_symbol_in_latex
from scifind_lib.units import (
    compound_unit_by_slug, compound_unit_slug,
    format_compound_unit_symbol,
    parse_compound_unit_parts, si_prefix_factor,
)
from scifind_lib.util import (
    SCI_LARGE_THRESHOLD, SCI_SMALL_THRESHOLD,
    as_int as _as_int,
    render_sci_latex, split_sci_mantissa,
)


class UnitGraphError(Exception):
    pass


def _nv(value, default):
    return default if value is None else value


class UnitGraph:
    """Per-quantity unit reference graph; cross-quantity refs load lazily."""

    _EDGE_COLS = (
        "reference_unit_id", "factor_numerator", "factor_denominator",
        "constant_id", "constant_power", "constant_shift", "offset",
    )
    _UNIT_COLS = "id, symbol, system, is_base, " + ", ".join(_EDGE_COLS)
    # No stored id: compound dict keys are canonical ids from compound_unit_slug.
    _COMPOUND_COLS = "quantity_id, unit, symbol_overwrite, system, is_base"

    def __init__(self, conn, quantity_id, locale="en-us"):
        self.conn = conn
        self.quantity_id = quantity_id
        self.locale = locale
        self.unit_rows: dict = {}
        self.compound_rows: dict = {}
        # Only unit rows have reference edges. Compound rows live in
        # compound_rows and are evaluated from their parts.
        self.edges: dict = {}
        self._const_cache: dict = {}
        self._rev_cache: dict | None = None
        for in_unit, table, cols in (
            (True, "unit", self._UNIT_COLS),
            (False, "compound_unit", self._COMPOUND_COLS),
        ):
            for row in conn.execute(
                f"SELECT {cols} FROM {table} WHERE quantity_id = ?",
                (quantity_id,),
            ).fetchall():
                self._install(row, in_unit=in_unit)

    def _install(self, row, *, in_unit):
        row_dict = dict(row)
        self._rev_cache = None
        if in_unit:
            self.unit_rows[row_dict["id"]] = row_dict
            self.edges[row_dict["id"]] = self.make_edge(
                row_dict["reference_unit_id"], row_dict["factor_numerator"], row_dict["factor_denominator"],
                row_dict["constant_id"],
                _nv(row_dict["constant_power"], 1.0),
                _nv(row_dict["constant_shift"], 0.0),
                _nv(row_dict["offset"], 0.0),
            )
        else:
            uid = row_dict.get("id") or compound_unit_slug(
                row_dict.get("quantity_id"), row_dict.get("unit"))
            row_dict["id"] = uid
            self.compound_rows[uid] = row_dict

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
        if row is not None:
            self._install(row, in_unit=False)
        return None

    def _constant_value(self, constant_id):
        if not constant_id:
            return 1.0
        if constant_id in self._const_cache:
            return self._const_cache[constant_id]
        row = self.conn.execute(
            "SELECT value FROM constant WHERE id = ? AND value IS NOT NULL",
            (constant_id,),
        ).fetchone()
        value = float(row["value"]) if row else float("nan")
        self._const_cache[constant_id] = value
        return value

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
            try:
                scaled = c ** constant_power
            except (ValueError, ZeroDivisionError, OverflowError, TypeError):
                return None
            if not isinstance(scaled, (int, float)) or not math.isfinite(scaled):
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
        product = 1.0
        for uid, exp, prefix in parts:
            v = self.root_value(uid)
            if v is None or not math.isfinite(v):
                return None
            if prefix is not None:
                try:
                    v *= float(si_prefix_factor(prefix))
                except (TypeError, ValueError):
                    return None
            product *= v ** exp
        return product


def validate_graph(conn):
    for (qid,) in conn.execute("SELECT DISTINCT quantity_id FROM unit").fetchall():
        graph = UnitGraph(conn, qid)
        for uid in list(graph.unit_rows):
            if graph.path_to_root(uid) is None:
                raise UnitGraphError(
                    f"quantity '{qid}' unit '{uid}' has no path to root "
                    f"(cycle or orphan — graph integrity violated)"
                )


def _edge_affine(graph, edge):
    """Per-edge (M, c) with `x_ref = M * x_row + c`; None when degenerate."""
    coeffs = graph._edge_coeffs(edge[1], edge[2], edge[3], edge[4], edge[5])
    if coeffs is None:
        return None
    m, shift = coeffs
    return m, m * (edge[6] or 0.0) + shift


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
        aff = _edge_affine(graph, edge)
        if aff is None:
            return None
        m_edge, c_edge = aff
        if not math.isfinite(m_edge) or m_edge == 0:
            return None
        # x_ref = m_edge * x_cur + c_edge, with x_cur = m * x + b.
        m, b = m_edge * m, m_edge * b + c_edge
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


def path_between(graph, from_id, to_id):
    """[from_id, ..., to_id] or None. BFS over both edge directions."""
    if from_id == to_id:
        return [from_id]
    rev = graph._rev_cache
    if rev is None or getattr(graph, "_rev_cache_size", -1) != len(graph.edges):
        rev = {}
        for owner, edge in graph.edges.items():
            if edge[0] is not None and owner != edge[0]:
                rev.setdefault(edge[0], []).append(owner)
        graph._rev_cache = rev
        graph._rev_cache_size = len(graph.edges)
    prev = {from_id: None}
    queue = deque([from_id])
    while queue:
        cur = queue.popleft()
        edge = graph.edges.get(cur)
        nxts = list(rev.get(cur, []))
        if edge is not None and edge[0] is not None:
            nxts.append(edge[0])
        for nxt in nxts:
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


def _unit_symbol(graph, unit_id):
    if unit_id in graph.unit_rows:
        return graph.unit_rows[unit_id].get("symbol") or unit_id
    row = graph.compound_rows.get(unit_id)
    if row is None:
        return unit_id
    if row.get("symbol_overwrite"):
        return row["symbol_overwrite"]
    parts = parse_compound_unit_parts(row["unit"])
    if not parts:
        return unit_id
    cache: dict = {}

    def sym(uid):
        if uid not in cache:
            if uid in graph.unit_rows:
                cache[uid] = graph.unit_rows[uid].get("symbol") or uid
            else:
                hit = graph.conn.execute(
                    "SELECT symbol FROM unit WHERE id = ?", (uid,)).fetchone()
                cache[uid] = hit["symbol"] if hit else uid
        return cache[uid]

    def prefix_sym(exp):
        hit = graph.conn.execute(
            "SELECT symbol FROM si_prefix WHERE id = ?", (str(int(exp)),)).fetchone()
        return localise(hit["symbol"], graph.locale) if hit else ""

    return format_compound_unit_symbol(
        row["unit"], unit_symbol=sym, prefix_symbol=prefix_sym,
    )


def _render_sci(x, *, decimals=4):
    """Exact scientific notation like `10^{-9}`."""
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    mant, exp = split_sci_mantissa(abs(x))
    if abs(mant - 1.0) <= 1e-6:
        return f"{sign}10^{{{exp}}}"
    if abs(mant - 10.0) <= 1e-6:
        return f"{sign}10^{{{exp + 1}}}"
    mant = round(mant, 6)
    if mant >= 9.9999995:
        mant, exp = 1.0, exp + 1
    mant_str = str(int(round(mant))) if abs(mant - round(mant)) < 1e-9 \
        else f"{mant:.{decimals}f}".rstrip("0").rstrip(".")
    return render_sci_latex(sign, mant_str, exp)


def _pretty_factor(x):
    if x == 0:
        return "0"
    if math.isinf(x):
        return "\\infty"
    ax = abs(x)
    if ax >= SCI_LARGE_THRESHOLD or ax < SCI_SMALL_THRESHOLD:
        return _render_sci(x, decimals=6)
    if (iv := _as_int(x)) is not None:
        return str(iv)
    return f"{x:.6g}"


def _factor_value_text(value):
    if value == 0:
        return "0"
    if value > 0 and value != 1:
        r = _as_int(1.0 / value)
        if r is not None and r > 1:
            k = r
            if k < 10000:
                return f"1\\div {k}"
            log10 = math.log10(k)
            if abs(log10 - round(log10)) < 1e-9:
                return f"1\\div 10^{{{int(round(log10))}}}"
    return _pretty_factor(value)


def _nice_num(x):
    """Render a coefficient readably: int, fraction, ≤2 dp, else .6g."""
    if x == 0:
        return "0"
    if (iv := _as_int(x)) is not None and iv != 0:
        return str(iv)
    for d in range(2, 21):
        n = x * d
        nr = round(n)
        if abs(n - nr) < 1e-9 and abs(nr) <= 1000 and nr != 0:
            return f"{int(nr)}\\div {d}"
    ax = abs(x)
    if ax > 1e14 or ax < 1e-5:
        return _render_sci(x)
    r2 = round(x, 2)
    if abs(x - r2) < 1e-6:
        return f"{r2:.2f}".rstrip("0").rstrip(".")
    if ax >= SCI_LARGE_THRESHOLD or ax < SCI_SMALL_THRESHOLD:
        return _render_sci(x)
    return f"{x:.6g}"


def render_equation(graph, row_id, ref_id):
    """LaTeX for the (row, ref) conversion cell."""
    if row_id == ref_id:
        return None
    row_qid, ref_qid = graph._quantity_of(row_id), graph._quantity_of(ref_id)
    if row_qid is None or row_qid != ref_qid:
        return _render_numeric_equation(graph, row_id, ref_id)
    path = path_between(graph, row_id, ref_id)
    if path is not None:
        return _render_chain(graph, path)
    return _render_numeric_equation(graph, row_id, ref_id)


def _hop_factor(graph, edge, inverted):
    """Per-hop (M, c) with x_ref = M * x_row + c; inverted hops use the exact inverse."""
    aff = _edge_affine(graph, edge)
    if aff is None:
        return None
    m, c = aff
    if inverted:
        m, c = 1.0 / m, -c / m
    power = edge[4]
    if power is None:
        power = 1.0
    if inverted:
        power = -power
    return {"M": m, "c": c, "cid": edge[3], "p": power if edge[3] else 0.0,
            "raw_num": edge[2] if inverted else edge[1],
            "raw_den": edge[1] if inverted else edge[2],
            "off": edge[6] or 0.0}


def _render_chain(graph, path):
    """Chain LaTeX for a row→ref path."""
    row_sym = wrap_symbol_in_latex(_unit_symbol(graph, path[0]))
    ref_sym = wrap_symbol_in_latex(_unit_symbol(graph, path[-1]))
    hops = []
    for i in range(len(path) - 1):
        cur, nxt = path[i], path[i + 1]
        edge = graph.edges.get(cur)
        hop_inverted = False
        if edge is None or edge[0] != nxt:
            edge, hop_inverted = graph.edges.get(nxt), True
        if edge is None:
            edge = graph._ensure_unit_loaded(cur) or graph._ensure_unit_loaded(nxt)
        if edge is None:
            return None
        hop = _hop_factor(graph, edge, hop_inverted)
        if hop is None:
            return None
        hops.append(hop)
    if any(abs(h["c"]) > 1e-12 for h in hops):
        return _render_affine_equation(hops, row_sym, ref_sym, graph)
    if any(h["cid"] for h in hops):
        return _render_chain_with_constant(graph, hops, row_sym, ref_sym)
    return _render_chain_numeric(hops, row_sym, ref_sym)


def _hop_display_text(hop):
    """Per-hop text preferring the stored fraction (e.g. 5/9); large fractions use decimals."""
    n = 1.0 if hop.get("raw_num") is None else hop["raw_num"]
    d = 1.0 if hop.get("raw_den") is None else hop["raw_den"]
    if not (n == 1.0 and d == 1.0) and abs(n) < 1e6 and abs(d) < 1e6:
        n_int, d_int = _as_int(n), _as_int(d)
        if n_int is not None and d_int is not None and d_int != 0:
            if d_int == 1:
                return str(n_int)
            g = math.gcd(abs(n_int), abs(d_int))
            sn, sd = n_int // g, d_int // g
            if max(abs(sn), abs(sd)) < 10000:
                return f"{sn}\\div {sd}"
    return _factor_value_text(hop["M"])


def _join_chain(frags):
    """Join hop frags; wrap ÷-frags in parens when order could confuse."""
    if len(frags) <= 1:
        return frags[0] if frags else ""
    return " \\times ".join(f"({t})" if "\\div" in t and not t.startswith("(") else t for t in frags)


def _needs_power_parens(frag):
    """Whether `frag^{n}` needs parens: any operator, space, or existing
    superscript inside makes a bare `frag^{n}` misparse."""
    return frag.startswith("-") or any(
        tok in frag for tok in ("\\div", "\\times", "\\cdot", "^{", " ", "/"))


def _collapse_repeats(frags):
    """Collapse consecutive identical frags into powers (1÷60 × 1÷60 → (1÷60)²)."""
    out = []
    i = 0
    while i < len(frags):
        j = i
        while j < len(frags) and frags[j] == frags[i]:
            j += 1
        n = j - i
        if n >= 2:
            t = frags[i]
            out.append(f"({t})^{{{n}}}" if _needs_power_parens(t) else f"{t}^{{{n}}}")
        else:
            out.append(frags[i])
        i = j
    return out


def _cancelled_single(hops):
    """Single fraction when int-like stored numerators/denominators cancel across hops."""
    num, den, cancelled = 1, 1, 1
    for h in hops:
        n = 1.0 if h.get("raw_num") is None else h["raw_num"]
        d = 1.0 if h.get("raw_den") is None else h["raw_den"]
        n_int, d_int = _as_int(n), _as_int(d)
        if n_int is None or d_int is None or d_int == 0:
            return None, False
        g1 = math.gcd(abs(n_int), abs(d_int))
        num *= abs(n_int) // g1
        den *= abs(d_int) // g1
        cancelled *= g1
        if num > 10**12 or den > 10**12:
            return None, False
    g = math.gcd(num, den)
    num //= g
    den //= g
    if cancelled <= 1 or max(num, den) >= 10000:
        return None, False
    return (str(num) if den == 1 else f"{num}\\div {den}"), True


def _render_chain_numeric(hops, row_sym, ref_sym):
    """Pure numeric factor chain (unity hops omitted)."""
    hops = [h for h in hops if abs(h["M"] - 1.0) >= 1e-12]
    if not hops:
        # Distinct ids with identical value: show the identity, not a dash.
        return f"1\\,{row_sym} = 1\\,{ref_sym}"
    if len(hops) == 1:
        return f"1\\,{row_sym} = {_hop_display_text(hops[0])}\\,{ref_sym}"
    if (single := _cancelled_single(hops))[1]:
        return f"1\\,{row_sym} = {single[0]}\\,{ref_sym}"
    frags = _collapse_repeats([_hop_display_text(h) for h in hops])
    chain = _join_chain(frags)
    return f"1\\,{row_sym} = {chain} = {_factor_value_text(math.prod(h['M'] for h in hops))}\\,{ref_sym}"


def _const_multiplier_fragment(sym, M, cv):
    """LaTeX chunk whose value equals `M` for a constant hop."""
    def isint(x):
        r = round(x)
        return 1 <= r < 10**18 and abs(x - r) <= 1e-9 * max(1.0, abs(x))

    if M == cv:
        return sym
    if 1.0 / cv == M:
        return f"1\\div {sym}"
    best = None
    for k, one, many in (
        (M / cv, "{sym}", "{k} \\times {sym}"),
        (cv / M, "{sym}", "{sym} \\div {k}"),
        (M * cv, "{sym}", "{k} \\div {sym}"),
        (1.0 / (M * cv), "1\\div {sym}", "1\\div ({sym} \\times {k})"),
    ):
        k_int = int(round(k))
        if isint(k) and (best is None or k_int < best[0]):
            best = (k_int, (one if k_int == 1 else many).format(sym=sym, k=k_int))
    return best[1] if best else _factor_value_text(M)


def _numeric_hop_text(hop):
    """Stored-fraction text for a hop whose constant cancels out (None when unity)."""
    n = 1.0 if hop.get("raw_num") is None else hop["raw_num"]
    d = 1.0 if hop.get("raw_den") is None else hop["raw_den"]
    if n == 1.0 and d == 1.0:
        return None
    if abs(n) < 1e6 and abs(d) < 1e6:
        n_int, d_int = _as_int(n), _as_int(d)
        if n_int is not None and d_int is not None:
            return str(n_int) if d_int == 1 else f"{n_int}\\div {d_int}"
    return _factor_value_text(n / d)


def _render_chain_with_constant(graph, hops, row_sym, ref_sym):
    """Chain with ≥1 constant edge; each fragment equals the hop's effective M."""
    net: dict = {}
    for h in hops:
        if h.get("cid") and h.get("p"):
            net[h["cid"]] = net.get(h["cid"], 0.0) + h["p"]
    cancelled = {cid for cid, e in net.items() if e == 0.0}
    frags = []
    for h in hops:
        M = h["M"]
        if abs(M - 1.0) < 1e-12:
            continue
        if h["cid"] and h["cid"] in cancelled:
            if (frag := _numeric_hop_text(h)) is not None:
                frags.append(frag)
            continue
        if h["cid"]:
            hit = graph.conn.execute(
                "SELECT symbol FROM constant WHERE id = ?", (h["cid"],)).fetchone()
            sym = hit["symbol"] if hit else h["cid"]
            frags.append(_const_multiplier_fragment(
                sym, M, graph._constant_value(h["cid"])))
        else:
            frags.append(_factor_value_text(M))
    shown = [h for h in hops if abs(h["M"] - 1.0) >= 1e-12]
    if not frags:
        # Distinct ids with identical value: show the identity, not a dash.
        return f"1\\,{row_sym} = 1\\,{ref_sym}"
    chain_str = _join_chain(_collapse_repeats(frags))
    if len(shown) <= 1:
        return f"1\\,{row_sym} = {chain_str}\\,{ref_sym}"
    return f"1\\,{row_sym} = {chain_str} = {_factor_value_text(math.prod(h['M'] for h in hops))}\\,{ref_sym}"


def _render_affine_equation(hops, row_sym, ref_sym, graph=None):
    """Affine form for offset chains; composes each hop's (M, c) in path order."""
    a, b = 1.0, 0.0
    scale = 0.0
    for h in hops:
        a, b = h["M"] * a, h["M"] * b + h["c"]
        # Largest intercept magnitude seen mid-composition: float dust in
        # the final b is born at this scale (e.g. ±273.15/491.67 when
        # routing through Celsius), even if the final slope is tiny
        # (SI-prefixed rows like 1.8e-30 × x_qK).
        scale = max(scale, abs(b), abs(h["c"]))
    if not math.isfinite(a) or a == 0:
        return None
    # Snap float dust to zero: composing hops through an offset (e.g.
    # Rankine↔Kelvin via 273.15) can leave residues like b≈5.7e-14 that
    # would render as a spurious `+ 5.6843×10⁻¹⁴`. Epsilon is relative
    # to the equation's own scale so genuine offsets survive.
    if abs(b) <= 1e-9 * max(scale, abs(a), abs(b)):
        b = 0.0
    eq = "="
    lhs, body = f"x\\,{ref_sym}", f"x\\,{row_sym}"
    if abs(a - 1.0) < 1e-9:
        if b == 0:
            return f"{lhs} {eq} {body}"
        return f"{lhs} {eq} {body} - {_nice_num(-b)}" if b < 0 else f"{lhs} {eq} {body} + {_nice_num(b)}"
    if b == 0:
        return f"{lhs} {eq} {_nice_num(a)} \\times {body}"
    c = -b / a
    if 1e-6 <= abs(c) < 1000 and (
        abs(c - round(c)) < 1e-9 or abs(c - round(c, 2)) < 1e-6
    ):
        allowed = _as_int(c) is not None
        if not allowed and graph is not None:
            for h in hops:
                for v in ([graph._constant_value(h["cid"])] if h.get("cid") else []):
                    if math.isfinite(v) and abs(abs(c) - abs(v)) <= 1e-6 * max(1.0, abs(v)):
                        allowed = True
                        break
                if not allowed and math.isfinite(off := abs(h.get("off") or 0.0)) and off > 1e-12:
                    if abs(abs(c) - off) <= 1e-6 * max(1.0, off):
                        allowed = True
                        break
                if allowed:
                    break
        if allowed:
            if c < 0:
                return f"{lhs} {eq} ({body} + {_nice_num(-c)}) \\times {_nice_num(a)}"
            return f"{lhs} {eq} ({body} - {_nice_num(c)}) \\times {_nice_num(a)}"
    equation = f"{lhs} {eq} {_nice_num(a)} \\times {body}"
    if b != 0:
        equation += f" - {_nice_num(-b)}" if b < 0 else f" + {_nice_num(b)}"
    return equation


def _render_numeric_equation(graph, row_id, ref_id):
    if row_id == ref_id:
        return None
    row_val = graph.root_value(row_id)
    ref_val = graph.root_value(ref_id)
    if row_val is None or ref_val is None or ref_val == 0:
        return None
    ratio = row_val / ref_val
    row_sym = wrap_symbol_in_latex(_unit_symbol(graph, row_id))
    ref_sym = wrap_symbol_in_latex(_unit_symbol(graph, ref_id))
    if not math.isfinite(ratio) or (ratio == 0 and row_val != 0):
        # Extreme prefix powers (e.g. m^6) overflow double; compare decades.
        try:
            decade = round(math.log10(abs(row_val)) - math.log10(abs(ref_val)))
        except ValueError:
            return None
        sign = "-" if (row_val < 0) != (ref_val < 0) else ""
        return f"1\\,{row_sym} = {sign}10^{{{decade}}}\\,{ref_sym}"
    if ratio == 1:
        # Distinct ids with identical value: show the identity, not a dash.
        return f"1\\,{row_sym} = 1\\,{ref_sym}"
    return f"1\\,{row_sym} = {_factor_value_text(ratio)}\\,{ref_sym}"
