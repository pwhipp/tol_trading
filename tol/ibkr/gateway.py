import math
import sys
from collections import defaultdict
from decimal import Decimal
from ib_insync import IB, MarketOrder, Stock
from ib_insync.wrapper import RequestError

from tol.exchange import resolve_exchange_currency

_REFUSED_ENDPOINTS: set[tuple[str, int]] = set()


class IBKRGateway:
    def __init__(self, mode: str, client_id: int):
        self.mode = mode
        self.client_id = client_id
        self.ib = IB()

    def connect(self):
        host = "127.0.0.1"
        port = 4002 if self.mode == "paper" else 4001
        if self.ib.isConnected():
            self.ib.disconnect()
        try:
            self.ib.connect(
                host,
                port=port,
                clientId=self.client_id,
                timeout=5,
            )
        except RequestError as exc:
            if exc.code == 326:
                print(
                    "clientId ({}) already in use.\n"
                    "Try a different clientId or restart the IB Gateway process.".format(
                        self.client_id
                    )
                )
            self.ib.disconnect()
            raise
        except ConnectionRefusedError as exc:
            print(
                f"API connection failed: ConnectionRefusedError{exc.args[:2]!r}\n"
                "Make sure API port on TWS/IBG is open"
            )
            self.ib.disconnect()
            sys.exit(1)

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
            exchange = _select_exchange(
                getattr(p.contract, "primaryExchange", None),
                getattr(p.contract, "exchange", None),
            )
            results.append({
                "symbol": _format_ticker(p.contract.symbol, exchange),
                "quantity": Decimal(str(p.position)),
                "market_value": Decimal(str(p.marketValue)),
                "currency": p.contract.currency,
            })

        return results

    def get_pending_trades(self):
        trades = []
        self.ib.reqAllOpenOrders()
        self.ib.sleep(1)
        for trade in self.ib.openTrades():
            contract = getattr(trade, "contract", None)
            order = getattr(trade, "order", None)
            status = getattr(getattr(trade, "orderStatus", None), "status", None)
            if contract is None or order is None:
                continue
            action = getattr(order, "action", None)
            if not action:
                continue
            action_type = action.lower()
            if action_type not in {"buy", "sell"}:
                continue
            remaining = getattr(
                getattr(trade, "orderStatus", None),
                "remaining",
                None,
            )
            total_quantity = getattr(order, "totalQuantity", None)
            quantity = self._safe_decimal(remaining or total_quantity)
            if quantity is None or quantity <= 0:
                continue
            limit_price = self._safe_decimal(getattr(order, "lmtPrice", None))
            if limit_price is not None and limit_price <= 0:
                limit_price = None
            exchange = _select_exchange(
                getattr(contract, "primaryExchange", None),
                getattr(contract, "exchange", None),
            )
            trades.append(
                {
                    "symbol": _format_ticker(getattr(contract, "symbol", ""), exchange),
                    "action_type": action_type,
                    "quantity": quantity,
                    "status": status or "Unknown",
                    "price": limit_price,
                    "currency": getattr(contract, "currency", "USD"),
                    "order_type": getattr(order, "orderType", None),
                    "order_id": getattr(order, "orderId", None),
                }
            )
        return trades

    def qualify_stock_contract(
        self,
        symbol: str,
        currency: str = "USD",
        exchange: str = "SMART",
    ):
        base_symbol, exchange_suffix = _split_ticker(symbol)
        resolved_exchange = exchange_suffix or exchange
        resolved_currency = resolve_exchange_currency(resolved_exchange) or currency
        contract = Stock(base_symbol, resolved_exchange, resolved_currency)
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

    def get_market_snapshot(self, contract, settle_window: float = 0.0) -> dict:
        self.ib.reqMarketDataType(3)
        settle_delay = max(0.0, float(settle_window))
        ticker = self.ib.reqMktData(contract, "", True, False)
        if settle_delay > 0:
            self.ib.sleep(settle_delay)
        for _ in range(25):
            self.ib.sleep(0.2)
            if self._extract_snapshot_price(ticker) is not None:
                break

        price = self._extract_snapshot_price(ticker)
        bid = self._sanitize_quote_value(getattr(ticker, "bid", None))
        ask = self._sanitize_quote_value(getattr(ticker, "ask", None))

        is_open = None
        if bid is not None and ask is not None:
            is_open = True
        elif price is not None:
            is_open = False

        return {
            "price": price,
            "bid": bid,
            "ask": ask,
            "currency": getattr(contract, "currency", "USD"),
            "is_open": is_open,
        }

    @staticmethod
    def _sanitize_quote_value(value) -> Decimal | None:
        quote = IBKRGateway._safe_decimal(value)
        if quote is None or quote < 0:
            return None
        return quote

    @staticmethod
    def _extract_snapshot_price(ticker) -> Decimal | None:
        candidates = [
            getattr(ticker, "last", None),
            getattr(ticker, "close", None),
            getattr(ticker, "marketPrice", lambda: None)(),
        ]
        for candidate in candidates:
            sanitized = IBKRGateway._sanitize_quote_value(candidate)
            if sanitized is not None:
                return sanitized
        return None

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


def _split_ticker(symbol: str) -> tuple[str, str | None]:
    cleaned = symbol.strip().upper()
    if "." in cleaned:
        base, exchange = cleaned.rsplit(".", 1)
        if base and exchange:
            return base, exchange
    return cleaned, None


def _format_ticker(symbol: str, exchange: str | None) -> str:
    cleaned = str(symbol).strip().upper()
    if not exchange:
        return cleaned
    return f"{cleaned}.{exchange.strip().upper()}"


def _select_exchange(primary_exchange: str | None, fallback: str | None) -> str | None:
    for candidate in (primary_exchange, fallback):
        if candidate and str(candidate).strip():
            return str(candidate).strip().upper()
    return None
