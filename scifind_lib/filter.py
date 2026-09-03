"""Parse query-string filter state for the list pages."""

from dataclasses import dataclass, field

from scifind_lib.dimensions import DIMENSION_OPS, dimension_symbols


MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 10


@dataclass
class QuantityFilter:
    ids: list = field(default_factory=list)
    ids_provided: bool = False
    exclude_all: bool = False
    quantity_ids: list = field(default_factory=list)
    quantity_mode: str = "and"
    diff_min: int = MIN_DIFFICULTY
    diff_max: int = MAX_DIFFICULTY
    dimension_filter: dict = field(default_factory=dict)
    dim_mode: str = "and"
    base_quantity_only: int = 0

    @property
    def has_dimension_filter(self) -> bool:
        return any(d.get("val") is not None for d in self.dimension_filter.values())


def parse_int_with_default(value, default=None):
    if not value:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_csv_string(value):
    """Split a comma-separated query value into a list of stripped non-empty parts."""
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_filter_state(args):
    """Parse query-string args into a QuantityFilter for the list pages."""
    mode_switched_raw = args.get("mode_switched", "")
    mode_switched = set(parse_csv_string(mode_switched_raw)) if mode_switched_raw else set()
    if mode_switched:
        dim_mode = "or" if "dim" in mode_switched else "and"
        quantity_mode = "or" if "fml" in mode_switched else "and"
    else:
        dim_mode = args.get("dim_mode", "and")
        if dim_mode not in ("and", "or"):
            dim_mode = "and"
        quantity_mode = args.get("qty_mode", "and")
        if quantity_mode not in ("and", "or"):
            quantity_mode = "and"

    dimension_filter = {}
    for symbol in dimension_symbols():
        dimension_filter[symbol] = {"op": "eq", "val": None}
        for op in DIMENSION_OPS:
            v = parse_int_with_default(args.get(f"{symbol}_{op}"))
            if v is not None:
                dimension_filter[symbol] = {"op": op, "val": v}
                break

    ids_raw = args.get("ids")
    return QuantityFilter(
        ids=parse_csv_string(ids_raw) if ids_raw is not None else [],
        ids_provided=ids_raw is not None,
        exclude_all=args.get("exclude_all") == "1",
        quantity_ids=parse_csv_string(args.get("qty", "")),
        quantity_mode=quantity_mode,
        diff_min=parse_int_with_default(args.get("diff_min"), MIN_DIFFICULTY),
        diff_max=parse_int_with_default(args.get("diff_max"), MAX_DIFFICULTY),
        dimension_filter=dimension_filter,
        dim_mode=dim_mode,
        base_quantity_only=parse_int_with_default(args.get("is_dim"), 0) or 0,
    )