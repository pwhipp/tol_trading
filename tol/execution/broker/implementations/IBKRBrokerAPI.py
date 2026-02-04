from __future__ import annotations

from decimal import Decimal
from typing import Any

from ib_insync import MarketOrder

from tol.execution.broker.BrokerAPI import BrokerAPI, OrderStatus, OrderSubmission
from tol.ibkr.gateway import IBKRGateway


class IBKRBrokerAPI(BrokerAPI):
    def __init__(self, mode: str, client_id: int) -> None:
        self._mode = mode
        self._client_id = client_id

    def submit_order(self, order_spec: dict[str, Any]) -> OrderSubmission:
        gateway = IBKRGateway(self._mode, self._client_id)
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
            trade_snapshot = _build_trade_snapshot(
                trade=trade,
                order_spec=order_spec,
                broker_order_id=broker_order_id,
            )
            return OrderSubmission(
                broker_order_id=broker_order_id,
                trade=trade_snapshot,
            )
        finally:
            gateway.disconnect()

    def cancel_order(self, broker_order_id: str) -> None:
        gateway = IBKRGateway(self._mode, self._client_id)
        gateway.connect()
        try:
            gateway.ib.cancelOrder(int(broker_order_id))
        finally:
            gateway.disconnect()

    def get_order_status(self, broker_order_id: str) -> OrderStatus:
        gateway = IBKRGateway(self._mode, self._client_id)
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

    def list_open_orders(self) -> list[str]:
        gateway = IBKRGateway(self._mode, self._client_id)
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
        gateway = IBKRGateway(self._mode, self._client_id)
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


def _build_trade_snapshot(
    trade: Any,
    order_spec: dict[str, Any],
    broker_order_id: str,
) -> dict[str, Any]:
    order_status = getattr(trade, "orderStatus", None)
    status = getattr(order_status, "status", "Submitted")
    filled = getattr(order_status, "filled", 0)
    avg_price = getattr(order_status, "avgFillPrice", None)
    order = getattr(trade, "order", None)
    order_type = getattr(order, "orderType", None)
    avg_price_decimal = None
    if avg_price is not None:
        avg_price_decimal = float(Decimal(str(avg_price)))
    return {
        "order_id": broker_order_id,
        "status": str(status).upper(),
        "filled_qty": float(Decimal(str(filled))),
        "avg_fill_price": avg_price_decimal,
        "action_type": order_spec.get("action_type"),
        "symbol": order_spec.get("symbol"),
        "submitted_qty": float(Decimal(str(order_spec.get("quantity", 0)))),
        "order_type": order_type,
    }
