import math
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

    def get_market_snapshot(self, contract) -> dict:
        self.ib.reqMarketDataType(3)
        ticker = self.ib.reqMktData(contract, "", False, False)
        self.ib.sleep(1)
        last = self._safe_decimal(getattr(ticker, "last", None))
        close = self._safe_decimal(getattr(ticker, "close", None))
        bid = self._safe_decimal(getattr(ticker, "bid", None))
        ask = self._safe_decimal(getattr(ticker, "ask", None))
        price = last or close
        is_open = None
        if bid is not None and ask is not None:
            is_open = True
        elif price is not None:
            is_open = False
        return {
            "price": price,
            "currency": getattr(contract, "currency", "USD"),
            "is_open": is_open,
        }

    @staticmethod
    def _safe_decimal(value) -> Decimal | None:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(numeric):
            return None
        return Decimal(str(value))
