"""Equation tokeniser + shunting-yard-to-RPN + RPN-to-tree.

All operator behavior comes from the ``operator`` table via
:mod:`scifind_lib.operators`; this module has no operator-specific branches.
"""

from dataclasses import dataclass, field
from typing import Optional

from scifind_lib.db import in_clause
from scifind_lib.operators import alias_to_id_map, load_operators


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


def _scan_word(equation, pos, length):
    """Scan an identifier at equation[pos]; return (word, alias, next_pos)."""
    j = pos
    while j < length and (equation[j].isalnum() or equation[j] == "_"):
        j += 1
    word = equation[pos:j]
    alias = None
    if j < length and equation[j] == "[":
        k = equation.find("]", j + 1)
        if k == -1:
            raise ValueError(f"unterminated alias for {word!r}")
        alias = equation[j + 1:k] or None
        j = k + 1
    return word, alias, j


def parse_equation(conn, equation):
    """Tokenize an infix equation string and convert to RPN token dicts."""
    operators = load_operators(conn)
    qty_ids = {r["id"] for r in conn.execute("SELECT id FROM quantity")}
    const_ids = {r["id"] for r in conn.execute("SELECT id FROM constant")}
    alias_to_id = alias_to_id_map(operators)
    max_match_width = max((len(s) for s in alias_to_id), default=1)

    if not equation or not equation.strip():
        return []

    pos, length = 0, len(equation)
    tokens = []
    expect_operand = True

    def emit_op(op_id):
        nonlocal expect_operand
        op = operators[op_id]
        if expect_operand and op.fixity == "postfix":
            raise ValueError(f"operator {op_id!r} needs a left operand")
        tokens.append({"token_kind": "operator", "operator_id": op_id})
        expect_operand = op.fixity != "postfix"

    while pos < length:
        char = equation[pos]
        if char.isspace():
            pos += 1
            continue
        if char.isdigit() or (char == "." and pos + 1 < length
                              and equation[pos + 1].isdigit()):
            tok, pos = _scan_number(equation, pos, length)
            tokens.append(tok)
            expect_operand = False
            continue
        if char.isalpha() or char == "_":
            # Whole-word match only, so quantities like `single` never split
            # into an operator prefix plus garbage.
            word, alias, pos = _scan_word(equation, pos, length)
            if (op_id := alias_to_id.get(word)) is not None:
                if alias is not None:
                    raise ValueError(f"operator {word} cannot have an alias")
                emit_op(op_id)
                continue
            kind = "quantity" if word in qty_ids else "constant" if word in const_ids else None
            if kind is None:
                raise ValueError(f"unknown identifier: {word!r}")
            tokens.append({"token_kind": kind, f"{kind}_id": word,
                           **({"label": alias} if alias else {})})
            expect_operand = False
            continue
        if char in "()":
            tokens.append({"token_kind": "paren", "paren": char})
            pos += 1
            expect_operand = char == "("
            continue
        op_id, op_len = None, 0
        for width in range(min(max_match_width, length - pos), 0, -1):
            if (op_id := alias_to_id.get(equation[pos:pos + width])) is not None:
                op_len = width
                break
        if op_id is None:
            raise ValueError(f"unexpected character: {char!r} at position {pos}")
        emit_op(op_id)
        pos += op_len

    return _infix_to_rpn(tokens, operators)


def _emit_op(stack, output):
    output.append({"token_kind": "operator", "operator_id": stack.pop()["id"]})


def _cascade_completed(stack, output, operators):
    """Credit one finished operand to enclosing prefix frames, emitting completed calls."""
    while stack and stack[-1]["kind"] == "op":
        top = stack[-1]
        top_op = operators[top["id"]]
        if top_op.fixity != "prefix":
            break
        top["nargs"] += 1
        if top["nargs"] < top_op.arity:
            break
        _emit_op(stack, output)


def _infix_to_rpn(tokens, operators):
    """Convert flat infix tokens to RPN (prefix/postfix/infix + relational chaining)."""
    output = []
    stack = []
    expect_operand = True

    for tok in tokens:
        kind = tok["token_kind"]
        if kind in ("number", "quantity", "constant"):
            output.append(tok)
            _cascade_completed(stack, output, operators)
            expect_operand = False
            continue
        if kind == "paren":
            if tok["paren"] == "(":
                stack.append({"kind": "paren", "out_len": len(output)})
                expect_operand = True
                continue
            while stack and stack[-1]["kind"] != "paren":
                _emit_op(stack, output)
            if not stack:
                raise ValueError("unmatched ')'")
            marker = stack.pop()
            if len(output) == marker["out_len"]:
                raise ValueError("empty parentheses")
            output[-1]["_paren_wrap"] = True
            _cascade_completed(stack, output, operators)
            expect_operand = False
            continue
        op_id = tok["operator_id"]
        op = operators.get(op_id)
        if op is None:
            raise ValueError(f"unknown operator: {op_id!r}")
        if op.fixity == "postfix":
            if expect_operand:
                raise ValueError(f"operator {op_id!r} needs a left operand")
            output.append({"token_kind": "operator", "operator_id": op_id})
            _cascade_completed(stack, output, operators)
            expect_operand = False
            continue
        if op.fixity == "prefix" or expect_operand:
            # Lenient binary push where an operand is expected, so prefix-led
            # expressions like `neg log 10 x` still parse; a genuinely missing
            # operand surfaces as RPN underflow at reduce time.
            stack.append({"kind": "op", "id": op_id, "nargs": 0})
            expect_operand = True
            continue
        while stack and stack[-1]["kind"] == "op":
            top = stack[-1]
            top_op = operators[top["id"]]
            ready = top_op.fixity == "prefix" and top["nargs"] >= top_op.arity
            higher = top_op.fixity != "prefix" and (
                top_op.precedence > op.precedence
                or (top_op.precedence == op.precedence and op.associativity == "left"))
            if not (ready or higher):
                if (top_op.fixity != "prefix" and top_op.precedence == op.precedence
                        and op.fixity == "relational" and top["id"] != op_id):
                    raise ValueError(
                        f"operator {op_id!r} is not associative; "
                        f"add parentheses to chain it")
                break
            _emit_op(stack, output)
        stack.append({"kind": "op", "id": op_id, "nargs": 1})
        expect_operand = True

    while stack:
        if stack[-1]["kind"] == "paren":
            raise ValueError("unmatched parenthesis")
        _emit_op(stack, output)

    return output


@dataclass
class FormulaNode:
    """A node in the parsed formula tree (operator nodes carry resolved display/dim data)."""
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
    fixity: str = "infix"
    latex_template: str = ""
    dim_spec: dict = field(default_factory=dict)
    placeholder: bool = False
    _paren_wrap: bool = False


def bulk_entity_rows(conn, table, columns, ids):
    """{id: row} for `ids` in a single query (empty input → {})."""
    if not (ids := set(ids)):
        return {}
    marks, params = in_clause(ids)
    rows = conn.execute(f"SELECT {columns} FROM {table} WHERE id IN ({marks})", params)
    return {r["id"]: dict(r) for r in rows}


def _leaf_node(kind, tok, row, wrap):
    """Quantity/constant leaf (blank-symbol quantities become placeholders)."""
    if kind == "quantity":
        return FormulaNode(
            kind="quantity", quantity_id=tok["quantity_id"], label=tok.get("label"),
            symbol_overwrite=tok.get("symbol_overwrite"), symbol=row.get("symbol"),
            placeholder=not (row.get("symbol") or tok.get("symbol_overwrite")
                             or tok.get("label")),
            _paren_wrap=wrap)
    return FormulaNode(kind="constant", constant_id=tok["constant_id"],
                       symbol=row["symbol"] or tok["constant_id"], _paren_wrap=wrap)


def _op_node(op, args, wrap):
    node = FormulaNode(kind="operator", children=list(args), operator_id=op.id,
                       symbol=op.symbol, arity=op.arity, precedence=op.precedence,
                       associativity=op.associativity, fixity=op.fixity,
                       latex_template=op.latex_template, dim_spec=dict(op.dim_spec),
                       _paren_wrap=wrap)
    if (op.fixity == "relational" and args and args[-1].kind == "operator"
            and args[-1].operator_id == op.id):
        inner = args[-1]
        node.children = args[:-1] + list(inner.children)
        node.arity = len(node.children)
        node._paren_wrap = inner._paren_wrap
    return node


def reduce_rpn_to_tree(conn, tokens):
    """Reduce a token stream to an expression tree (relational chains fold n-ary)."""
    operators = load_operators(conn)
    qty_map = bulk_entity_rows(conn, "quantity", "id, name, symbol",
                               {t["quantity_id"] for t in tokens if t["token_kind"] == "quantity"})
    const_map = bulk_entity_rows(conn, "constant", "id, symbol",
                                 {t["constant_id"] for t in tokens if t["token_kind"] == "constant"})
    stack = []
    for tok in tokens:
        kind = tok["token_kind"]
        wrap = bool(tok.get("_paren_wrap"))
        if kind == "operator":
            op = operators.get(tok["operator_id"])
            if op is None:
                raise ValueError(f"unknown operator: {tok['operator_id']!r}")
            if len(stack) < op.arity:
                raise ValueError(
                    f"RPN underflow at {tok['operator_id']}: need {op.arity}, "
                    f"have {len(stack)}")
            stack.append(_op_node(op, [stack.pop() for _ in range(op.arity)][::-1], wrap))
        elif kind in ("quantity", "constant"):
            key = "quantity_id" if kind == "quantity" else "constant_id"
            row = (qty_map if kind == "quantity" else const_map).get(tok[key])
            if row is None:
                raise ValueError(f"unknown {kind}: {tok[key]!r}")
            stack.append(_leaf_node(kind, tok, row, wrap))
        elif kind == "number":
            stack.append(FormulaNode(kind="number", value=tok["value"], _paren_wrap=wrap))
        else:
            raise ValueError(f"unknown token kind: {tok!r}")
    if not stack:
        return None
    if len(stack) > 1:
        raise ValueError(f"RPN did not reduce: {len(stack)} items left on stack")
    return stack[0]
