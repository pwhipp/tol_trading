from __future__ import annotations

from pathlib import Path
from typing import Any

import json


def load_tol(path: Path) -> dict[str, Any]:
    tol_doc = _read_tol_file(path)

    if not tol_doc:
        return {}

    actions = tol_doc.get("actions")
    if isinstance(actions, list):
        tol_doc["actions"] = [_normalize_action(action) for action in actions]

    return tol_doc


def _normalize_action(action: dict[str, Any]) -> dict[str, Any]:
    if len(action) != 1:
        raise ValueError("action must be a dict with a single key specifying buy/sell/target")

    action_type, body = next(iter(action.items()))
    if not isinstance(body, dict):
        return action

    if "quantity" in body:
        body = dict(body)
        body["quantity"] = _normalize_quantity(body["quantity"])

    return {action_type: body}


def _normalize_quantity(value: Any) -> Any:
    if value is None:
        return value
    if isinstance(value, bool):
        raise ValueError("Quantity must be numeric or string, not boolean.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value > 1.0:
            raise ValueError("Float quantity must be <= 1.0 for percentage values.")
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("Quantity string cannot be empty.")
        upper = raw.upper()
        if upper == "ALL":
            return 1.0
        if upper.endswith("%"):
            number = upper[:-1].strip()
            if not number:
                raise ValueError("Percent quantity is missing a value.")
            percent = float(number) / 100.0
            if percent > 1.0:
                raise ValueError("Percent quantity must be <= 100%.")
            return percent
        try:
            return int(upper)
        except ValueError as exc:
            raise ValueError(
                f"Quantity string must be ALL, percent, or integer: {value}"
            ) from exc
    return value


def _read_tol_file(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError:
        yaml = None

    with path.open("r", encoding="utf-8") as file_handle:
        if yaml is not None:
            return yaml.safe_load(file_handle)
        return json.load(file_handle)
