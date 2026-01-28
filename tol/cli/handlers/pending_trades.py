from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional


@dataclass(frozen=True)
class PendingTrade:
    symbol: str
    action_type: str
    quantity: Decimal
    status: str
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    order_type: Optional[str] = None
    order_id: Optional[int] = None


def normalize_pending_trades(
    raw_trades: Optional[Iterable[dict]],
) -> list[PendingTrade]:
    if not raw_trades:
        return []
    normalized: list[PendingTrade] = []
    for trade in raw_trades:
        if isinstance(trade, PendingTrade):
            normalized.append(trade)
            continue
        if not isinstance(trade, dict):
            continue
        symbol = str(trade.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        action_type = str(trade.get("action_type", "")).strip().lower()
        if action_type not in {"buy", "sell"}:
            continue
        quantity = _coerce_decimal(trade.get("quantity"))
        if quantity is None or quantity <= 0:
            continue
        status = str(trade.get("status", "")).strip() or "Unknown"
        price = _coerce_decimal(trade.get("price"))
        currency = str(trade.get("currency", "")).strip().upper() or None
        order_type = str(trade.get("order_type", "")).strip().upper() or None
        order_id = _coerce_int(trade.get("order_id"))
        normalized.append(
            PendingTrade(
                symbol=symbol,
                action_type=action_type,
                quantity=quantity,
                status=status,
                price=price,
                currency=currency,
                order_type=order_type,
                order_id=order_id,
            )
        )
    return normalized


def format_pending_trade(trade: PendingTrade) -> str:
    price = f"{trade.price:,.2f} " if trade.price is not None else ""
    currency = f"{trade.currency}" if trade.currency else ""
    order_type = f"{trade.order_type} " if trade.order_type else ""
    order_id = f" #{trade.order_id}" if trade.order_id is not None else ""
    details = " ".join(part for part in [order_type, price + currency] if part)
    if details:
        details = f", {details.strip()}"
    return (
        f"{trade.action_type.upper()} {trade.quantity} {trade.symbol} "
        f"({trade.status}{order_id}{details})"
    )


def _coerce_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _coerce_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
