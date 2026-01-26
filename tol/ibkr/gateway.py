from decimal import Decimal
from collections import defaultdict
from ib_insync import IB


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

        return results
