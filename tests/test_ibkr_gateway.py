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


class _FakeIBSnapshot:
    def __init__(self, ticker: _SnapshotTicker) -> None:
        self._ticker = ticker
        self.market_data_requests: list[tuple[bool, bool]] = []
        self.sleeps: list[float] = []
        self.cancel_calls = 0

    def reqMarketDataType(self, _market_data_type: int) -> None:
        return None

    def reqMktData(self, _contract, _generic, snapshot: bool, regulatory: bool):
        self.market_data_requests.append((snapshot, regulatory))
        return self._ticker

    def sleep(self, value: float) -> None:
        self.sleeps.append(value)

    def cancelMktData(self, _contract) -> None:
        self.cancel_calls += 1


class TestIBKRGatewaySnapshotParsing(unittest.TestCase):
    def test_extract_snapshot_price_uses_market_price_fallback(self) -> None:
        ticker = _SnapshotTicker(last=float("nan"), close=None, market_price=49.02)

        price = IBKRGateway._extract_snapshot_price(ticker)

        self.assertEqual(str(price), "49.02")

    def test_get_market_snapshot_returns_bid_and_ask(self) -> None:
        gateway = IBKRGateway("paper", client_id=7)
        fake_ib = _FakeIBSnapshot(
            _SnapshotTicker(last=None, close=49.02, bid=48.9, ask=49.1)
        )
        gateway.ib = fake_ib

        snapshot = gateway.get_market_snapshot(contract=object())

        self.assertEqual(str(snapshot["price"]), "49.02")
        self.assertEqual(str(snapshot["bid"]), "48.9")
        self.assertEqual(str(snapshot["ask"]), "49.1")
        self.assertTrue(snapshot["is_open"])
        self.assertEqual(fake_ib.market_data_requests, [(True, False)])

    def test_get_market_snapshot_does_not_cancel_snapshot_request(self) -> None:
        gateway = IBKRGateway("paper", client_id=7)
        fake_ib = _FakeIBSnapshot(_SnapshotTicker(last=49.02))
        gateway.ib = fake_ib

        gateway.get_market_snapshot(contract=object())

        self.assertEqual(fake_ib.cancel_calls, 0)


    def test_get_market_snapshot_sleeps_for_settle_window_before_polling(self) -> None:
        gateway = IBKRGateway("paper", client_id=7)
        fake_ib = _FakeIBSnapshot(_SnapshotTicker(last=49.02))
        gateway.ib = fake_ib

        gateway.get_market_snapshot(contract=object(), settle_window=0.3)

        self.assertGreaterEqual(len(fake_ib.sleeps), 1)
        self.assertEqual(fake_ib.sleeps[0], 0.3)

    def test_get_market_snapshot_sanitizes_negative_ask_value(self) -> None:
        gateway = IBKRGateway("paper", client_id=7)
        fake_ib = _FakeIBSnapshot(
            _SnapshotTicker(last=-1, bid=-1, ask=-1)
        )
        gateway.ib = fake_ib

        snapshot = gateway.get_market_snapshot(contract=object())

        self.assertIsNone(snapshot["price"])
        self.assertIsNone(snapshot["bid"])
        self.assertIsNone(snapshot["ask"])
