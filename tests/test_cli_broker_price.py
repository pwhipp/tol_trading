from __future__ import annotations

from argparse import Namespace

from tol.cli.handlers.broker import price as broker_price
from tol.cli.handlers.broker.price import BrokerPriceHandler


class _Section(dict):
    def __getattr__(self, item: str):
        return self[item]


class _StubConfig(dict):
    def __getattr__(self, item: str):
        return self[item]

    def save(self) -> None:
        self["saved"] = True


def test_normalize_tickers_uses_default_exchange_when_missing() -> None:
    tickers = BrokerPriceHandler._normalize_tickers(["msft", "nvda.nasdaq"], "nyse")

    assert tickers[0].symbol == "MSFT"
    assert tickers[0].exchange == "NYSE"
    assert tickers[1].symbol == "NVDA"
    assert tickers[1].exchange == "NASDAQ"


def test_normalize_tickers_falls_back_to_nsye_default() -> None:
    tickers = BrokerPriceHandler._normalize_tickers(["aapl"], None)

    assert tickers[0].symbol == "AAPL"
    assert tickers[0].exchange == "NSYE"


def test_persist_watched_tickers_reset_and_add_modes() -> None:
    config = _StubConfig(broker=_Section(watched_tickers=["AAPL.NASDAQ"]))

    BrokerPriceHandler._persist_watched_tickers(
        config,
        BrokerPriceHandler._normalize_tickers(["msft"], "nyse"),
        "reset",
    )
    assert config["broker"]["watched_tickers"] == ["MSFT.NYSE"]

    BrokerPriceHandler._persist_watched_tickers(
        config,
        BrokerPriceHandler._normalize_tickers(["aapl.nasdaq", "msft.nyse"], "nyse"),
        "add",
    )
    assert config["broker"]["watched_tickers"] == ["MSFT.NYSE", "AAPL.NASDAQ"]


def test_handle_rejects_non_ibkr_broker(monkeypatch) -> None:
    args = Namespace(tickers=["MSFT"], watch="reset")
    config = _StubConfig(
        broker=_Section(api="FakeBrokerAPI", mode="paper", client_id=1, watched_tickers=[]),
        execution=_Section(default_exchange="NYSE"),
    )

    monkeypatch.setattr(broker_price, "get_config", lambda: config)

    try:
        BrokerPriceHandler.handle(args)
    except ValueError as exc:
        assert str(exc) == "tol broker price is only supported with IBKRBrokerAPI"
    else:
        raise AssertionError("Expected ValueError")


def test_resolve_raw_tickers_prefers_cli_values() -> None:
    args = Namespace(tickers=["MSFT"], watch="reset")
    config = _StubConfig(broker=_Section(watched_tickers=["AAPL.NASDAQ"]))

    resolved = BrokerPriceHandler._resolve_raw_tickers(args, config)

    assert resolved == ["MSFT"]


def test_resolve_raw_tickers_falls_back_to_watched_tickers() -> None:
    args = Namespace(tickers=[], watch="reset")
    config = _StubConfig(broker=_Section(watched_tickers=["AAPL.NASDAQ", "MSFT.NYSE"]))

    resolved = BrokerPriceHandler._resolve_raw_tickers(args, config)

    assert resolved == ["AAPL.NASDAQ", "MSFT.NYSE"]


def test_resolve_raw_tickers_raises_when_no_sources() -> None:
    args = Namespace(tickers=[], watch="reset")
    config = _StubConfig(broker=_Section(watched_tickers=[]))

    try:
        BrokerPriceHandler._resolve_raw_tickers(args, config)
    except ValueError as exc:
        assert (
            str(exc)
            == "No tickers supplied. Provide tickers or set broker.watched_tickers in config."
        )
    else:
        raise AssertionError("Expected ValueError")


class _GatewayStub:
    last_instance = None

    def __init__(self, mode: str, client_id: int) -> None:
        self.mode = mode
        self.client_id = client_id
        self.calls: list[float] = []
        _GatewayStub.last_instance = self

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def qualify_stock_contract(self, _symbol: str):
        return object()

    def get_market_snapshot(self, _contract, settle_window: float = 0.0) -> dict:
        self.calls.append(settle_window)
        return {
            "price": None,
            "bid": None,
            "ask": None,
            "currency": "AUD",
            "is_open": None,
        }


def test_handle_passes_configured_settle_window(monkeypatch) -> None:
    args = Namespace(tickers=["BHP.ASX"], watch="reset")
    config = _StubConfig(
        broker=_Section(
            api="IBKRBrokerAPI",
            mode="paper",
            client_id=1,
            watched_tickers=[],
            settle_window=0.3,
        ),
        execution=_Section(default_exchange="ASX"),
    )

    monkeypatch.setattr(broker_price, "get_config", lambda: config)
    monkeypatch.setattr(broker_price, "IBKRGateway", _GatewayStub)

    BrokerPriceHandler.handle(args)

    assert _GatewayStub.last_instance is not None
    assert _GatewayStub.last_instance.calls == [0.3]
