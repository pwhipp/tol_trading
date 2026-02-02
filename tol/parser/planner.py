from dataclasses import dataclass
import re
from typing import List, Optional, Set, Tuple


@dataclass
class PlannedAction:
    index: int
    action_type: str
    symbol: str
    quantity: Optional[str] = None
    percent: Optional[float] = None
    using: List[str] = None
    using_classified: List[Tuple[str, str]] = None
    derived_id: str = ""
    depends_on: List[str] = None
    amount: Optional[str] = None
    to: Optional[str] = None


def derive_action_id(action_type: str, symbol: str) -> str:
    return f"{action_type}{symbol.upper()}"


def plan_actions(tol_doc: dict) -> List[PlannedAction]:
    actions = []
    seen_ids = {}

    for idx, action_entry in enumerate(tol_doc.get("actions", [])):
        if len(action_entry) != 1:
            raise ValueError(f"Action at index {idx} must have exactly one action type")

        action_type, body = next(iter(action_entry.items()))
        symbol = body.get("symbol")
        if action_type == "convert":
            symbol = body.get("to")

        if not symbol:
            raise ValueError(f"{action_type} action at index {idx} missing symbol")

        if action_type == "convert":
            derived_id = f"convert{idx + 1}"
        else:
            derived_id = derive_action_id(action_type, symbol)

        # Disambiguate duplicates deterministically
        if derived_id in seen_ids:
            count = seen_ids[derived_id] + 1
            seen_ids[derived_id] = count
            derived_id = f"{derived_id}_{count}"
        else:
            seen_ids[derived_id] = 0

        using = body.get("using")
        if action_type in {"buy", "target"} and not using:
            using = [f"CASH ({_default_currency(tol_doc)})"]
        elif using is None:
            using = []
        if action_type == "convert":
            using = []

        action = PlannedAction(
            index=idx,
            action_type=action_type,
            symbol=symbol,
            quantity=body.get("quantity"),
            percent=body.get("percent"),
            using=using,
            derived_id=derived_id,
            depends_on=[],
            amount=body.get("amount"),
            to=body.get("to"),
        )

        actions.append(action)

    id_map = {a.derived_id: a for a in actions if a.action_type != "convert"}
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


def _default_currency(tol_doc: dict) -> str:
    candidates = [
        tol_doc.get("default_currency"),
        tol_doc.get("settings", {}).get("default_currency")
        if isinstance(tol_doc.get("settings"), dict)
        else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().upper()
    return "USD"


def is_action_reference(source, id_map):
    return source in id_map


def is_cash(source):
    return bool(_CASH_PATTERN.fullmatch(source))


def is_holding(source):
    return bool(_HOLDING_PATTERN.fullmatch(source))


def classify_source(source: str, action_ids: Set[str]) -> str:
    if _CASH_PATTERN.fullmatch(source):
        return "cash"
    if source in action_ids:
        return "action"
    if _HOLDING_PATTERN.fullmatch(source):
        return "holding"
    return "unknown"


_CASH_PATTERN = re.compile(r"CASH \([A-Z]{3}\)$")
_HOLDING_PATTERN = re.compile(r"[A-Z0-9]+\.[A-Z0-9_]+$")
