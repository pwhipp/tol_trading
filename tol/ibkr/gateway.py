from dataclasses import dataclass
from decimal import Decimal
from collections import defaultdict
from typing import Iterable, List

from ib_insync import IB, Stock

from tol.parser.planner import PlannedAction


@dataclass(frozen=True)
class BrokerDryRunResult:
    action_id: str
    symbol: str
    status: str
    details: str | None = None


class IBKRGateway:
    def __init__(self, mode: str):
        self.mode = mode
        self.ib = IB()

    def connect(self):
        port = 7497 if self.mode == "paper" else 7496
        self.ib.connect("127.0.0.1", port=port, clientId=991, timeout=5)

    def disconnect(self):
        self.ib.disconnect()

    def get_cash_by_currency(self):
        cash = defaultdict(Decimal)

        for row in self.ib.accountSummary():
            if row.tag == "CashBalance":
                cash[row.currency] += Decimal(row.value)

        return cash

    def get_position_values(self):
        values = defaultdict(Decimal)
        for row in self.ib.accountSummary():
            if row.tag == "MarketValue" and row.symbol:
                values[row.symbol] += Decimal(row.value)
        return values

    def get_positions(self):
        results = []

        for p in self.ib.portfolio():
            results.append({
                "symbol": p.contract.symbol,
                "quantity": Decimal(str(p.position)),
                "market_value": Decimal(str(p.marketValue)),
                "currency": p.contract.currency,
            })

        return results

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        if symbol is None:
            raise ValueError("Symbol cannot be None")

        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("Symbol cannot be empty")
        if not normalized.isalnum():
            raise ValueError("Symbol must be alphanumeric")

        return normalized

    def broker_dry_run(
        self, actions: Iterable[PlannedAction]
    ) -> List[BrokerDryRunResult]:
        results: List[BrokerDryRunResult] = []

        for action in actions:
            try:
                symbol = self.normalize_symbol(action.symbol)
            except ValueError as exc:
                results.append(
                    BrokerDryRunResult(
                        action_id=action.derived_id,
                        symbol=action.symbol,
                        status="invalid_symbol",
                        details=str(exc),
                    )
                )
                continue

            contract = Stock(symbol, "SMART", "USD")
            qualified = self.ib.qualifyContracts(contract)
            if not qualified:
                results.append(
                    BrokerDryRunResult(
                        action_id=action.derived_id,
                        symbol=symbol,
                        status="unresolved_contract",
                        details="No matching contract found.",
                    )
                )
                continue

            results.append(
                BrokerDryRunResult(
                    action_id=action.derived_id,
                    symbol=symbol,
                    status="ok",
                    details="Contract resolved.",
                )
            )

        return results
