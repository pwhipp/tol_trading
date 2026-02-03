from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from ib_insync import MarketOrder

from tol.ibkr.gateway import IBKRGateway


@dataclass(frozen=True)
class OrderStatus:
    status: str
    filled_qty: Decimal
    average_price: Decimal | None = None


class BrokerAPI(ABC):
    @abstractmethod
    def submit_order(self, order_spec: dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_order_status(self, broker_order_id: str) -> OrderStatus:
        raise NotImplementedError

    @abstractmethod
    def list_open_orders(self) -> Iterable[str]:
        raise NotImplementedError

    @abstractmethod
    def get_portfolio_snapshot(self) -> dict[str, Any]:
        raise NotImplementedError


class IBKRBrokerAPI(BrokerAPI):
    def __init__(self, mode: str) -> None:
        self._mode = mode

    def submit_order(self, order_spec: dict[str, Any]) -> str:
        gateway = IBKRGateway(self._mode)
        gateway.connect()
        try:
            contract = gateway.qualify_stock_contract(order_spec["symbol"])
            if contract is None:
                symbol = order_spec["symbol"]
                raise ValueError(f"Unable to qualify contract for {symbol}")
            action_type = order_spec["action_type"]
            quantity = Decimal(str(order_spec["quantity"]))
            side = "BUY" if action_type == "buy" else "SELL"
            order = MarketOrder(side, float(quantity))
            trade = gateway.ib.placeOrder(contract, order)
            broker_order_id = str(trade.order.orderId)
            return broker_order_id
        finally:
            gateway.disconnect()

    def cancel_order(self, broker_order_id: str) -> None:
        gateway = IBKRGateway(self._mode)
        gateway.connect()
        try:
            gateway.ib.cancelOrder(int(broker_order_id))
        finally:
            gateway.disconnect()

    def get_order_status(self, broker_order_id: str) -> OrderStatus:
        gateway = IBKRGateway(self._mode)
        gateway.connect()
        try:
            gateway.ib.reqAllOpenOrders()
            gateway.ib.sleep(1)
            for trade in gateway.ib.openTrades():
                order = getattr(trade, "order", None)
                if order and str(getattr(order, "orderId", "")) == broker_order_id:
                    status = getattr(trade.orderStatus, "status", "Submitted").upper()
                    filled = Decimal(str(getattr(trade.orderStatus, "filled", 0)))
                    avg_price = getattr(trade.orderStatus, "avgFillPrice", None)
                    avg_price_decimal = None
                    if avg_price is not None:
                        avg_price_decimal = Decimal(str(avg_price))
                    normalized = _normalize_ibkr_status(status)
                    return OrderStatus(
                        status=normalized,
                        filled_qty=filled,
                        average_price=avg_price_decimal,
                    )
            return OrderStatus(status="SUBMITTED", filled_qty=Decimal("0"))
        finally:
            gateway.disconnect()

    def list_open_orders(self) -> Iterable[str]:
        gateway = IBKRGateway(self._mode)
        gateway.connect()
        try:
            gateway.ib.reqAllOpenOrders()
            gateway.ib.sleep(1)
            open_orders = []
            for trade in gateway.ib.openTrades():
                order = getattr(trade, "order", None)
                if order:
                    open_orders.append(str(getattr(order, "orderId", "")))
            return open_orders
        finally:
            gateway.disconnect()

    def get_portfolio_snapshot(self) -> dict[str, Any]:
        gateway = IBKRGateway(self._mode)
        gateway.connect()
        try:
            cash = gateway.get_cash_by_currency()
            positions = gateway.get_positions()
            return {
                "market_open": None,
                "cash": {currency: float(value) for currency, value in cash.items()},
                "positions": positions,
            }
        finally:
            gateway.disconnect()


class FakeBrokerAPI(BrokerAPI):
    def __init__(self, state_path: Path) -> None:
        self._state_path = Path(state_path)

    def submit_order(self, order_spec: dict[str, Any]) -> str:
        state = self._load_state()
        orders = state.setdefault("orders", {})
        broker_order_id = self._next_order_id(orders.keys())
        orders[broker_order_id] = {
            "status": "SUBMITTED",
            "submitted_qty": float(order_spec["quantity"]),
            "filled_qty": 0.0,
        }
        self._save_state(state)
        return broker_order_id

    def cancel_order(self, broker_order_id: str) -> None:
        state = self._load_state()
        order = state.get("orders", {}).get(broker_order_id)
        if order is None:
            return
        order["status"] = "CANCELLED"
        self._save_state(state)

    def get_order_status(self, broker_order_id: str) -> OrderStatus:
        state = self._load_state()
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
        state = self._load_state()
        open_orders = []
        for broker_order_id, order in state.get("orders", {}).items():
            status = str(order.get("status", "SUBMITTED")).upper()
            if status in {"SUBMITTED", "PARTIAL"}:
                open_orders.append(broker_order_id)
        return open_orders

    def get_portfolio_snapshot(self) -> dict[str, Any]:
        state = self._load_state()
        market_open = None
        market = state.get("market")
        if isinstance(market, dict):
            market_open = market.get("open")
        return {
            "market_open": market_open,
            "portfolio": state.get("portfolio", {}),
        }

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {}
        with self._state_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return data or {}

    def _save_state(self, state: dict[str, Any]) -> None:
        with self._state_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(state, handle, sort_keys=False)

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


def _normalize_ibkr_status(status: str) -> str:
    normalized = status.strip().upper()
    if normalized in {"FILLED", "FILLED."}:
        return "FILLED"
    if normalized in {"CANCELLED", "API CANCELED", "CANCELED"}:
        return "CANCELLED"
    if normalized in {"SUBMITTED", "PRESUBMITTED"}:
        return "SUBMITTED"
    if normalized in {"PARTIAL", "PARTIALLYFILLED", "PARTIALLY FILLED"}:
        return "PARTIAL"
    if normalized in {"EXPIRED"}:
        return "EXPIRED"
    if normalized in {"INACTIVE", "PENDINGCANCEL"}:
        return "FAILED"
    return normalized
