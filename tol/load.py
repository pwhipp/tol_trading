from __future__ import annotations

from pathlib import Path
from typing import Any

import json


def load_tol(path: Path) -> dict[str, Any]:
    tol_doc = _read_tol_file(path)
    return normalize_tol_document(tol_doc)


def load_tol_text(text: str) -> dict[str, Any]:
    tol_doc = _read_tol_text(text)
    return normalize_tol_document(tol_doc)


def normalize_tol_document(tol_doc: dict[str, Any] | None) -> dict[str, Any]:
    if not tol_doc:
        return {}

    actions = tol_doc.get("actions")
    if isinstance(actions, list):
        tol_doc["actions"] = [_normalize_action(action) for action in actions]

    return tol_doc


def dump_tol(tol_doc: dict[str, Any]) -> str:
    try:
        import yaml
    except ModuleNotFoundError:
        yaml = None

    if yaml is not None:
        return yaml.safe_dump(
            tol_doc,
            sort_keys=False,
            default_flow_style=False,
        )
    return json.dumps(tol_doc, indent=2)


def _normalize_action(action: dict[str, Any]) -> dict[str, Any]:
    if len(action) != 1:
        return action

    action_type, body = next(iter(action.items()))
    if not isinstance(body, dict):
        return action

    if "quantity" in body or "percent" in body:
        body = dict(body)
        if "quantity" in body:
            body["quantity"] = _normalize_quantity(body["quantity"])
        if "percent" in body:
            body["percent"] = _normalize_percent(body["percent"])
    if "using" in body:
        body = dict(body)
        body["using"] = _normalize_using(body["using"])

    return {action_type: body}


def _normalize_using(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_using_source(item) for item in value]
    if isinstance(value, str):
        return _normalize_using_source(value)
    return value


def _normalize_using_source(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    lowered = normalized.lower()
    prefixes = ("proceeds from ", "proceeds of ")
    for prefix in prefixes:
        if lowered.startswith(prefix):
            symbol = normalized[len(prefix):].strip().upper()
            if symbol:
                return f"sell{symbol}"
    return normalized


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
        if value <= 0:
            raise ValueError("Float quantity must be greater than 0.")
        if value == 1.0:
            return "ALL"
        return _format_percent(value * 100)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("Quantity string cannot be empty.")
        upper = raw.upper()
        if upper == "ALL":
            return "ALL"
        if raw.startswith("$"):
            normalized_money = _normalize_money_string(raw)
            if normalized_money is not None:
                return normalized_money
        if upper.endswith("%"):
            number = upper[:-1].strip()
            if not number:
                raise ValueError("Percent quantity is missing a value.")
            percent_value = float(number)
            if percent_value > 100:
                raise ValueError("Percent quantity must be <= 100%.")
            if percent_value <= 0:
                raise ValueError("Percent quantity must be greater than 0%.")
            if percent_value == 100:
                return "ALL"
            return _format_percent(percent_value)
        try:
            return int(upper)
        except ValueError as exc:
            raise ValueError(
                f"Quantity string must be ALL, percent, or integer: {value}"
            ) from exc
    return value


def _normalize_percent(value: Any) -> Any:
    if value is None:
        return value
    if isinstance(value, bool):
        raise ValueError("Percent must be numeric or string, not boolean.")
    if isinstance(value, (int, float)):
        percent = float(value)
        if percent > 100:
            raise ValueError("Percent must be <= 100.")
        if percent <= 0:
            raise ValueError("Percent must be greater than 0.")
        return _format_percent(percent)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("Percent string cannot be empty.")
        upper = raw.upper()
        if upper.endswith("%"):
            number = upper[:-1].strip()
            if not number:
                raise ValueError("Percent string is missing a value.")
            percent = float(number)
            if percent > 100:
                raise ValueError("Percent must be <= 100.")
            if percent <= 0:
                raise ValueError("Percent must be greater than 0.")
            return _format_percent(percent)
        try:
            percent = float(upper)
            if percent > 100:
                raise ValueError("Percent must be <= 100.")
            if percent <= 0:
                raise ValueError("Percent must be greater than 0.")
            return _format_percent(percent)
        except ValueError as exc:
            raise ValueError(
                f"Percent string must be numeric or percent: {value}"
            ) from exc
    return value


def _normalize_money_string(value: str) -> str | None:
    stripped = value.strip()
    if not stripped.startswith("$"):
        return None
    amount_text = stripped[1:].strip()
    if not amount_text:
        raise ValueError("Monetary quantity is missing a value.")
    try:
        amount = float(amount_text.replace(",", ""))
    except ValueError as exc:
        raise ValueError(
            f"Monetary quantity must be numeric: {value}"
        ) from exc
    if amount <= 0:
        raise ValueError("Monetary quantity must be greater than 0.")
    normalized = f"{amount:.2f}".rstrip("0").rstrip(".")
    return f"${normalized}"


def _format_percent(value: float) -> str:
    formatted = f"{value:.4f}".rstrip("0").rstrip(".")
    return f"{formatted}%"


def _read_tol_file(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError:
        yaml = None

    with path.open("r", encoding="utf-8") as file_handle:
        if yaml is not None:
            return yaml.safe_load(file_handle)
        return json.load(file_handle)


def _read_tol_text(text: str) -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError:
        yaml = None

    if yaml is not None:
        return yaml.safe_load(text)
    return json.loads(text)
