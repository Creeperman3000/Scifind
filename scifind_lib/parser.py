"""Equation tokeniser + shunting-yard-to-RPN + RPN-to-tree (no operator-specific branches)."""

from dataclasses import dataclass, field
from typing import Optional

from scifind_lib.db import keyed_rows
from scifind_lib.operators import alias_to_id_map, load_operators


def quantity_token_key(quantity_id, label, pos):
    """Stable key linking a quantity token to its per-occurrence overrides."""
    return f"{quantity_id}|{label or ''}|{pos}"


def check_equation_length(equation, max_length):
    """Return (equation, error) enforcing a max length (shared web/CLI rule)."""
    if len(equation or "") > max_length:
        return None, f"equation exceeds {max_length} characters"
    return equation, None


def parse_bracket_keys(pairs, prefix, nparts, fields=None):
    """Parse ``prefix[a][b]...`` keys; blanks omitted, last non-blank wins."""
    parsed, pre = {}, prefix + "["
    for key, values in pairs:
        if not key.startswith(pre) or not key.endswith("]"):
            continue
        parts = key[len(pre):-1].split("][")
        if len(parts) != nparts or (fields and parts[-1] not in fields):
            continue
        value = next((v for v in reversed(values) if v and v.strip()), "")
        if not value:
            continue
        node = parsed
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value.strip()
    return parsed


def _scan_number(equation, pos, length):
    """Scan a float literal at equation[pos]; return (token, next_pos)."""
    j, seen_dot, seen_exp = pos, False, False
    while j < length:
        c = equation[j]
        if c.isdigit():
            j += 1
        elif c == "." and not (seen_dot or seen_exp):
            seen_dot, j = True, j + 1
        elif c in "eE" and not seen_exp:
            seen_exp, j = True, j + 1
            if j < length and equation[j] in "+-":
                j += 1
        else:
            break
    try:
        value = float(equation[pos:j])
    except ValueError as e:
        raise ValueError(f"bad number: {equation[pos:j]!r}") from e
    return {"token_kind": "number", "value": value}, j


def _scan_word(equation, pos, length):
    """Scan an identifier at equation[pos]; return (word, alias, next_pos)."""
    j = pos
    while j < length and (equation[j].isalnum() or equation[j] == "_"):
        j += 1
    word, alias = equation[pos:j], None
    if j < length and equation[j] == "[":
        k = equation.find("]", j + 1)
        if k == -1:
            raise ValueError(f"unterminated alias for {word!r}")
        alias, j = equation[j + 1:k] or None, k + 1
    return word, alias, j


def parse_equation(conn, equation):
    """Tokenize an infix equation string and convert to RPN token dicts."""
    operators = load_operators(conn)
    qty_ids = {r["id"] for r in conn.execute("SELECT id FROM quantity")}
    const_ids = {r["id"] for r in conn.execute("SELECT id FROM constant")}
    alias_to_id = alias_to_id_map(operators)
    max_width = max((len(s) for s in alias_to_id), default=1)
    if not (equation or "").strip():
        return []
    pos, length, tokens, expect_operand = 0, len(equation), [], True

    def emit_op(op_id):
        nonlocal expect_operand
        if expect_operand and operators[op_id].fixity == "postfix":
            raise ValueError(f"operator {op_id!r} needs a left operand")
        tokens.append({"token_kind": "operator", "operator_id": op_id})
        expect_operand = operators[op_id].fixity != "postfix"

    while pos < length:
        char = equation[pos]
        if char.isspace():
            pos += 1
            continue
        if char.isdigit() or (char == "." and equation[pos + 1:pos + 2].isdigit()):
            tok, pos = _scan_number(equation, pos, length)
            tokens.append(tok)
            expect_operand = False
            continue
        if char.isalpha() or char == "_":
            # Whole-word match only, so `single` never splits into op prefix + garbage.
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
            pos, expect_operand = pos + 1, char == "("
            continue
        for width in range(min(max_width, length - pos), 0, -1):
            if equation[pos:pos + width] in alias_to_id:
                emit_op(alias_to_id[equation[pos:pos + width]])
                pos += width
                break
        else:
            raise ValueError(f"unexpected character: {char!r} at position {pos}")
    return _infix_to_rpn(tokens, operators)


def _emit_op(stack, output):
    output.append({"token_kind": "operator", "operator_id": stack.pop()["id"]})


def _cascade_completed(stack, output, operators):
    """Credit one finished operand to enclosing prefix frames, emitting completed calls."""
    while stack and stack[-1]["kind"] == "op" and (op := operators[stack[-1]["id"]]).fixity == "prefix":
        stack[-1]["nargs"] += 1
        if stack[-1]["nargs"] < op.arity:
            break
        _emit_op(stack, output)


def _infix_to_rpn(tokens, operators):
    """Convert flat infix tokens to RPN (prefix/postfix/infix + relational chaining)."""
    output, stack, expect_operand = [], [], True

    def done(tok=None):
        nonlocal expect_operand
        if tok is not None:
            output.append(tok)
        _cascade_completed(stack, output, operators)
        expect_operand = False

    for tok in tokens:
        kind = tok["token_kind"]
        if kind in ("number", "quantity", "constant"):
            done(tok)
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
            if len(output) == stack.pop()["out_len"]:
                raise ValueError("empty parentheses")
            done()
            continue
        op_id = tok["operator_id"]
        if (op := operators.get(op_id)) is None:
            raise ValueError(f"unknown operator: {op_id!r}")
        if op.fixity == "postfix":
            if expect_operand:
                raise ValueError(f"operator {op_id!r} needs a left operand")
            done({"token_kind": "operator", "operator_id": op_id})
            continue
        if op.fixity == "prefix":
            stack.append({"kind": "op", "id": op_id, "nargs": 0})
            expect_operand = True
            continue
        if expect_operand:
            raise ValueError(f"operator {op_id!r} needs a left operand; use 'drop {op_id} ...' for a blank slot")
        while stack and stack[-1]["kind"] == "op":
            top, top_op = stack[-1], operators[stack[-1]["id"]]
            if top_op.fixity == "prefix":
                if top["nargs"] < top_op.arity:
                    break
            elif (top_op.precedence > op.precedence or (top_op.precedence == op.precedence
                                                        and op.associativity == "left")):
                pass
            else:
                if (top_op.precedence == op.precedence and op.fixity == "relational"
                        and top["id"] != op_id):
                    raise ValueError(f"operator {op_id!r} is not associative; "
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
    quantity_id: Optional[str] = None; constant_id: Optional[str] = None
    value: Optional[float] = None; label: Optional[str] = None
    symbol_overwrite: Optional[str] = None; operator_id: Optional[str] = None
    symbol: Optional[str] = None; arity: int = 0
    precedence: int = 0; associativity: str = "left"; fixity: str = "infix"
    latex_template: str = ""; dim_spec: dict = field(default_factory=dict)
    placeholder: bool = False


def bulk_entity_rows(conn, table, columns, ids):
    """{id: row} for `ids` in a single query (empty input → {})."""
    return keyed_rows(conn, f"SELECT {columns} FROM {table} WHERE id IN ({{}})", set(ids))


def _leaf_node(kind, tok, row):
    """Quantity/constant leaf (blank-symbol quantities become placeholders)."""
    if kind == "quantity":
        blank = not (row.get("symbol") or tok.get("symbol_overwrite") or tok.get("label"))
        return FormulaNode(kind="quantity", quantity_id=tok["quantity_id"], label=tok.get("label"),
                           symbol_overwrite=tok.get("symbol_overwrite"), symbol=row.get("symbol"),
                           placeholder=blank)
    return FormulaNode(kind="constant", constant_id=tok["constant_id"],
                       symbol=row["symbol"] or tok["constant_id"])


def _op_node(op, args):
    node = FormulaNode(kind="operator", children=list(args), operator_id=op.id,
                       symbol=op.symbol, arity=op.arity, precedence=op.precedence,
                       associativity=op.associativity, fixity=op.fixity,
                       latex_template=op.latex_template, dim_spec=dict(op.dim_spec))
    if op.fixity == "relational" and args and args[-1].kind == "operator" and args[-1].operator_id == op.id:
        node.children = [*args[:-1], *args[-1].children]
        node.arity = len(node.children)
    return node


def reduce_rpn_to_tree_preloaded(tokens, operators, qty_map, const_map):
    """Reduce tokens using preloaded operator/entity maps (no DB queries)."""
    maps = {"quantity": qty_map, "constant": const_map}
    stack = []
    for tok in tokens:
        kind = tok["token_kind"]
        if kind == "operator":
            op = operators.get(tok["operator_id"])
            if op is None:
                raise ValueError(f"unknown operator: {tok['operator_id']!r}")
            if len(stack) < op.arity:
                raise ValueError(f"RPN underflow at {tok['operator_id']}: need {op.arity}, have {len(stack)}")
            args, stack = stack[len(stack) - op.arity:], stack[:len(stack) - op.arity]
            stack.append(_op_node(op, args))
        elif kind == "number":
            stack.append(FormulaNode(kind="number", value=tok["value"]))
        elif kind in maps:
            row = maps[kind].get(tok[f"{kind}_id"])
            if row is None:
                raise ValueError(f"unknown {kind}: {tok[f'{kind}_id']!r}")
            stack.append(_leaf_node(kind, tok, row))
        else:
            raise ValueError(f"unknown token kind: {tok!r}")
    if not stack:
        return None
    if len(stack) > 1:
        raise ValueError(f"RPN did not reduce: {len(stack)} items left on stack")
    return stack[0]


def reduce_rpn_to_tree(conn, tokens):
    """Reduce a token stream to an expression tree (relational chains fold n-ary)."""
    return reduce_rpn_to_tree_preloaded(
        tokens, load_operators(conn),
        bulk_entity_rows(conn, "quantity", "id, name, symbol",
                          (t["quantity_id"] for t in tokens if t["token_kind"] == "quantity")),
        bulk_entity_rows(conn, "constant", "id, symbol",
                          (t["constant_id"] for t in tokens if t["token_kind"] == "constant")))
