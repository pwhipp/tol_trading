from __future__ import annotations

from argparse import Namespace

from tol.cli.handlers.broker import price as broker_price
from tol.cli.handlers.broker.price import BrokerPriceHandler


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
    config = _StubConfig(broker_watched_tickers=["AAPL.NASDAQ"])

    BrokerPriceHandler._persist_watched_tickers(
        config,
        BrokerPriceHandler._normalize_tickers(["msft"], "nyse"),
        "reset",
    )
    assert config["broker_watched_tickers"] == ["MSFT.NYSE"]

    BrokerPriceHandler._persist_watched_tickers(
        config,
        BrokerPriceHandler._normalize_tickers(["aapl.nasdaq", "msft.nyse"], "nyse"),
        "add",
    )
    assert config["broker_watched_tickers"] == ["MSFT.NYSE", "AAPL.NASDAQ"]


def test_handle_rejects_non_ibkr_broker(monkeypatch) -> None:
    args = Namespace(tickers=["MSFT"], watch="reset")
    config = _StubConfig(
        broker="FakeBrokerAPI",
        default_exchange="NYSE",
        mode="paper",
        broker_client_id=1,
        broker_watched_tickers=[],
    )

    monkeypatch.setattr(broker_price, "get_config", lambda: config)

    try:
        BrokerPriceHandler.handle(args)
    except ValueError as exc:
        assert str(exc) == "tol broker price is only supported with IBKRBrokerAPI"
    else:
        raise AssertionError("Expected ValueError")
