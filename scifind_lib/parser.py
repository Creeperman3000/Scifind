"""Equation tokeniser + shunting-yard-to-RPN."""

import json
import logging

logger = logging.getLogger("scifind.parser")


_CHAINABLE_RELATIONALS = {
    "eq", "approx", "neq", "ngeq", "sim", "perp", "parallel",
    "lt", "gt", "leq", "geq",
}


def _parse_paren_arg(raw, arity, op_id):
    """Parse the operator.paren_arg JSON column into [bool] of length arity."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("operator %r: paren_arg bad JSON: %s", op_id, exc)
        raise ValueError(
            f"paren_arg for {op_id} must be a JSON list of {arity} 0/1 values; got {raw!r}"
        ) from exc
    if not isinstance(parsed, list) or len(parsed) != arity:
        logger.warning("operator %r: paren_arg wrong shape: %r", op_id, parsed)
        raise ValueError(
            f"paren_arg for {op_id} must be a JSON list of {arity} 0/1 values; got {raw!r}"
        )
    if not all(isinstance(p, (int, bool)) and int(p) in (0, 1) for p in parsed):
        logger.warning("operator %r: paren_arg has non-binary values: %r", op_id, parsed)
        raise ValueError(
            f"paren_arg for {op_id} must contain only 0/1; got {parsed!r}"
        )
    return [bool(p) for p in parsed]


# Cap on a per-connection cache: id(conn) is recycled, so a long-running
# server would otherwise accumulate one entry per request.
_PARSER_CACHE = {}
_PARSER_CACHE_MAX = 64


def _parser_cache_for(conn):
    cache = _PARSER_CACHE.get(id(conn))
    if cache is None:
        if len(_PARSER_CACHE) >= _PARSER_CACHE_MAX:
            for stale in list(_PARSER_CACHE)[:len(_PARSER_CACHE) - _PARSER_CACHE_MAX + 1]:
                del _PARSER_CACHE[stale]
        cache = _PARSER_CACHE[id(conn)] = {}
        cache["qty_ids"] = {r["id"] for r in conn.execute("SELECT id FROM quantity")}
        cache["const_ids"] = {r["id"] for r in conn.execute("SELECT id FROM constant")}
        by_id = {}
        symbol_to_id = {}
        for r in conn.execute(
            "SELECT id, symbol, arity, precedence, associativity, operator_type, paren_arg "
            "FROM operator"
        ):
            by_id[r["id"]] = dict(r)
            if r["symbol"]:
                symbol_to_id[r["symbol"]] = r["id"]
        cache["operators"] = (by_id, symbol_to_id)
    return cache


def _match_operator_at(symbol_to_id, s, i, n):
    """Return (op_id, length) for the longest operator starting at s[i], up to 4 chars."""
    for length in (4, 3, 2, 1):
        if i + length > n:
            continue
        op_id = symbol_to_id.get(s[i:i + length])
        if op_id is None:
            continue
        return op_id, length
    return None, 0


def parse_equation(conn, equation):
    """Tokenize an infix equation string and convert to RPN (shunting-yard).

    Returns token dicts shaped like formula_token rows. Raises ValueError on
    parse error.
    """
    cache = _parser_cache_for(conn)
    op_by_id, symbol_to_id = cache["operators"]
    qty_ids = cache["qty_ids"]
    const_ids = cache["const_ids"]

    if not equation or not equation.strip():
        return []

    s = equation
    pos, n = 0, len(s)
    tokens = []

    while pos < n:
        ch = s[pos]
        if ch.isspace():
            pos += 1
            continue
        if ch.isdigit() or (ch == "." and pos + 1 < n and s[pos + 1].isdigit()):
            j = pos
            seen_dot = False
            seen_exp = False
            while j < n:
                c = s[j]
                if c.isdigit():
                    j += 1
                elif c == "." and not seen_dot and not seen_exp:
                    seen_dot = True
                    j += 1
                elif c in ("e", "E") and not seen_exp:
                    seen_exp = True
                    j += 1
                    if j < n and s[j] in "+-":
                        j += 1
                else:
                    break
            num_str = s[pos:j]
            try:
                value = float(num_str)
            except ValueError as e:
                raise ValueError(f"bad number: {num_str!r}") from e
            tokens.append({"token_kind": "number", "value": value})
            pos = j
            continue
        if ch.isalpha() or ch == "_":
            op_id, op_len = _match_operator_at(symbol_to_id, s, pos, n)
            if op_id is not None:
                tokens.append({"token_kind": "operator", "operator_id": op_id})
                pos += op_len
                continue
            j = pos
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            ident = s[pos:j]
            alias = None
            if j < n and s[j] == "[":
                k = s.find("]", j + 1)
                if k == -1:
                    raise ValueError(f"unterminated alias for {ident!r}")
                alias = s[j + 1:k] or None
                j = k + 1
            if ident in op_by_id:
                tok = {"token_kind": "operator", "operator_id": ident}
                if alias is not None:
                    raise ValueError(f"operator {ident} cannot have an alias")
                tokens.append(tok)
            else:
                if ident in qty_ids:
                    tok = {"token_kind": "quantity", "quantity_id": ident}
                elif ident in const_ids:
                    tok = {"token_kind": "constant", "constant_id": ident}
                else:
                    raise ValueError(f"unknown identifier: {ident!r}")
                if alias is not None:
                    tok["label"] = alias
                tokens.append(tok)
            pos = j
            continue
        if ch == "(":
            tokens.append({"token_kind": "operator", "operator_id": "paren_open"})
            pos += 1
            continue
        if ch == ")":
            tokens.append({"token_kind": "operator", "operator_id": "paren_close"})
            pos += 1
            continue
        op_id, op_len = _match_operator_at(symbol_to_id, s, pos, n)
        if op_id is not None:
            tokens.append({"token_kind": "operator", "operator_id": op_id})
            pos += op_len
            continue
        raise ValueError(f"unexpected character: {ch!r} at position {pos}")

    return _infix_to_rpn(tokens, op_by_id)


def _infix_to_rpn(tokens, op_by_id):
    """Convert a flat infix token list to RPN.

    Each operator stack entry carries a `consumed` counter: only operators
    that have consumed their full arity may be popped by the precedence rule,
    and each emitted operand bumps the topmost still-open operator. The
    outermost token of a `(...)` group gets a `_paren_wrap=True` marker which
    the renderer uses to preserve explicit parens.
    """
    output = []
    stack = []

    def _bump_operand_count():
        for entry in reversed(stack):
            if entry["operator_id"] == "paren_open":
                continue
            op_meta = op_by_id.get(entry["operator_id"])
            if op_meta is None:
                continue
            if entry["consumed"] >= op_meta["arity"]:
                continue
            entry["consumed"] += 1
            return

    for tok in tokens:
        kind = tok["token_kind"]
        if kind in ("number", "quantity", "constant"):
            output.append(tok)
            while stack and stack[-1]["operator_id"] in op_by_id:
                top_op = op_by_id[stack[-1]["operator_id"]]
                if top_op["operator_type"] not in ("prefix", "postfix"):
                    break
                output.append(stack.pop())
            _bump_operand_count()
            continue
        op_id = tok["operator_id"]
        if op_id == "paren_open":
            stack.append({**tok, "consumed": 0})
            continue
        if op_id == "paren_close":
            while stack and stack[-1]["operator_id"] != "paren_open":
                output.append(stack.pop())
            if not stack:
                raise ValueError("unmatched ')'")
            stack.pop()
            if output:
                output[-1]["_paren_wrap"] = True
            while stack:
                top_id = stack[-1]["operator_id"]
                if top_id == "paren_open":
                    break
                top_op = op_by_id.get(top_id)
                if top_op is None or top_op["operator_type"] != "prefix":
                    break
                output.append(stack.pop())
            _bump_operand_count()
            continue
        op = op_by_id.get(op_id)
        if op is None:
            raise ValueError(f"unknown operator: {op_id!r}")
        op_type = op["operator_type"]
        prec = op["precedence"]
        assoc = op["associativity"]
        if op_type in ("prefix", "postfix"):
            stack.append({**tok, "consumed": 0})
            continue
        if assoc == "none" and op_type == "relational":
            while stack and stack[-1]["operator_id"] != "paren_open":
                top_id = stack[-1]["operator_id"]
                top_op = op_by_id.get(top_id)
                if top_op and top_op["operator_type"] == "relational":
                    break
                output.append(stack.pop())
            stack.append({**tok, "consumed": 0})
            continue
        while stack:
            top_entry = stack[-1]
            top_id = top_entry["operator_id"]
            if top_id == "paren_open":
                break
            top_op = op_by_id.get(top_id)
            if top_op is None or top_op["operator_type"] in ("prefix", "postfix"):
                break
            if (
                top_op["precedence"] == prec
                and assoc == "left"
                and top_entry["consumed"] >= top_op["arity"]
            ):
                output.append(stack.pop())
            elif top_op["precedence"] > prec and top_entry["consumed"] >= top_op["arity"]:
                output.append(stack.pop())
            else:
                break
        stack.append({**tok, "consumed": 0})

    while stack:
        top_entry = stack.pop()
        if top_entry["operator_id"] in ("paren_open", "paren_close"):
            raise ValueError("unmatched parenthesis")
        output.append(top_entry)

    return output