from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple, Set


@dataclass(frozen=True)
class ParsedQuantity:
    kind: str
    value: Decimal | None = None

    def __str__(self) -> str:
        if self.kind == "all":
            return "ALL"
        if self.kind == "percent":
            return f"{self.value}%"
        return f"{self.value}"


@dataclass
class PlannedAction:
    index: int
    action_type: str
    symbol: str
    quantity: Optional[ParsedQuantity] = None
    percent: Optional[Decimal] = None
    using: List[str] = None
    using_classified: List[Tuple[str, str]] = None
    derived_id: str = ""
    depends_on: List[str] = None


def derive_action_id(action_type: str, symbol: str) -> str:
    return f"{action_type}{symbol.upper()}"


def parse_percent(value) -> Optional[Decimal]:
    if value is None:
        return None

    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))

    if isinstance(value, str):
        stripped = value.strip()
        if stripped.endswith("%"):
            stripped = stripped[:-1].strip()
        if not stripped:
            raise ValueError("Percent cannot be empty")
        try:
            return Decimal(stripped)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid percent value: {value}") from exc

    raise ValueError(f"Unsupported percent value type: {type(value)}")


def parse_quantity(value) -> Optional[ParsedQuantity]:
    if value is None:
        return None

    if isinstance(value, (int, float, Decimal)):
        return ParsedQuantity(kind="shares", value=Decimal(str(value)))

    if isinstance(value, str):
        stripped = value.strip().upper()
        if stripped == "ALL":
            return ParsedQuantity(kind="all")
        if stripped.endswith("%"):
            stripped = stripped[:-1].strip()
            if not stripped:
                raise ValueError("Quantity percent cannot be empty")
            try:
                return ParsedQuantity(kind="percent", value=Decimal(stripped))
            except InvalidOperation as exc:
                raise ValueError(f"Invalid percent quantity: {value}") from exc
        try:
            return ParsedQuantity(kind="shares", value=Decimal(stripped))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid quantity value: {value}") from exc

    raise ValueError(f"Unsupported quantity value type: {type(value)}")


def plan_actions(tol_doc: dict) -> List[PlannedAction]:
    actions = []
    seen_ids = {}

    for idx, action_entry in enumerate(tol_doc.get("actions", [])):
        if len(action_entry) != 1:
            raise ValueError(f"Action at index {idx} must have exactly one action type")

        action_type, body = next(iter(action_entry.items()))
        symbol = body.get("symbol")

        if not symbol:
            raise ValueError(f"{action_type} action at index {idx} missing symbol")

        derived_id = derive_action_id(action_type, symbol)

        # Disambiguate duplicates deterministically
        if derived_id in seen_ids:
            count = seen_ids[derived_id] + 1
            seen_ids[derived_id] = count
            derived_id = f"{derived_id}_{count}"
        else:
            seen_ids[derived_id] = 0

        using = body.get("using")
        if not using:
            using = ["CASH"]

        action = PlannedAction(
            index=idx,
            action_type=action_type,
            symbol=symbol,
            quantity=parse_quantity(body.get("quantity")),
            percent=parse_percent(body.get("percent")),
            using=using,
            derived_id=derived_id,
            depends_on=[]
        )

        actions.append(action)

    id_map = {a.derived_id: a for a in actions}
    action_ids = set(id_map.keys())

    for action in actions:
        action.using_classified = []
        for source in action.using:
            source_type = classify_source(source, action_ids)
            action.using_classified.append((source, source_type))

            if source_type == "action":
                action.depends_on.append(source)
            elif source_type in ("cash", "holding"):
                continue
            else:
                raise ValueError(
                    f"Action {action.derived_id} references unknown source '{source}'"
                )

    return actions


def is_action_reference(source, id_map):
    return source in id_map


def is_cash(source):
    return source == "CASH"


def is_holding(source):
    return source.isalpha() and source.isupper()


def classify_source(source: str, action_ids: Set[str]) -> str:
    if source == "CASH":
        return "cash"
    if source in action_ids:
        return "action"
    if source.isalpha() and source.isupper():
        return "holding"
    return "unknown"
