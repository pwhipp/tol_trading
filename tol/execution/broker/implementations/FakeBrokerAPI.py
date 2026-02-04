from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from tol.exchange import resolve_exchange_currency
from tol.execution.broker.BrokerAPI import BrokerAPI, OrderStatus, OrderSubmission

IBKR_FAIL_REASONS = (
    "MARKET_CLOSED",
    "INSUFFICIENT_FUNDS",
    "INVALID_CONTRACT",
    "ORDER_REJECTED",
    "UNKNOWN",
)


class FakeBrokerState:
    def __init__(self, state_path: Path) -> None:
        self._state_path = Path(state_path)

    def load(self) -> dict[str, Any]:
        if not self._state_path.exists():
            state = self.default_state()
            self.save(state)
            return state
        with self._state_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if data is None:
            state = self.default_state()
            self.save(state)
            return state
        if not isinstance(data, dict):
            data = {}
        return self._normalize_state(data)

    def save(self, state: dict[str, Any]) -> None:
        with self._state_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(state, handle, sort_keys=False)

    @staticmethod
    def default_state() -> dict[str, Any]:
        return {
            "closed_markets": [],
            "prices": {},
            "portfolio": {"cash": {"USD": 1_000_000}, "positions": []},
            "orders": {},
        }

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        return str(symbol).strip().upper()

    @staticmethod
    def normalize_exchange(exchange: str) -> str:
        return str(exchange).strip().upper()

    @staticmethod
    def normalize_currency(currency: str) -> str:
        return str(currency).strip().upper()

    @staticmethod
    def split_symbol(symbol: str) -> tuple[str, str | None]:
        normalized = FakeBrokerState.normalize_symbol(symbol)
        if "." not in normalized:
            return normalized, None
        base, exchange = normalized.rsplit(".", 1)
        return base, exchange

    def is_market_closed(self, state: dict[str, Any], exchange: str | None) -> bool:
        closed_markets = state.get("closed_markets", [])
        if not exchange:
            return False
        exchange_code = self.normalize_exchange(exchange)
        closed = [self.normalize_exchange(item) for item in closed_markets]
        return exchange_code in closed or "GLOBAL" in closed

    def resolve_price(self, state: dict[str, Any], symbol: str) -> tuple[Decimal, str]:
        normalized = self.normalize_symbol(symbol)
        prices = state.get("prices", {})
        currency = None
        price_value = None
        if isinstance(prices, dict):
            entry = prices.get(normalized)
            if isinstance(entry, dict):
                price_value = entry.get("price")
                currency = entry.get("currency")
        if currency is None:
            _, exchange = self.split_symbol(normalized)
            currency = resolve_exchange_currency(exchange or "") or "USD"
        if price_value is None:
            return Decimal("100"), self.normalize_currency(currency)
        return Decimal(str(price_value)), self.normalize_currency(currency)

    def _normalize_state(self, data: dict[str, Any]) -> dict[str, Any]:
        state = dict(data)
        closed_markets = state.get("closed_markets")
        if closed_markets is None:
            closed_markets = []
        if not isinstance(closed_markets, list):
            closed_markets = []
        normalized_closed = []
        for exchange in closed_markets:
            if not exchange:
                continue
            normalized_closed.append(self.normalize_exchange(exchange))
        if "market" in state and not normalized_closed:
            market = state.get("market")
            if isinstance(market, dict) and market.get("open") is False:
                normalized_closed.append("GLOBAL")
        state["closed_markets"] = normalized_closed
        state.setdefault("prices", {})
        portfolio = state.get("portfolio")
        if not isinstance(portfolio, dict):
            portfolio = {}
        portfolio.setdefault("cash", {"USD": 1_000_000})
        portfolio.setdefault("positions", [])
        state["portfolio"] = portfolio
        state.setdefault("orders", {})
        return state


class FakeBrokerAPI(BrokerAPI):
    def __init__(self, state_path: Path) -> None:
        self._state = FakeBrokerState(state_path)

    def submit_order(self, order_spec: dict[str, Any]) -> OrderSubmission:
        state = self._state.load()
        orders = state.setdefault("orders", {})
        broker_order_id = self._next_order_id(orders.keys())
        symbol = FakeBrokerState.normalize_symbol(order_spec.get("symbol", ""))
        _, exchange = FakeBrokerState.split_symbol(symbol)
        is_closed = self._state.is_market_closed(state, exchange)
        status = "FAILED" if is_closed else "SUBMITTED"
        failure_reason = "MARKET_CLOSED" if is_closed else None
        trade_snapshot = _build_fake_trade_snapshot(
            order_spec,
            broker_order_id,
            status=status,
            failure_reason=failure_reason,
        )
        orders[broker_order_id] = {
            "status": status,
            "submitted_qty": float(order_spec["quantity"]),
            "filled_qty": 0.0,
            "trade": trade_snapshot,
            "average_price": None,
            "failure_reason": failure_reason,
        }
        self._state.save(state)
        return OrderSubmission(
            broker_order_id=broker_order_id,
            trade=trade_snapshot,
        )

    def cancel_order(self, broker_order_id: str) -> None:
        state = self._state.load()
        order = state.get("orders", {}).get(broker_order_id)
        if order is None:
            return
        order["status"] = "CANCELLED"
        self._state.save(state)

    def get_order_status(self, broker_order_id: str) -> OrderStatus:
        state = self._state.load()
        order = state.get("orders", {}).get(broker_order_id)
        if order is None:
            raise ValueError(f"Unknown broker order id {broker_order_id}")
        status = str(order.get("status", "SUBMITTED")).upper()
        filled_qty = Decimal(str(order.get("filled_qty", 0)))
        average_price = order.get("average_price")
        avg_price = None
        if average_price is not None:
            avg_price = Decimal(str(average_price))
        return OrderStatus(status=status, filled_qty=filled_qty, average_price=avg_price)

    def list_open_orders(self) -> Iterable[str]:
        state = self._state.load()
        open_orders = []
        for broker_order_id, order in state.get("orders", {}).items():
            status = str(order.get("status", "SUBMITTED")).upper()
            if status in {"SUBMITTED", "PARTIAL"}:
                open_orders.append(broker_order_id)
        return open_orders

    def get_portfolio_snapshot(self) -> dict[str, Any]:
        state = self._state.load()
        market_open = True
        if state.get("closed_markets"):
            open_orders = state.get("orders", {})
            market_open = not _has_closed_market_orders(open_orders, state)
        return {
            "market_open": market_open,
            "portfolio": state.get("portfolio", {}),
        }

    @staticmethod
    def _next_order_id(existing_ids: Iterable[str]) -> str:
        highest = 0
        for broker_order_id in existing_ids:
            if not isinstance(broker_order_id, str):
                continue
            if broker_order_id.startswith("FB-"):
                try:
                    value = int(broker_order_id.split("-", 1)[1])
                except ValueError:
                    continue
                highest = max(highest, value)
        return f"FB-{highest + 1}"


def _build_fake_trade_snapshot(
    order_spec: dict[str, Any],
    broker_order_id: str,
    status: str = "SUBMITTED",
    failure_reason: str | None = None,
) -> dict[str, Any]:
    quantity = Decimal(str(order_spec.get("quantity", 0)))
    snapshot = {
        "order_id": broker_order_id,
        "status": status,
        "filled_qty": 0.0,
        "avg_fill_price": None,
        "action_type": order_spec.get("action_type"),
        "symbol": order_spec.get("symbol"),
        "submitted_qty": float(quantity),
        "order_type": "MKT",
    }
    if failure_reason:
        snapshot["failure_reason"] = failure_reason
    return snapshot


def _has_closed_market_orders(
    orders: dict[str, Any],
    state: dict[str, Any],
) -> bool:
    closed_markets = state.get("closed_markets", [])
    if not closed_markets:
        return False
    normalized_closed = {
        FakeBrokerState.normalize_exchange(item) for item in closed_markets
    }
    for order in orders.values():
        status = str(order.get("status", "SUBMITTED")).upper()
        if status not in {"SUBMITTED", "PARTIAL"}:
            continue
        trade = order.get("trade", {})
        symbol = FakeBrokerState.normalize_symbol(trade.get("symbol", ""))
        _, exchange = FakeBrokerState.split_symbol(symbol)
        if exchange and (
            FakeBrokerState.normalize_exchange(exchange) in normalized_closed
            or "GLOBAL" in normalized_closed
        ):
            return True
    return False
