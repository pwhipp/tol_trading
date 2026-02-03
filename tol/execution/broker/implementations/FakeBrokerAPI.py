from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from tol.execution.broker.BrokerAPI import BrokerAPI, OrderStatus


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
