import io
import unittest
from contextlib import redirect_stdout

from ib_insync.wrapper import RequestError

from tol.ibkr.gateway import IBKRGateway


class _FakeIB:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.disconnected = False

    def isConnected(self) -> bool:
        return False

    def connect(self, *_args, **_kwargs) -> None:
        raise self._error

    def disconnect(self) -> None:
        self.disconnected = True


class TestIBKRGatewayConnect(unittest.TestCase):
    def test_client_id_in_use_prints_message(self) -> None:
        gateway = IBKRGateway("paper", client_id=7)
        error = RequestError(reqId=1, code=326, message="client id conflict")
        gateway.ib = _FakeIB(error)

        stdout = io.StringIO()
        with self.assertRaises(RequestError):
            with redirect_stdout(stdout):
                gateway.connect()

        self.assertTrue(gateway.ib.disconnected)
        self.assertEqual(
            stdout.getvalue().strip(),
            "clientId (7) already in use.\n"
            "Try a different clientId or restart the IB Gateway process.",
        )

    def test_connection_refused_prints_message(self) -> None:
        gateway = IBKRGateway("paper", client_id=7)
        gateway.ib = _FakeIB(
            ConnectionRefusedError(
                111,
                "Connect call failed",
                ("127.0.0.1", 4002),
            )
        )

        stdout = io.StringIO()
        with self.assertRaises(SystemExit):
            with redirect_stdout(stdout):
                gateway.connect()

        self.assertEqual(
            stdout.getvalue().strip(),
            "API connection failed: ConnectionRefusedError("
            "111, 'Connect call failed')\n"
            "Make sure API port on TWS/IBG is open",
        )


class _SnapshotTicker:
    def __init__(
        self,
        last=None,
        close=None,
        bid=None,
        ask=None,
        market_price=None,
    ) -> None:
        self.last = last
        self.close = close
        self.bid = bid
        self.ask = ask
        self._market_price = market_price

    def marketPrice(self):
        return self._market_price


class TestIBKRGatewaySnapshotParsing(unittest.TestCase):
    def test_extract_snapshot_price_uses_market_price_fallback(self) -> None:
        ticker = _SnapshotTicker(last=float("nan"), close=None, market_price=49.02)

        price = IBKRGateway._extract_snapshot_price(ticker)

        self.assertEqual(str(price), "49.02")

    def test_extract_snapshot_marks_open_when_bid_ask_present(self) -> None:
        ticker = _SnapshotTicker(last=None, close=None, bid=48.9, ask=49.1)

        price, is_open = IBKRGateway._extract_snapshot(ticker)

        self.assertIsNone(price)
        self.assertTrue(is_open)

    def test_extract_snapshot_marks_closed_when_price_without_bid_ask(self) -> None:
        ticker = _SnapshotTicker(last=49.02, close=None, bid=None, ask=None)

        price, is_open = IBKRGateway._extract_snapshot(ticker)

        self.assertEqual(str(price), "49.02")
        self.assertFalse(is_open)


class _FakeIBCancel:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.cancel_calls = 0

    def cancelMktData(self, _contract) -> None:
        self.cancel_calls += 1
        if self._error is not None:
            raise self._error


class TestIBKRGatewayCancelMarketData(unittest.TestCase):
    def test_cancel_market_data_ignores_error_300(self) -> None:
        gateway = IBKRGateway("paper", client_id=7)
        gateway.ib = _FakeIBCancel(
            RequestError(reqId=32, code=300, message="Can't find EId with tickerId:32")
        )

        gateway._cancel_market_data(contract=object())

        self.assertEqual(gateway.ib.cancel_calls, 1)

    def test_cancel_market_data_raises_other_request_errors(self) -> None:
        gateway = IBKRGateway("paper", client_id=7)
        gateway.ib = _FakeIBCancel(
            RequestError(reqId=32, code=321, message="Some other IBKR error")
        )

        with self.assertRaises(RequestError):
            gateway._cancel_market_data(contract=object())
