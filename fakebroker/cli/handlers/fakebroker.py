from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any

import yaml

from tol.config import get_config_path
from tol.execution.broker.implementations.FakeBrokerAPI import (
    FakeBrokerState,
    IBKR_FAIL_REASONS,
)


@dataclass(frozen=True)
class FillResult:
    order_id: str
    filled_qty: Decimal
    price: Decimal
    currency: str
    status: str


class FakeBrokerController:
    def __init__(self, state_path: Path) -> None:
        self._state = FakeBrokerState(state_path)

    def status(self) -> dict[str, Any]:
        return self._state.load()

    def open_market(self, exchange: str) -> None:
        state = self._state.load()
        closed = self._normalize_closed_markets(state)
        exchange_code = self._state.normalize_exchange(exchange)
        closed = [item for item in closed if item != exchange_code]
        state["closed_markets"] = closed
        self._state.save(state)

    def close_market(self, exchange: str) -> None:
        state = self._state.load()
        closed = self._normalize_closed_markets(state)
        exchange_code = self._state.normalize_exchange(exchange)
        if exchange_code not in closed:
            closed.append(exchange_code)
        state["closed_markets"] = closed
        self._state.save(state)

    def set_price(
        self,
        symbol: str,
        price: Decimal,
        currency: str,
        market: str | None = None,
    ) -> None:
        state = self._state.load()
        normalized = self._resolve_symbol(symbol, market)
        prices = state.setdefault("prices", {})
        prices[normalized] = {
            "price": float(price),
            "currency": self._state.normalize_currency(currency),
        }
        self._state.save(state)

    def set_cash(self, amount: Decimal, currency: str) -> None:
        state = self._state.load()
        portfolio = state.setdefault("portfolio", {})
        cash = portfolio.setdefault("cash", {})
        cash[self._state.normalize_currency(currency)] = float(amount)
        self._state.save(state)

    def list_open_orders(self) -> list[dict[str, Any]]:
        state = self._state.load()
        orders = []
        for order_id, order in state.get("orders", {}).items():
            status = str(order.get("status", "")).upper()
            if status not in {"SUBMITTED", "PARTIAL"}:
                continue
            trade = order.get("trade", {})
            orders.append(
                {
                    "order_id": order_id,
                    "action_type": str(trade.get("action_type", "")).lower(),
                    "symbol": str(trade.get("symbol", "")).upper(),
                    "status": status,
                    "submitted_qty": Decimal(str(order.get("submitted_qty", 0))),
                    "filled_qty": Decimal(str(order.get("filled_qty", 0))),
                    "average_price": order.get("average_price"),
                }
            )
        orders.sort(key=self._order_sort_key)
        return orders

    def fill_order(self, order_id: str, quantity: Decimal | None = None) -> FillResult:
        state = self._state.load()
        orders = state.get("orders", {})
        if order_id not in orders:
            raise ValueError(f"Unknown broker order id {order_id}")
        order = orders[order_id]
        status = str(order.get("status", "")).upper()
        if status not in {"SUBMITTED", "PARTIAL"}:
            raise ValueError(f"Order {order_id} is not open")
        trade = order.get("trade", {})
        action_type = str(trade.get("action_type", "")).lower()
        symbol = FakeBrokerState.normalize_symbol(trade.get("symbol", ""))
        submitted_qty = Decimal(str(order.get("submitted_qty", 0)))
        filled_qty = Decimal(str(order.get("filled_qty", 0)))
        remaining = submitted_qty - filled_qty
        if remaining <= 0:
            raise ValueError(f"Order {order_id} has no remaining quantity")
        requested = remaining if quantity is None else quantity
        if requested <= 0:
            raise ValueError("Fill quantity must be positive")

        price, currency = self._state.resolve_price(state, symbol)
        fill_qty = self._resolve_fill_quantity(
            state=state,
            symbol=symbol,
            action_type=action_type,
            requested=requested,
            remaining=remaining,
            price=price,
            currency=currency,
        )
        if fill_qty <= 0:
            raise ValueError("Unable to fill order with current constraints")

        new_filled = filled_qty + fill_qty
        average_price = self._resolve_average_price(
            order=order,
            added_qty=fill_qty,
            price=price,
        )
        order["filled_qty"] = float(new_filled)
        order["average_price"] = float(average_price)
        order["status"] = "FILLED" if new_filled >= submitted_qty else "PARTIAL"
        order["trade"] = self._update_trade_snapshot(
            trade=trade,
            status=order["status"],
            filled_qty=new_filled,
            average_price=average_price,
        )
        self._state.save(state)
        return FillResult(
            order_id=order_id,
            filled_qty=fill_qty,
            price=price,
            currency=currency,
            status=order["status"],
        )

    def fail_order(self, order_id: str, reason: str) -> None:
        if reason not in IBKR_FAIL_REASONS:
            raise ValueError(f"Unsupported reason: {reason}")
        state = self._state.load()
        orders = state.get("orders", {})
        if order_id not in orders:
            raise ValueError(f"Unknown broker order id {order_id}")
        order = orders[order_id]
        order["status"] = "FAILED"
        order["failure_reason"] = reason
        trade = order.get("trade", {})
        trade["status"] = "FAILED"
        trade["failure_reason"] = reason
        order["trade"] = trade
        self._state.save(state)

    def delete_orders(self, order_ids: list[str]) -> tuple[list[str], list[str]]:
        state = self._state.load()
        orders = state.get("orders", {})
        deleted: list[str] = []
        missing: list[str] = []
        for order_id in order_ids:
            if order_id in orders:
                del orders[order_id]
                deleted.append(order_id)
            else:
                missing.append(order_id)
        self._state.save(state)
        return deleted, missing

    @staticmethod
    def _order_sort_key(item: dict[str, Any]) -> tuple[int, str]:
        action = str(item.get("action_type", "")).lower()
        action_rank = 0 if action == "sell" else 1
        return action_rank, str(item.get("order_id", ""))

    @staticmethod
    def _normalize_closed_markets(state: dict[str, Any]) -> list[str]:
        closed = state.get("closed_markets", [])
        if not isinstance(closed, list):
            return []
        return [str(item).strip().upper() for item in closed if str(item).strip()]

    def _resolve_symbol(self, symbol: str, market: str | None) -> str:
        normalized = FakeBrokerState.normalize_symbol(symbol)
        if market:
            base, _ = FakeBrokerState.split_symbol(normalized)
            return f"{base}.{FakeBrokerState.normalize_exchange(market)}"
        return normalized

    def _resolve_fill_quantity(
        self,
        state: dict[str, Any],
        symbol: str,
        action_type: str,
        requested: Decimal,
        remaining: Decimal,
        price: Decimal,
        currency: str,
    ) -> Decimal:
        if action_type == "buy":
            cash = self._get_cash(state, currency)
            max_qty = Decimal("0")
            if price > 0:
                max_qty = cash / price
            fill_qty = min(requested, remaining, max_qty)
            fill_qty = self._round_down(fill_qty)
            cost = fill_qty * price
            self._set_cash(state, currency, cash - cost)
            self._update_position(state, symbol, fill_qty, price, currency, is_buy=True)
            return fill_qty
        if action_type == "sell":
            available = self._get_position_qty(state, symbol)
            fill_qty = min(requested, remaining, available)
            fill_qty = self._round_down(fill_qty)
            proceeds = fill_qty * price
            cash = self._get_cash(state, currency)
            self._set_cash(state, currency, cash + proceeds)
            self._update_position(
                state,
                symbol,
                fill_qty,
                price,
                currency,
                is_buy=False,
            )
            return fill_qty
        raise ValueError(f"Unsupported action type: {action_type}")

    @staticmethod
    def _resolve_average_price(
        order: dict[str, Any],
        added_qty: Decimal,
        price: Decimal,
    ) -> Decimal:
        filled_qty = Decimal(str(order.get("filled_qty", 0)))
        avg_price = order.get("average_price")
        average = Decimal(str(avg_price)) if avg_price is not None else Decimal("0")
        total_qty = filled_qty + added_qty
        if total_qty <= 0:
            return Decimal("0")
        total_cost = (average * filled_qty) + (price * added_qty)
        return total_cost / total_qty

    @staticmethod
    def _update_trade_snapshot(
        trade: dict[str, Any],
        status: str,
        filled_qty: Decimal,
        average_price: Decimal,
    ) -> dict[str, Any]:
        updated = dict(trade)
        updated["status"] = status
        updated["filled_qty"] = float(filled_qty)
        updated["avg_fill_price"] = float(average_price)
        return updated

    @staticmethod
    def _round_down(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.0001"), rounding=ROUND_DOWN)

    @staticmethod
    def _get_cash(state: dict[str, Any], currency: str) -> Decimal:
        portfolio = state.setdefault("portfolio", {})
        cash = portfolio.setdefault("cash", {})
        amount = cash.get(currency, 0)
        return Decimal(str(amount))

    @staticmethod
    def _set_cash(state: dict[str, Any], currency: str, amount: Decimal) -> None:
        portfolio = state.setdefault("portfolio", {})
        cash = portfolio.setdefault("cash", {})
        cash[currency] = float(amount)

    @staticmethod
    def _get_position_qty(state: dict[str, Any], symbol: str) -> Decimal:
        positions = state.setdefault("portfolio", {}).setdefault("positions", [])
        for position in positions:
            if str(position.get("symbol", "")).upper() == symbol:
                return Decimal(str(position.get("quantity", 0)))
        return Decimal("0")

    @staticmethod
    def _update_position(
        state: dict[str, Any],
        symbol: str,
        qty: Decimal,
        price: Decimal,
        currency: str,
        is_buy: bool,
    ) -> None:
        portfolio = state.setdefault("portfolio", {})
        positions = portfolio.setdefault("positions", [])
        for position in positions:
            if str(position.get("symbol", "")).upper() == symbol:
                current_qty = Decimal(str(position.get("quantity", 0)))
                new_qty = current_qty + qty if is_buy else current_qty - qty
                if new_qty <= 0:
                    positions.remove(position)
                else:
                    position["quantity"] = float(new_qty)
                    position["market_value"] = float(new_qty * price)
                    position["currency"] = currency
                return
        if is_buy and qty > 0:
            positions.append(
                {
                    "symbol": symbol,
                    "quantity": float(qty),
                    "market_value": float(qty * price),
                    "currency": currency,
                }
            )

    @staticmethod
    def _coerce_decimal(value: str | Decimal | None) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value).replace(",", "").strip())


def handle_fakebroker(args: Any) -> None:
    controller = FakeBrokerController(_resolve_state_path())
    if args.command == "status":
        state = controller.status()
        print(yaml.safe_dump(state, sort_keys=False).strip())
        return
    if args.command == "market":
        if args.market_command == "open":
            controller.open_market(args.exchange)
            return
        if args.market_command == "close":
            controller.close_market(args.exchange)
            return
    if args.command == "price" and args.price_command == "set":
        price = FakeBrokerController._coerce_decimal(args.price)
        controller.set_price(args.symbol, price, args.currency, args.market)
        return
    if args.command == "cash" and args.cash_command == "set":
        amount = FakeBrokerController._coerce_decimal(args.amount)
        controller.set_cash(amount, args.currency)
        return
    if args.command == "order":
        if args.order_command == "list":
            _print_order_table(controller.list_open_orders())
            return
        if args.order_command == "fill":
            quantity = (
                FakeBrokerController._coerce_decimal(args.quantity)
                if args.quantity is not None
                else None
            )
            result = controller.fill_order(args.order_id, quantity)
            print(
                f"Filled {result.filled_qty} @ {result.price} {result.currency} "
                f"for {result.order_id} ({result.status})."
            )
            return
        if args.order_command == "delete":
            deleted, missing = controller.delete_orders(args.order_ids)
            if deleted:
                print(f"Deleted orders: {', '.join(deleted)}")
            if missing:
                print(f"Missing orders: {', '.join(missing)}")
            return
    if args.command == "fail":
        controller.fail_order(args.order_id, args.reason)
        return
    raise ValueError("Unknown fakebroker command")


def _resolve_state_path() -> Path:
    config_dir = get_config_path().parent
    return config_dir / "fake_broker_state.yaml"


def _print_order_table(orders: list[dict[str, Any]]) -> None:
    if not orders:
        print("No open orders.")
        return
    columns = [
        ("ORDER_ID", 10),
        ("SIDE", 6),
        ("SYMBOL", 16),
        ("STATUS", 10),
        ("SUBMITTED", 12),
        ("FILLED", 12),
        ("AVG_PRICE", 12),
    ]
    header = " ".join(label.ljust(width) for label, width in columns)
    print(header)
    print("-" * len(header))
    for order in orders:
        avg_price = order.get("average_price")
        avg_text = "" if avg_price is None else f"{Decimal(str(avg_price)):.4f}"
        row = [
            str(order["order_id"]).ljust(10),
            str(order["action_type"]).upper().ljust(6),
            str(order["symbol"]).ljust(16),
            str(order["status"]).ljust(10),
            f"{order['submitted_qty']:.4f}".rjust(12),
            f"{order['filled_qty']:.4f}".rjust(12),
            avg_text.rjust(12),
        ]
        print(" ".join(row))
