from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache
def load_exchange_currencies() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "EXCHANGE_CURRENCIES.yaml"
    data: dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    exchanges = data.get("exchanges", {}) if isinstance(data, dict) else {}
    if not isinstance(exchanges, dict):
        return {}
    normalized: dict[str, str] = {}
    for exchange, currency in exchanges.items():
        if not exchange or not currency:
            continue
        normalized[str(exchange).strip().upper()] = str(currency).strip().upper()
    return normalized


def resolve_exchange_currency(exchange: str) -> str | None:
    if not exchange:
        return None
    currencies = load_exchange_currencies()
    return currencies.get(exchange.strip().upper())
