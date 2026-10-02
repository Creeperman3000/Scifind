"""``s2.<b64url(gzip(json))>`` share token for the print selection.

Formulas travel as RPN token arrays (``["q", qid, sym?, nam?, label?]`` /
``["c", id]`` / ``["o", id]`` / ``["n", value]``), quantities as display
strings (``{"n", "s", "u"}``). The token length is the only user-visible
budget; ``_SAFETY_*`` caps bound hostile input, not users.
"""

import base64
import binascii
import gzip
import json
import math
import re

SELECTION_VERSION = 2
SEL_TOKEN_PREFIX = "s2."
SEL_TOKEN_MAX_CHARS = 8000

# Safety caps (DoS bounds, not user quotas — the token length governs).
_SAFETY_IDS = 5000
_SAFETY_FLAGS = 5000
_SAFETY_CUSTOMS = 500
_SAFETY_TOKENS = 500

SEL_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,80}$")

_NAME_MAX = 200
_SYM_MAX = 100
_UNIT_MAX = 200
_LABEL_MAX = 200
_EQUATION_MAX = 2000


def _valid_id(value):
    return isinstance(value, str) and bool(SEL_ID_RE.match(value))


def _text(value, limit):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value[:limit] if len(value) > limit else value


def _clean_ids(ids_value):
    if isinstance(ids_value, str):
        ids_value = ids_value.split(",")
    if not isinstance(ids_value, (list, tuple)):
        return []
    ids, seen = [], set()
    for raw in ids_value:
        sid = raw.strip() if isinstance(raw, str) else ""
        if sid and sid not in seen and SEL_ID_RE.match(sid):
            seen.add(sid)
            ids.append(sid)
            if len(ids) >= _SAFETY_IDS:
                break
    return ids


def _clean_token(tok):
    """Normalized compact token or None."""
    if not isinstance(tok, (list, tuple)) or not tok:
        return None
    kind = tok[0]
    if kind == "q":
        if len(tok) < 2 or len(tok) > 5:
            return None
        if not _valid_id(tok[1]):
            return None
        sym = _text(tok[2], _SYM_MAX) if len(tok) > 2 else ""
        nam = _text(tok[3], _NAME_MAX) if len(tok) > 3 else ""
        lab = _text(tok[4], _LABEL_MAX) if len(tok) > 4 else ""
        # Drop trailing empties to keep the encoding minimal.
        parts = [sym, nam, lab]
        while parts and not parts[-1]:
            parts.pop()
        return ["q", tok[1], *parts]
    if kind == "c":
        if len(tok) != 2 or not _valid_id(tok[1]):
            return None
        return ["c", tok[1]]
    if kind == "o":
        if len(tok) != 2 or not _valid_id(tok[1]):
            return None
        return ["o", tok[1]]
    if kind == "n":
        if len(tok) != 2:
            return None
        value = tok[1]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(value):
            return None
        return ["n", value]
    return None


def _clean_tokens(raw):
    if not isinstance(raw, (list, tuple)) or not raw or len(raw) > _SAFETY_TOKENS:
        return None
    out = []
    for tok in raw:
        clean = _clean_token(tok)
        if clean is None:
            return None
        out.append(clean)
    return out


def _clean_formula_snap(value):
    if not isinstance(value, dict):
        return None
    name = _text(value.get("n"), _NAME_MAX)
    tokens = _clean_tokens(value.get("t")) if value.get("t") is not None else None
    if value.get("t") is not None and tokens is None:
        return None
    equation = _text(value.get("e"), _EQUATION_MAX)
    if not name and not tokens:
        return None
    out = {}
    if name:
        out["n"] = name
    if tokens:
        out["t"] = tokens
    if equation:
        out["e"] = equation
    return out or None


def _clean_formula_custom(item):
    if not isinstance(item, dict) or not _valid_id(item.get("i")):
        return None
    snap = _clean_formula_snap(item)
    if not snap or not snap.get("t"):
        return None
    return {"i": item["i"], **snap}


def _clean_quantity_snap(value):
    if not isinstance(value, dict):
        return None
    name = _text(value.get("n"), _NAME_MAX)
    sym = _text(value.get("s"), _SYM_MAX)
    unit = _text(value.get("u"), _UNIT_MAX)
    if not name and not sym and not unit:
        return None
    out = {}
    if name:
        out["n"] = name
    if sym:
        out["s"] = sym
    if unit:
        out["u"] = unit
    return out or None


def _clean_quantity_custom(item):
    if not isinstance(item, dict) or not _valid_id(item.get("i")):
        return None
    snap = _clean_quantity_snap(item)
    if snap is None:
        return None
    return {"i": item["i"], **snap}


def _empty_payload():
    return {"v": SELECTION_VERSION, "f": [], "q": [],
            "fo": {}, "cf": [], "qo": {}, "cq": [],
            "off": {}, "qoff": {}}


def _clean_map(raw, clean_fn):
    out = {}
    if isinstance(raw, dict):
        for key, value in list(raw.items())[:_SAFETY_FLAGS]:
            if not _valid_id(key):
                continue
            try:
                entry = clean_fn(value)
            except (AttributeError, TypeError, ValueError):
                continue
            if entry is not None:
                out[key] = entry
    return out


def _clean_flags(raw):
    if not isinstance(raw, dict):
        return {}
    return {fid: 1 for fid, flag in list(raw.items())[:_SAFETY_FLAGS] if _valid_id(fid) and flag}


def _clean_list(raw, clean_fn):
    out = []
    if isinstance(raw, list):
        for item in raw[:_SAFETY_CUSTOMS]:
            try:
                entry = clean_fn(item)
            except (AttributeError, TypeError, ValueError):
                continue
            if entry is not None and all(e["i"] != entry["i"] for e in out):
                out.append(entry)
    return out


def normalize_selection_payload(raw):
    """Validate/normalize an untrusted share payload dict (never raises)."""
    if not isinstance(raw, dict):
        return _empty_payload()
    try:
        return {"v": SELECTION_VERSION,
                "f": _clean_ids(raw.get("f")),
                "q": _clean_ids(raw.get("q")),
                "fo": _clean_map(raw.get("fo"), _clean_formula_snap),
                "cf": _clean_list(raw.get("cf"), _clean_formula_custom),
                "qo": _clean_map(raw.get("qo"), _clean_quantity_snap),
                "cq": _clean_list(raw.get("cq"), _clean_quantity_custom),
                "off": _clean_flags(raw.get("off")),
                "qoff": _clean_flags(raw.get("qoff"))}
    except (AttributeError, TypeError, ValueError):
        return _empty_payload()


def compact_to_token_dicts(tokens):
    """Compact token arrays -> RPN token dicts (for ``render_tokens_latex``)."""
    out = []
    for tok in tokens or []:
        kind = tok[0] if tok else None
        if kind == "q":
            entry = {"token_kind": "quantity", "quantity_id": tok[1]}
            sym = tok[2] if len(tok) > 2 else ""
            nam = tok[3] if len(tok) > 3 else ""
            lab = tok[4] if len(tok) > 4 else ""
            if sym:
                entry["symbol_overwrite"] = sym
            if nam:
                entry["name_overwrite"] = nam
            if lab:
                entry["label"] = lab
            out.append(entry)
        elif kind == "c":
            out.append({"token_kind": "constant", "constant_id": tok[1]})
        elif kind == "o":
            out.append({"token_kind": "operator", "operator_id": tok[1]})
        elif kind == "n":
            out.append({"token_kind": "number", "value": tok[1]})
    return out


def token_dicts_to_compact(tokens):
    """RPN token dicts (plain-string overwrites) -> compact token arrays."""
    out = []
    for tok in tokens or []:
        kind = tok.get("token_kind")
        if kind == "quantity":
            sym = _text(tok.get("symbol_overwrite"), _SYM_MAX)
            nam = _text(tok.get("name_overwrite"), _NAME_MAX)
            lab = _text(tok.get("label"), _LABEL_MAX)
            parts = [sym, nam, lab]
            while parts and not parts[-1]:
                parts.pop()
            out.append(["q", tok["quantity_id"], *parts])
        elif kind == "constant":
            out.append(["c", tok["constant_id"]])
        elif kind == "operator":
            out.append(["o", tok["operator_id"]])
        elif kind == "number":
            out.append(["n", tok["value"]])
    return out


def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64u_decode(text: str) -> bytes:
    padded = text + "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def encode_selection(payload):
    """Normalized payload -> share token (raises ValueError)."""
    normalized = normalize_selection_payload(payload)
    payload_bytes = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"),
                               sort_keys=True).encode("utf-8")
    token = SEL_TOKEN_PREFIX + _b64u_encode(gzip.compress(payload_bytes, mtime=0))
    if len(token) > SEL_TOKEN_MAX_CHARS:
        raise ValueError(f"selection too large for a share link ({len(token)} chars)")
    return token


def decode_selection(token):
    """Share token -> normalized payload (raises ValueError)."""
    if not isinstance(token, str) or not token.startswith(SEL_TOKEN_PREFIX):
        raise ValueError("not a selection share token")
    if len(token) > len(SEL_TOKEN_PREFIX) + SEL_TOKEN_MAX_CHARS:
        raise ValueError("selection token too large")
    body = token[len(SEL_TOKEN_PREFIX):]
    if not body:
        raise ValueError("malformed selection token")
    try:
        payload_bytes = gzip.decompress(_b64u_decode(body))
    except (binascii.Error, ValueError, OSError, EOFError) as exc:
        raise ValueError(f"malformed selection token: {exc}") from exc
    if len(payload_bytes) > 2 * 1024 * 1024:
        raise ValueError("selection payload too large")
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"malformed selection payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("malformed selection payload")
    return normalize_selection_payload(payload)
