from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class OrderStatus:
    status: str
    filled_qty: Decimal
    average_price: Decimal | None = None


@dataclass(frozen=True)
class OrderSubmission:
    broker_order_id: str
    trade: dict[str, Any]


class BrokerAPI(ABC):
    @abstractmethod
    def submit_order(self, order_spec: dict[str, Any]) -> OrderSubmission:
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
    def list_open_order_details(self) -> Iterable[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_portfolio_snapshot(self) -> dict[str, Any]:
        raise NotImplementedError
