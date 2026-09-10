"""Equation tokeniser + shunting-yard-to-RPN + RPN-to-tree."""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from scifind_lib.db import in_clause

logger = logging.getLogger("scifind.parser")


CHAINABLE_RELATIONALS = {
    "eq", "approx", "neq", "ngeq", "sim", "perp", "parallel",
    "lt", "gt", "leq", "geq",
}


def parse_paren_arg(raw, arity, op_id):
    """Parse the operator.paren_arg JSON column into [bool] of length arity."""
    errmsg = (
        f"paren_arg for {op_id} must be a JSON list of {arity} 0/1 values; got {raw!r}"
    )
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("operator %r: paren_arg bad JSON: %s", op_id, exc)
        raise ValueError(errmsg) from exc
    if (
        not isinstance(parsed, list)
        or len(parsed) != arity
        or not all(isinstance(p, (int, bool)) and int(p) in (0, 1) for p in parsed)
    ):
        logger.warning("operator %r: paren_arg invalid: %r", op_id, parsed)
        raise ValueError(errmsg)
    return [bool(p) for p in parsed]


def _load_parse_tables(conn):
    """Fresh (qty_ids, const_ids, op_by_id, symbol_to_id) for one parse; uncached to avoid stale rows."""
    qty_ids = {r["id"] for r in conn.execute("SELECT id FROM quantity")}
    const_ids = {r["id"] for r in conn.execute("SELECT id FROM constant")}
    op_by_id = {}
    symbol_to_id = {}
    for r in conn.execute(
        "SELECT id, symbol, arity, precedence, associativity, operator_type, paren_arg "
        "FROM operator"
    ):
        op_by_id[r["id"]] = dict(r)
        if r["symbol"]:
            symbol_to_id[r["symbol"]] = r["id"]
    return qty_ids, const_ids, op_by_id, symbol_to_id


def quantity_token_key(quantity_id, label, pos):
    """Stable key linking a quantity token to its per-occurrence overrides."""
    return f"{quantity_id}|{label or ''}|{pos}"


def _scan_number(equation, pos, length):
    """Scan a float literal at equation[pos]; return (token, next_pos)."""
    j = pos
    seen_dot = False
    seen_exp = False
    while j < length:
        c = equation[j]
        if c.isdigit():
            j += 1
        elif c == "." and not seen_dot and not seen_exp:
            seen_dot = True
            j += 1
        elif c in ("e", "E") and not seen_exp:
            seen_exp = True
            j += 1
            if j < length and equation[j] in "+-":
                j += 1
        else:
            break
    num_str = equation[pos:j]
    try:
        value = float(num_str)
    except ValueError as e:
        raise ValueError(f"bad number: {num_str!r}") from e
    return {"token_kind": "number", "value": value}, j


def _scan_identifier(equation, pos, length, op_by_id, symbol_to_id, qty_ids, const_ids):
    """Scan an identifier/operator/alias at equation[pos]; return (token, next_pos)."""
    op_id, op_len = _match_operator_at(symbol_to_id, equation, pos, length)
    if op_id is not None:
        return {"token_kind": "operator", "operator_id": op_id}, pos + op_len
    j = pos
    while j < length and (equation[j].isalnum() or equation[j] == "_"):
        j += 1
    ident = equation[pos:j]
    alias = None
    if j < length and equation[j] == "[":
        k = equation.find("]", j + 1)
        if k == -1:
            raise ValueError(f"unterminated alias for {ident!r}")
        alias = equation[j + 1:k] or None
        j = k + 1
    if ident in op_by_id:
        if alias is not None:
            raise ValueError(f"operator {ident} cannot have an alias")
        return {"token_kind": "operator", "operator_id": ident}, j
    if ident in qty_ids:
        tok = {"token_kind": "quantity", "quantity_id": ident}
    elif ident in const_ids:
        tok = {"token_kind": "constant", "constant_id": ident}
    else:
        raise ValueError(f"unknown identifier: {ident!r}")
    if alias is not None:
        tok["label"] = alias
    return tok, j


def _match_operator_at(symbol_to_id, equation, i, length):
    """Return (op_id, width) for the longest operator starting at equation[i], up to 4 chars."""
    for width in (4, 3, 2, 1):
        if i + width > length:
            continue
        op_id = symbol_to_id.get(equation[i:i + width])
        if op_id is None:
            continue
        return op_id, width
    return None, 0


def parse_equation(conn, equation):
    """Tokenize an infix equation string and convert to RPN token dicts."""
    qty_ids, const_ids, op_by_id, symbol_to_id = _load_parse_tables(conn)

    if not equation or not equation.strip():
        return []

    pos, length = 0, len(equation)
    tokens = []

    while pos < length:
        char = equation[pos]
        if char.isspace():
            pos += 1
            continue
        if char.isdigit() or (char == "." and pos + 1 < length and equation[pos + 1].isdigit()):
            tok, pos = _scan_number(equation, pos, length)
            tokens.append(tok)
            continue
        if char.isalpha() or char == "_":
            tok, pos = _scan_identifier(
                equation, pos, length, op_by_id, symbol_to_id, qty_ids, const_ids
            )
            tokens.append(tok)
            continue
        if char == "(":
            tokens.append({"token_kind": "operator", "operator_id": "paren_open"})
            pos += 1
            continue
        if char == ")":
            tokens.append({"token_kind": "operator", "operator_id": "paren_close"})
            pos += 1
            continue
        op_id, op_len = _match_operator_at(symbol_to_id, equation, pos, length)
        if op_id is not None:
            tokens.append({"token_kind": "operator", "operator_id": op_id})
            pos += op_len
            continue
        raise ValueError(f"unexpected character: {char!r} at position {pos}")

    return _infix_to_rpn(tokens, op_by_id)


def _infix_to_rpn(tokens, op_by_id):
    """Convert a flat infix token list to RPN; paren groups mark the outer token with `_paren_wrap`."""
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


@dataclass
class FormulaNode:
    """A node in the parsed formula tree; `symbol` is resolved so rendering needs no DB lookups."""
    kind: str
    children: list = field(default_factory=list)
    quantity_id: Optional[str] = None
    constant_id: Optional[str] = None
    value: Optional[float] = None
    label: Optional[str] = None
    symbol_overwrite: Optional[str] = None
    operator_id: Optional[str] = None
    symbol: Optional[str] = None
    arity: int = 0
    precedence: int = 0
    associativity: str = "left"
    operator_type: str = "infix"
    paren_arg: Optional[list] = None
    _paren_wrap: bool = False


_OPERATOR_COLUMNS = (
    "id, symbol, arity, precedence, associativity, operator_type, paren_arg"
)


def bulk_entity_rows(conn, table, columns, ids):
    """{id: row} for `ids` in a single query (empty input → {})."""
    ids = set(ids)
    if not ids:
        return {}
    marks, params = in_clause(ids)
    return {
        r["id"]: dict(r)
        for r in conn.execute(
            f"SELECT {columns} FROM {table} WHERE id IN ({marks})", params
        )
    }


def reduce_rpn_to_tree(conn, tokens):
    """Reduce a token stream to an expression tree via bulk-loaded entity rows."""
    op_map = bulk_entity_rows(
        conn, "operator", _OPERATOR_COLUMNS,
        (t["operator_id"] for t in tokens if t["token_kind"] == "operator"),
    )
    qty_map = bulk_entity_rows(
        conn, "quantity", "id, name, symbol",
        (t["quantity_id"] for t in tokens
         if t["token_kind"] == "quantity" and t["quantity_id"] != "drop"),
    )
    const_map = bulk_entity_rows(
        conn, "constant", "id, symbol",
        (t["constant_id"] for t in tokens if t["token_kind"] == "constant"),
    )
    stack = []
    for tok in tokens:
        kind = tok["token_kind"]
        if kind == "operator":
            op = op_map.get(tok["operator_id"])
            if op is None:
                raise ValueError(f"unknown operator: {tok['operator_id']!r}")
            if len(stack) < op["arity"]:
                raise ValueError(
                    f"RPN underflow at {tok['operator_id']}: need {op['arity']}, have {len(stack)}"
                )
            args = [stack.pop() for _ in range(op["arity"])][::-1]
            new_node = FormulaNode(
                kind="operator",
                children=args,
                operator_id=op["id"],
                symbol=op["symbol"],
                arity=op["arity"],
                precedence=op["precedence"],
                associativity=op["associativity"],
                operator_type=op["operator_type"],
                paren_arg=parse_paren_arg(op["paren_arg"], op["arity"], op["id"]),
                _paren_wrap=bool(tok.get("_paren_wrap")),
            )
            if (
                op["operator_type"] == "relational"
                and op["id"] in CHAINABLE_RELATIONALS
                and len(args) == 2
                and args[1].kind == "operator"
                and args[1].operator_id == op["id"]
                and args[1].operator_type == "relational"
            ):
                inner = args[1]
                new_node.children = [args[0]] + list(inner.children)
                new_node.arity = len(new_node.children)
                new_node._paren_wrap = inner._paren_wrap
            stack.append(new_node)
        elif kind == "quantity":
            qid = tok["quantity_id"]
            q = qty_map.get(qid)
            if q is None:
                if qid == "drop":
                    q = {}
                else:
                    raise ValueError(f"unknown quantity: {qid!r}")
            stack.append(FormulaNode(
                kind="quantity",
                quantity_id=qid,
                label=tok.get("label"),
                symbol_overwrite=tok.get("symbol_overwrite"),
                symbol=q.get("symbol"),
                _paren_wrap=bool(tok.get("_paren_wrap")),
            ))
        elif kind == "constant":
            cid = tok["constant_id"]
            c = const_map.get(cid)
            if c is None:
                raise ValueError(f"unknown constant: {cid!r}")
            stack.append(FormulaNode(
                kind="constant",
                constant_id=cid,
                symbol=c["symbol"] or cid,
                _paren_wrap=bool(tok.get("_paren_wrap")),
            ))
        elif kind == "number":
            stack.append(FormulaNode(
                kind="number",
                value=tok["value"],
                _paren_wrap=bool(tok.get("_paren_wrap")),
            ))
        else:
            raise ValueError(f"unknown token kind: {tok!r}")
    if not stack:
        return None
    if len(stack) > 1:
        raise ValueError(f"RPN did not reduce: {len(stack)} items left on stack")
    return stack[0]