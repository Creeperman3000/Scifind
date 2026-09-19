"""Shared small helpers: safe JSON parsing, ints, localized SQL columns."""

import html
import json
import logging
import math
import re

logger = logging.getLogger(__name__)

# Shared sci-notation thresholds: >= LARGE or < SMALL renders as scientific notation.
SCI_LARGE_THRESHOLD = 1e4
SCI_SMALL_THRESHOLD = 1e-4


def _safe_json(json_text, kind, default):
    """Parse JSON `json_text`; fall back to `default` (copied if mutable) on NULL/bad input."""
    blank = kind() if default is None else default
    fallback = dict(blank) if isinstance(blank, dict) else list(blank) if isinstance(blank, list) else blank
    if not json_text: return fallback
    try: parsed = json.loads(json_text)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("safe_json: bad JSON: %s", exc)
        return fallback
    return parsed if isinstance(parsed, kind) else fallback


def safe_json_dict(json_text, *, default=None):
    """Parse JSON object text; return {} (or `default`) on NULL/bad input."""
    return _safe_json(json_text, dict, {} if default is None else default)


def safe_json_list(json_text, *, default=None):
    """Parse JSON list text; return [] (or `default`) on NULL/bad input."""
    return _safe_json(json_text, list, [] if default is None else default)


def parse_int_or(value, default=None):
    """int(value) with fallback to `default` on blank/bad input."""
    if value is None or value == "": return default
    try: return int(value)
    except (TypeError, ValueError): return default


def slugify_text(value):
    """Lowercase snake_case slug mirroring web/utils.js slugify."""
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def split_sci_mantissa(value):
    """Normalize positive `value` to (mantissa in [1,10), exponent); (0.0, 0) for 0."""
    if not value: return 0.0, 0
    exponent = int(math.floor(math.log10(value)))
    mantissa = value / (10.0 ** exponent)
    if mantissa >= 10:
        exponent += 1
        mantissa = value / (10.0 ** exponent)
    return mantissa, exponent


def render_sci_latex(sign, mant_str, exp):
    """`[sign]mant\\times10^{exp}` (mant_str already formatted)."""
    return f"{sign}{mant_str}\\times10^{{{exp}}}"


def as_int(value):
    """int(value) when within 1e-9 relative tolerance and |v| < 1e15, else None."""
    try: v = float(value); r = round(v)
    except (TypeError, ValueError): return None
    if r == 0: return 0 if v == 0 else None
    return int(r) if abs(v - r) <= 1e-9 * abs(v) and abs(r) < 1e15 else None


def format_sci_parts(value):
    """Single sci-splitting path: {sign, int, dec, exp} with mantissa in [1,10)."""
    v = float(value)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= SCI_LARGE_THRESHOLD or (a and a < SCI_SMALL_THRESHOLD):
        mantissa, exponent = split_sci_mantissa(a)
        mant_text = f"{mantissa:.9f}"
        if float(mant_text) >= 10: exponent += 1; mantissa = a / 10 ** exponent; mant_text = f"{mantissa:.9f}"
        int_part, _, dec = mant_text.rstrip("0").rstrip(".").partition(".")
        return {"sign": sign, "int": int_part, "dec": dec, "exp": exponent}
    int_part, _, dec = f"{a:.10g}".partition(".")
    return {"sign": sign, "int": int_part, "dec": dec, "exp": None}


def _js_round(x):
    """JS Math.round (half up), unlike Python banker's round."""
    return int(math.floor(float(x) + 0.5))


def eval_dim_expr(raw):
    """Integer expression evaluator mirroring web/app.js evalDimExpr (no eval())."""
    cleaned = re.sub(r"\s+", "", str("" if raw is None else raw))
    if not cleaned or not re.fullmatch(r"[-+*/%^().0-9]+", cleaned):
        return None
    pos = 0

    class _Fail(Exception): pass

    def peek(): return cleaned[pos] if pos < len(cleaned) else ""

    def expr():
        nonlocal pos
        left = term()
        while peek() in ("+", "-"):
            op = cleaned[pos]; pos += 1
            right = term()
            left = left + right if op == "+" else left - right
        return left

    def term():
        nonlocal pos
        left = power()
        while peek() in ("*", "/", "%"):
            op = cleaned[pos]; pos += 1
            right = power()
            if op in ("/", "%") and right == 0:
                raise _Fail()
            if op == "*":
                left = left * right
            elif op == "/":
                left = int(left / right)  # trunc toward zero like Math.trunc
            else:
                q = abs(left) // abs(right)
                if (left < 0) != (right < 0):
                    q = -q
                left = left - right * q
        return left

    def power():
        nonlocal pos
        base = unary()
        if peek() == "^": pos += 1; return _js_round(math.pow(base, power()))
        return base

    def unary():
        nonlocal pos
        if peek() == "+": pos += 1; return +unary()
        if peek() == "-": pos += 1; return -unary()
        return atom()

    def atom():
        nonlocal pos
        if peek() == "(":
            pos += 1; value = expr()
            if peek() != ")": raise _Fail()
            pos += 1
            return value
        start = pos
        while pos < len(cleaned) and "0" <= cleaned[pos] <= "9": pos += 1
        if start == pos: raise _Fail()
        return int(cleaned[start:pos])

    try:
        result = expr()
        if pos != len(cleaned) or not math.isfinite(result): return None
    except (_Fail, ValueError, OverflowError, ZeroDivisionError, TypeError): return None
    return _js_round(result)


_ENTITY_LINK_KINDS = frozenset({"formula", "quantity", "unit", "constant"})


def anchor(url, label):
    """Escaped ``<a href="url">label</a>``."""
    return f'<a href="{html.escape(url)}">{html.escape(label or "")}</a>'


def entity_link(kind, ent_id, display):
    """Render ``<a href="/<kind>/<id>">display</a>``; bad ids render as escaped text only."""
    if kind not in _ENTITY_LINK_KINDS or not isinstance(ent_id, str) \
            or not re.fullmatch(r"^[A-Za-z0-9_]+$", ent_id):
        return html.escape(display or "")
    return anchor(f"/{kind}/{ent_id}", display or "")


def request_cached(key, build):
    """Memoize build() on Flask g for this request; plain call without app context."""
    try:
        from flask import g, has_app_context
    except ImportError:
        return build()
    if not has_app_context():
        return build()
    if getattr(g, key, None) is None:
        setattr(g, key, build())
    return getattr(g, key)
