from __future__ import annotations

from decimal import Decimal

from tol.cli.handlers.broker.summary import _normalize_snapshot


def test_normalize_snapshot_converts_top_level_position_market_value() -> None:
    snapshot = {
        "cash": {"USD": 1000.0},
        "positions": [
            {
                "symbol": "TSM.NYSE",
                "quantity": 100,
                "market_value": 10000.0,
                "currency": "USD",
            }
        ],
    }

    cash_by_currency, positions = _normalize_snapshot(snapshot)

    assert cash_by_currency["USD"] == Decimal("1000.0")
    assert positions[0]["market_value"] == Decimal("10000.0")


def test_normalize_snapshot_converts_nested_portfolio_position_market_value() -> None:
    snapshot = {
        "portfolio": {
            "cash": {"USD": 1000},
            "positions": [
                {
                    "symbol": "TSM.NYSE",
                    "quantity": 100,
                    "market_value": 10000.0,
                    "currency": "USD",
                }
            ],
        }
    }

    cash_by_currency, positions = _normalize_snapshot(snapshot)

    assert cash_by_currency["USD"] == Decimal("1000")
    assert positions[0]["market_value"] == Decimal("10000.0")
