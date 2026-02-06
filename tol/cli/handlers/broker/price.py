from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from decimal import Decimal

from tabulate import tabulate

from tol.config import get_config
from tol.ibkr.gateway import IBKRGateway


@dataclass(frozen=True)
class BrokerTicker:
    symbol: str
    exchange: str


class BrokerPriceHandler:
    @staticmethod
    def handle(args: Namespace) -> None:
        config = get_config()
        raw_tickers = BrokerPriceHandler._resolve_raw_tickers(args, config)
        tickers = BrokerPriceHandler._normalize_tickers(
            raw_tickers,
            config.execution.default_exchange,
        )
        BrokerPriceHandler._persist_watched_tickers(config, tickers, args.watch)

        if config.broker.api != "IBKRBrokerAPI":
            raise ValueError("tol broker price is only supported with IBKRBrokerAPI")

        gateway = IBKRGateway(config.broker.mode, config.broker.client_id)
        settle_window = max(0.0, float(config.broker.settle_window))
        rows: list[list[str]] = []

        gateway.connect()
        try:
            for ticker in tickers:
                formatted_ticker = f"{ticker.symbol}.{ticker.exchange}"
                contract = gateway.qualify_stock_contract(formatted_ticker)
                if contract is None:
                    rows.append([formatted_ticker, "-", "-", "-", "-", "-", "FAILED"])
                    continue

                snapshot = gateway.get_market_snapshot(
                    contract,
                    settle_window=settle_window,
                )
                rows.append(
                    [
                        formatted_ticker,
                        BrokerPriceHandler._sanitize_decimal(snapshot.get("price")),
                        BrokerPriceHandler._sanitize_decimal(snapshot.get("bid")),
                        BrokerPriceHandler._sanitize_decimal(snapshot.get("ask")),
                        str(snapshot.get("currency") or "-"),
                        BrokerPriceHandler._format_market_open(
                            snapshot.get("is_open")
                        ),
                        "OK",
                    ]
                )
        finally:
            gateway.disconnect()

        print(
            tabulate(
                rows,
                headers=[
                    "Ticker",
                    "Price",
                    "Bid",
                    "Ask",
                    "Currency",
                    "Market Open",
                    "Status",
                ],
                tablefmt="github",
            )
        )

    @staticmethod
    def _resolve_raw_tickers(args: Namespace, config) -> list[str]:
        cli_tickers = args.tickers or []
        if cli_tickers:
            return cli_tickers

        watched_tickers = config.broker.get("watched_tickers") or []
        if watched_tickers:
            return watched_tickers

        raise ValueError(
            "No tickers supplied. Provide tickers or set broker.watched_tickers in config."
        )

    @staticmethod
    def _normalize_tickers(
        raw_tickers: list[str],
        default_exchange: str | None,
    ) -> list[BrokerTicker]:
        exchange = (default_exchange or "NSYE").strip().upper()
        normalized: list[BrokerTicker] = []
        seen: set[tuple[str, str]] = set()

        for raw_ticker in raw_tickers:
            ticker = BrokerPriceHandler._normalize_ticker(raw_ticker, exchange)
            key = (ticker.symbol, ticker.exchange)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(ticker)

        return normalized

    @staticmethod
    def _normalize_ticker(raw_ticker: str, default_exchange: str) -> BrokerTicker:
        cleaned = raw_ticker.strip().upper()
        if "." in cleaned:
            symbol, exchange = cleaned.rsplit(".", 1)
            return BrokerTicker(symbol=symbol.strip(), exchange=exchange.strip())
        return BrokerTicker(symbol=cleaned, exchange=default_exchange)

    @staticmethod
    def _persist_watched_tickers(
        config,
        tickers: list[BrokerTicker],
        watch_mode: str,
    ) -> None:
        watched = [f"{ticker.symbol}.{ticker.exchange}" for ticker in tickers]
        if watch_mode == "add":
            existing = config.broker.get("watched_tickers") or []
            merged = list(dict.fromkeys([*existing, *watched]))
            config.broker["watched_tickers"] = merged
            config.save()
            return

        config.broker["watched_tickers"] = watched
        config.save()

    @staticmethod
    def _format_market_open(value: bool | None) -> str:
        if value is True:
            return "yes"
        if value is False:
            return "no"
        return "unknown"

    @staticmethod
    def _sanitize_decimal(value: Decimal | None) -> str:
        if value is None:
            return "-"
        return f"{value}"


def handle_broker_price(args: Namespace) -> None:
    BrokerPriceHandler.handle(args)
