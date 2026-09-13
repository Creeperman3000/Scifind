"""Data-driven operator machinery: latex templates + dim_spec evaluator."""

import json
import re

DIM_TOLERANCE = 1e-9

class OperatorDefinition:
    __slots__ = ("id", "symbol", "aliases", "arity", "precedence", "associativity", "fixity", "latex_template", "dim_spec")
    def __init__(self, row):
        self.id = row["id"]
        self.symbol = row.get("symbol")
        try:
            aliases = json.loads(row.get("aliases") or "[]")
        except (ValueError, TypeError):
            aliases = []
        self.aliases = [a for a in aliases if isinstance(a, str) and a]
        self.arity = row["arity"]
        self.precedence = row["precedence"]
        self.associativity = row["associativity"]
        self.fixity = row["type"]
        self.latex_template = row["latex_template"]
        raw_spec = row.get("dim_spec") or ""
        if isinstance(raw_spec, dict):
            self.dim_spec = dict(raw_spec)
            _validate_dim_spec(self.dim_spec, self.arity, self.id)
        else:
            self.dim_spec = parse_dim_spec(str(raw_spec), self.arity, self.id)
        _validate_template(self.latex_template, self.arity, self.id)
        kind = self.dim_spec.get("_result")
        if self.fixity == "relational":
            if kind != "any":
                raise ValueError(f"operator {self.id!r}: relational operators need 'result any' so n-ary folds stay aligned")
        elif kind == "any":
            raise ValueError(f"operator {self.id!r}: 'result any' is only for relational operators")

OPERATOR_COLUMNS = "id, symbol, aliases, arity, precedence, associativity, type, latex_template, dim_spec"

def load_operators(conn):
    return {r["id"]: OperatorDefinition(dict(r)) for r in conn.execute(f"SELECT {OPERATOR_COLUMNS} FROM operator")}

def alias_to_id_map(operators):
    mapping = {}
    for op in operators.values():
        for spelling in [op.id, *op.aliases]:
            if spelling:
                mapping.setdefault(spelling, op.id)
    return mapping

def operand_info(kind, value=None, ref=None, placeholder=False):
    return {"kind": kind, "value": value, "ref": ref, "placeholder": bool(placeholder)}

_PLACEHOLDER_RE = re.compile(r"\[\[(\d+)(!)?")
_MATCHER_RE = re.compile(r"(num|const|qty):")
_MATCHER_BAD = re.compile(r"[\[\]{}?:]")

def _check_indexes(kind, rest, arity, op_id):
    if kind == "text":
        return
    if kind == "slot":
        if rest[0] >= arity:
            raise ValueError(f"operator {op_id!r}: template slot {{{rest[0]}}} exceeds arity {arity}")
        return
    cond_idx, _, then_toks, else_toks = rest
    if cond_idx >= arity:
        raise ValueError(f"operator {op_id!r}: template condition {{{cond_idx}?...}} exceeds arity {arity}")
    for tok in then_toks + else_toks:
        _check_indexes(tok[0], tok[1:], arity, op_id)

def _validate_template(template, arity, op_id):
    if not isinstance(template, str) or not template:
        raise ValueError(f"operator {op_id!r}: latex_template must be non-empty")
    for kind, *rest in _parse_template(template, op_id):
        _check_indexes(kind, rest, arity, op_id)

def _parse_matcher(s, pos, op_id):
    m = _MATCHER_RE.match(s[pos:])
    if not m:
        raise ValueError(f"operator {op_id!r}: bad matcher in latex_template {s!r} (expected num:<float>, const:<id> or qty:<id>)")
    kind = m.group(1)
    pos += len(m.group(0))
    end = s.find("?", pos)
    if end == -1:
        raise ValueError(f"operator {op_id!r}: matcher without '?then:else' in {s!r}")
    arg = s[pos:end]
    if kind == "num":
        try:
            return ("num", float(arg)), end
        except ValueError as exc:
            raise ValueError(f"operator {op_id!r}: bad num matcher {arg!r} in {s!r}") from exc
    if not arg or _MATCHER_BAD.search(arg):
        raise ValueError(f"operator {op_id!r}: bad {kind} matcher {arg!r} in {s!r}")
    return (kind, arg), end

def _parse_seq(s, pos, op_id, closing):
    toks, buf = [], []
    def flush():
        if buf:
            toks.append(("text", "".join(buf)))
            del buf[:]
    while pos < len(s):
        if s.startswith("[[", pos):
            m = _PLACEHOLDER_RE.match(s[pos:])
            if not m:
                buf.append("[")
                pos += 1
                continue
            idx = int(m.group(1))
            bare = m.group(2) == "!"
            pos += len(m.group(0))
            matcher = None
            if s[pos:pos + 1] == "=":
                if bare:
                    raise ValueError(f"operator {op_id!r}: '[[{idx}!=' mixes grouping with matching in {s!r}; put '!' on the slots inside the branches")
                pos += 1
                matcher, pos = _parse_matcher(s, pos, op_id)
            if s.startswith("]]", pos):
                if matcher is not None:
                    raise ValueError(f"operator {op_id!r}: matcher without '?then:else' in {s!r}")
                flush()
                toks.append(("slot", idx, bare))
                pos += 2
                continue
            if s[pos:pos + 1] == "?":
                flush()
                then_toks, pos = _parse_seq(s, pos + 1, op_id, closing=":")
                if s[pos:pos + 1] != ":":
                    raise ValueError(f"operator {op_id!r}: '[[{idx}?...' misses ':' in {s!r}")
                else_toks, pos = _parse_seq(s, pos + 1, op_id, closing="]]")
                if not s.startswith("]]", pos):
                    raise ValueError(f"operator {op_id!r}: '[[{idx}?...:...' misses ']]' in {s!r}")
                toks.append(("cond", idx, matcher, then_toks, else_toks))
                pos += 2
                continue
            raise ValueError(f"operator {op_id!r}: bad '[[{idx}' in latex_template {s!r}")
        if s.startswith("]]", pos):
            if closing in (":", "]]"):
                break
            buf.append("]]")
            pos += 2
        elif s[pos:pos + 1] == ":" and closing == ":":
            break
        else:
            buf.append(s[pos])
            pos += 1
    flush()
    return toks, pos

def _parse_template(template, op_id):
    toks, pos = _parse_seq(template, 0, op_id, closing=None)
    if pos != len(template):
        raise ValueError(f"operator {op_id!r}: bad latex_template {template!r}")
    return toks

def _matcher_matches(matcher, info):
    kind, arg = matcher
    if kind == "num":
        return info.get("kind") == "number" and info.get("value") is not None and info["value"] == arg
    want = {"const": "constant", "qty": "quantity"}.get(kind)
    return want is not None and info.get("kind") == want and info.get("ref") == arg

def _render_tokens(toks, operands, infos):
    out = []
    for tok in toks:
        if tok[0] == "text":
            out.append(tok[1])
        elif tok[0] == "slot":
            out.append(operands[tok[1]])
        else:
            _, idx, matcher, then_toks, else_toks = tok
            take_then = _matcher_matches(matcher, infos[idx]) if matcher is not None else operands[idx]
            out.append(_render_tokens(then_toks if take_then else else_toks, operands, infos))
    return "".join(out)

def render_template(template, operands, infos, op_id="<template>"):
    operands, infos = list(operands), list(infos)
    if len(operands) != len(infos):
        raise ValueError(f"operator {op_id!r}: {len(operands)} operands vs {len(infos)} descriptors")
    try:
        return _render_tokens(_parse_template(template, op_id), operands, infos)
    except IndexError as exc:
        raise ValueError(f"operator {op_id!r}: template {template!r} needs {len(operands)} operands") from exc

def _slot_info(template, op_id="<template>"):
    top, bare = -1, set()
    def walk(ts):
        nonlocal top
        for t in ts:
            if t[0] == "text":
                continue
            top = max(top, t[1])
            if t[0] == "slot":
                if t[2]:
                    bare.add(t[1])
            else:
                walk(t[3])
                walk(t[4])
    walk(_parse_template(template, op_id))
    return top + 1, bare

def template_arity(template, op_id="<template>"):
    return _slot_info(template, op_id)[0]

def template_bare_slots(template, op_id="<template>"):
    return _slot_info(template, op_id)[1]

_DIM_CLAUSE_EXAMPLES = "'drop(0)', 'require same(all)', 'require dimless(1)', 'result same', 'result zero', 'result any', 'result dims(0)+dims(1)'"
_DROP_RE = re.compile(r"^drop\s*\(\s*(?P<args>.*)\s*\)$", re.IGNORECASE)
_REQUIRE_RE = re.compile(r"^require\s+(?P<kind>same|dimless)\s*\(\s*(?P<args>.*)\s*\)$", re.IGNORECASE)
_RESULT_RE = re.compile(r"^result\s+(?P<body>.+)$", re.IGNORECASE | re.DOTALL)
_TERM_RE = re.compile(r"^(?:(?P<coeff>\d+(?:\.\d+)?)\s*\*\s*)?dims\(\s*(?P<dim>-?\d+)\s*\)(?:\s*(?P<op>[*/])\s*(?P<weight>value\(\s*-?\d+\s*\)|\d+(?:\.\d+)?))?$", re.IGNORECASE)
_VALUE_RE = re.compile(r"^value\(\s*(?P<idx>-?\d+)\s*\)$", re.IGNORECASE)

def _wrap_dim_index(i, arity, op_id, what):
    j = i + arity if i < 0 else i
    if not 0 <= j < arity:
        raise ValueError(f"operator {op_id!r}: dim_spec {what} index {i} outside arity {arity}")
    return j

def _parse_idx_list(arg, arity, op_id, what):
    arg = (arg or "").strip()
    if arg.lower() == "all":
        return True
    if not arg:
        raise ValueError(f"operator {op_id!r}: dim_spec {what} needs indexes or 'all' (e.g. {what}(all), {what}(0, 1))")
    out = []
    for part in arg.split(","):
        part = part.strip()
        if not re.fullmatch(r"-?\d+", part or ""):
            raise ValueError(f"operator {op_id!r}: dim_spec {what} has bad index {part!r} (expected e.g. {what}(all), {what}(0, 1))")
        j = _wrap_dim_index(int(part), arity, op_id, what)
        if j in out:
            raise ValueError(f"operator {op_id!r}: dim_spec {what} repeats index {j}")
        out.append(j)
    return sorted(out)

def _split_terms(expr, op_id):
    terms, buf, sign, depth = [], [], 1, 0
    def bad(msg):
        raise ValueError(f"operator {op_id!r}: dim_spec result expression {expr!r} {msg}")
    for ch in expr:
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth -= 1
            if depth < 0:
                bad("has unbalanced ')'")
            buf.append(ch)
        elif depth == 0 and ch in "+-":
            chunk = "".join(buf).strip()
            if chunk:
                terms.append((sign, chunk))
            elif terms or sign != 1 or not buf:
                bad("has an empty term")
            sign = 1 if ch == "+" else -1
            buf = []
        else:
            buf.append(ch)
    if depth != 0:
        bad("has unbalanced '('")
    chunk = "".join(buf).strip()
    if not chunk:
        bad("has an empty term")
    terms.append((sign, chunk))
    return terms

def _parse_result_expr(expr, arity, op_id):
    factors, seen = [0] * arity, set()
    for sign, term in _split_terms(expr, op_id):
        m = _TERM_RE.match(term)
        if not m:
            raise ValueError(f"operator {op_id!r}: dim_spec result term {term!r} is not of the form dims(i), n*dims(i), dims(i)*value(j) or dims(i)/value(j)")
        d = _wrap_dim_index(int(m.group("dim")), arity, op_id, "dims")
        if d in seen:
            raise ValueError(f"operator {op_id!r}: dim_spec result mentions dims({d}) twice")
        seen.add(d)
        coeff = float(m.group("coeff")) if m.group("coeff") else 1.0
        op, weight = m.group("op"), (m.group("weight") or "").strip()
        if not weight:
            factors[d] = sign * coeff
            continue
        if (vm := _VALUE_RE.match(weight)) is not None:
            if sign != 1 or coeff != 1.0:
                raise ValueError(f"operator {op_id!r}: dim_spec value-weighted term {term!r} must be positive with no numeric prefix (e.g. dims({d})*value(j))")
            j = _wrap_dim_index(int(vm.group("idx")), arity, op_id, "value")
            factors[d] = {"value_of": j} if op == "*" else {"value_of": j, "invert": True}
            continue
        try:
            number = float(weight)
        except ValueError as exc:
            raise ValueError(f"operator {op_id!r}: dim_spec result term {term!r} has a bad weight") from exc
        if number == 0 and op == "/":
            raise ValueError(f"operator {op_id!r}: dim_spec result term {term!r} divides by zero")
        factors[d] = sign * coeff * (number if op == "*" else 1.0 / number)
    return factors

def parse_dim_spec(text, arity, op_id):
    raw = text if isinstance(text, str) else "" if text is None else str(text)
    clauses = [c.strip() for c in raw.split(";") if c.strip()]
    if not clauses:
        raise ValueError(f"operator {op_id!r}: dim_spec must declare exactly one 'result ...' clause (e.g. {_DIM_CLAUSE_EXAMPLES})")
    drop_spec = same_spec = dimless_spec = result_clause = None
    def _dup(old, label):
        if old is not None:
            raise ValueError(f"operator {op_id!r}: dim_spec has two {label} clauses")
    for clause in clauses:
        if (m := _DROP_RE.match(clause)):
            _dup(drop_spec, "'drop(...)'")
            drop_spec = _parse_idx_list(m.group("args"), arity, op_id, "drop")
        elif (m := _REQUIRE_RE.match(clause)):
            kind = m.group("kind").lower()
            parsed = _parse_idx_list(m.group("args"), arity, op_id, "same" if kind == "same" else "dimless")
            if kind == "same":
                _dup(same_spec, "'require same(...)'")
                same_spec = parsed
            else:
                _dup(dimless_spec, "'require dimless(...)'")
                dimless_spec = parsed
        elif (m := _RESULT_RE.match(clause)):
            _dup(result_clause, "'result ...'")
            result_clause = m.group("body").strip()
        else:
            raise ValueError(f"operator {op_id!r}: dim_spec clause {clause!r} is unknown (expected {_DIM_CLAUSE_EXAMPLES})")
    if result_clause is None:
        raise ValueError(f"operator {op_id!r}: dim_spec must declare exactly one 'result ...' clause (e.g. {_DIM_CLAUSE_EXAMPLES})")
    lowered, spec = result_clause.lower(), {}
    if lowered == "same":
        if same_spec is None:
            raise ValueError(f"operator {op_id!r}: 'result same' needs 'require same(...)' (e.g. 'require same(all); result same')")
        spec["factors"], spec["equal"], result_kind = 1, same_spec, "same"
    elif lowered == "any":
        if same_spec is not None:
            raise ValueError(f"operator {op_id!r}: 'result any' cannot be combined with 'require same(...)'")
        spec["factors"], result_kind = 1, "any"
    elif lowered == "zero":
        if same_spec is not None:
            raise ValueError(f"operator {op_id!r}: 'result zero' cannot be combined with 'require same(...)' (same(...) already fixes the result)")
        spec["factors"], result_kind = [0] * arity, "zero"
    else:
        if same_spec is not None:
            raise ValueError(f"operator {op_id!r}: 'require same(...)' needs 'result same' (a linear 'result {result_clause}' cannot also return the common vector)")
        spec["factors"], result_kind = _parse_result_expr(result_clause, arity, op_id), "expr"
    if dimless_spec is not None:
        spec["dimensionless"] = dimless_spec
    if drop_spec is not None:
        spec["placeholders"] = list(range(arity)) if drop_spec is True else list(drop_spec)
    _validate_dim_spec(spec, arity, op_id)
    spec["_result"] = result_kind
    return spec

def _is_broadcast(factor):
    return type(factor) in (int, float)

def _norm_indexes(value, arity, op_id, what, allow_true=True):
    if value is None:
        return set()
    if value is True and allow_true:
        return set(range(arity))
    if isinstance(value, list) and all(type(i) is int for i in value):
        return {_wrap_dim_index(i, arity, op_id, what) for i in value}
    raise ValueError(f"operator {op_id!r}: dim_spec {what} must be true or a list of indexes")

def _validate_dim_spec(spec, arity, op_id):
    factors = spec.get("factors", 1)
    ok = _is_broadcast(factors) or (isinstance(factors, list) and len(factors) == arity
            and all(_is_broadcast(f) or _is_value_ref(f) for f in factors))
    if not ok:
        raise ValueError(f"operator {op_id!r}: dim_spec factors must be a number or a list of {arity} numbers / value_of refs")
    for f in factors if isinstance(factors, list) else []:
        if isinstance(f, dict):
            j = f["value_of"] + arity if f["value_of"] < 0 else f["value_of"]
            if not 0 <= j < arity:
                raise ValueError(f"operator {op_id!r}: dim_spec value_of index {j} outside arity {arity}")
    _norm_indexes(spec.get("equal"), arity, op_id, "equal")
    _norm_indexes(spec.get("dimensionless"), arity, op_id, "dimensionless")
    _norm_indexes(spec.get("placeholders") or [], arity, op_id, "placeholders", allow_true=False)

def _is_value_ref(factor):
    return (isinstance(factor, dict) and set(factor) <= {"value_of", "invert"}
            and type(factor.get("value_of")) is int and isinstance(factor.get("invert", False), bool))

def _is_zero(vec):
    return all(abs(v) <= DIM_TOLERANCE for v in vec)

def _resolve_factor(factor, child_infos, op_id):
    if _is_broadcast(factor):
        return float(factor)
    j = factor["value_of"] + len(child_infos) if factor["value_of"] < 0 else factor["value_of"]
    if not 0 <= j < len(child_infos):
        raise ValueError(f"operator {op_id!r}: value_of index outside operands")
    info = child_infos[j]
    if info.get("kind") == "number" and info.get("value") is not None:
        value = info["value"]
        if factor.get("invert"):
            if value == 0:
                raise ValueError("exponent must be non-zero for reciprocal scaling")
            return 1.0 / value
        return float(value)
    if info.get("kind") in ("quantity", "operator"):
        return 1.0
    raise ValueError("exponent must be a number, quantity, or operator expression; " f"got kind={info.get('kind')!r}")

def apply_dim_spec(spec, child_dims, child_infos, op_id):
    n = len(child_dims)
    width = len(child_dims[0]) if child_dims else 0
    zeros = [0.0] * width
    spec = spec or {}
    raw = spec.get("factors", 1)
    arity = len(raw) if isinstance(raw, list) else n
    kept = [i for i in range(n) if not (child_infos[i].get("placeholder") and i in (spec.get("placeholders") or []))]
    def _as_set(value):
        if value is True:
            return set(kept)
        return {i for i in _norm_indexes(value, arity, op_id, "indexes") if i in kept}
    for i in _as_set(spec.get("dimensionless")):
        if not _is_zero(child_dims[i]):
            raise ValueError(f"argument of {op_id} must be dimensionless; got {list(child_dims[i])}")
    eq = _as_set(spec.get("equal"))
    if spec.get("equal") is not None:
        if not eq:
            return list(zeros)
        ordered = sorted(eq)
        first = list(child_dims[ordered[0]])
        for i in ordered[1:]:
            if any(abs(a - b) > DIM_TOLERANCE for a, b in zip(first, child_dims[i])):
                raise ValueError(f"operands of {op_id} have mismatched dimensions: {first} vs {list(child_dims[i])}")
        return first
    if _is_broadcast(raw):
        weights = [float(raw)] * n
    else:
        if len(raw) != n:
            raise ValueError(f"operator {op_id!r}: {len(raw)} factors for {n} operands")
        weights = [_resolve_factor(f, child_infos, op_id) for f in raw]
    result = list(zeros)
    for weight, vec in zip(weights, child_dims):
        for i, v in enumerate(vec):
            result[i] += weight * v
    return result
