from decimal import Decimal
from collections import defaultdict
from ib_insync import IB, MarketOrder, Stock


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

    def qualify_stock_contract(
        self,
        symbol: str,
        currency: str = "USD",
        exchange: str = "SMART",
    ):
        contract = Stock(symbol, exchange, currency)
        contracts = self.ib.qualifyContracts(contract)
        if not contracts:
            return None
        return contracts[0]

    def validate_order(
        self,
        contract,
        action_type: str,
        quantity: Decimal,
    ) -> dict:
        side = "BUY" if action_type == "buy" else "SELL"
        order = MarketOrder(side, float(quantity))
        order_state = self.ib.whatIfOrder(contract, order)
        status = getattr(order_state, "status", None)
        return {"status": status}
