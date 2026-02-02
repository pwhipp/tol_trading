from decimal import Decimal
import unittest

from tol.cli.handlers.portfolio_dry_run import (
    _derive_reservations,
    build_snapshot,
    evaluate_actions,
    normalize_quantity,
)
from tol.cli.handlers.pending_trades import normalize_pending_trades
from tol.parser.planner import plan_actions


class TestPortfolioDryRun(unittest.TestCase):
    def test_normalize_quantity(self) -> None:
        qty_all = normalize_quantity("ALL")
        self.assertEqual(qty_all.kind, "all")

        qty_percent = normalize_quantity("25%")
        self.assertEqual(qty_percent.kind, "percent")
        self.assertEqual(qty_percent.value, Decimal("0.25"))

        qty_shares = normalize_quantity(10)
        self.assertEqual(qty_shares.kind, "shares")
        self.assertEqual(qty_shares.value, Decimal("10"))

        qty_float = normalize_quantity(0.5)
        self.assertEqual(qty_float.kind, "percent")
        self.assertEqual(qty_float.value, Decimal("0.5"))

        qty_value = normalize_quantity("$1,000 (USD)")
        self.assertEqual(qty_value.kind, "value")
        self.assertEqual(qty_value.value, Decimal("1000"))
        self.assertEqual(qty_value.currency, "USD")

    def test_sell_insufficient_holdings(self) -> None:
        tol_doc = {
            "actions": [
                {"sell": {"symbol": "AAPL.NASDAQ", "quantity": 10}},
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "AAPL.NASDAQ",
                    "quantity": Decimal("5"),
                    "market_value": Decimal("500"),
                    "currency": "USD",
                }
            ],
        )

        evaluations = evaluate_actions(actions, snapshot)
        self.assertTrue(evaluations[0].errors)

    def test_buy_with_cash_sources(self) -> None:
        tol_doc = {
            "actions": [
                {
                    "buy": {
                        "symbol": "MSFT.NASDAQ",
                        "quantity": 5,
                        "using": ["CASH[USD]"],
                    }
                },
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "MSFT.NASDAQ",
                    "quantity": Decimal("10"),
                    "market_value": Decimal("1000"),
                    "currency": "USD",
                }
            ],
        )

        evaluations = evaluate_actions(actions, snapshot)
        self.assertFalse(evaluations[0].errors)
        self.assertTrue(
            any("Estimated spend" in msg for msg in evaluations[0].messages)
        )
        self.assertEqual(len(evaluations[0].planned_trades), 1)
        self.assertEqual(evaluations[0].planned_trades[0].symbol, "MSFT.NASDAQ")

    def test_buy_uses_matching_currency_cash(self) -> None:
        tol_doc = {
            "actions": [
                {
                    "buy": {
                        "symbol": "TSLA.NASDAQ",
                        "quantity": 1.0,
                        "using": ["CASH[USD]"],
                    }
                },
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("100"), "AUD": Decimal("200")},
            [
                {
                    "symbol": "TSLA.NASDAQ",
                    "quantity": Decimal("10"),
                    "market_value": Decimal("1000"),
                    "currency": "USD",
                }
            ],
        )

        evaluations = evaluate_actions(actions, snapshot)
        self.assertTrue(
            any(
                "Available value from sources: 100.00." in msg
                for msg in evaluations[0].messages
            )
        )
        self.assertTrue(evaluations[0].warnings)

    def test_target_implied_buy(self) -> None:
        tol_doc = {
            "actions": [
                {
                    "target": {
                        "symbol": "AAPL.NASDAQ",
                        "percent": 75,
                        "using": ["CASH[USD]", "AAPL.NASDAQ"],
                    }
                }
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "AAPL.NASDAQ",
                    "quantity": Decimal("10"),
                    "market_value": Decimal("1000"),
                    "currency": "USD",
                }
            ],
        )

        evaluations = evaluate_actions(actions, snapshot)
        self.assertFalse(evaluations[0].errors)
        self.assertTrue(
            any("Implied buy" in msg for msg in evaluations[0].messages)
        )
        self.assertEqual(len(evaluations[0].planned_trades), 1)

    def test_pending_trade_conflict_adjusts_holdings(self) -> None:
        tol_doc = {
            "actions": [
                {"sell": {"symbol": "AAPL.NASDAQ", "quantity": 5}},
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "AAPL.NASDAQ",
                    "quantity": Decimal("5"),
                    "market_value": Decimal("500"),
                    "currency": "USD",
                }
            ],
        )

        evaluations = evaluate_actions(
            actions,
            snapshot,
            pending_trades=[
                {
                    "symbol": "AAPL.NASDAQ",
                    "action_type": "buy",
                    "quantity": Decimal("2"),
                    "status": "Submitted",
                    "price": Decimal("100"),
                    "currency": "USD",
                    "order_type": "LMT",
                }
            ],
        )
        self.assertFalse(evaluations[0].errors)
        self.assertTrue(
            any("Pending trade overlap" in msg for msg in evaluations[0].warnings)
        )

    def test_convert_action_reports_message(self) -> None:
        tol_doc = {
            "actions": [
                {"convert": {"amount": "$1,000 (USD)", "to": "CASH[AUD]"}},
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot({"USD": Decimal("1000")}, [])

        evaluations = evaluate_actions(actions, snapshot)
        self.assertFalse(evaluations[0].errors)
        expected = "Convert $1,000 (USD) to CASH[AUD]."
        self.assertTrue(
            any(expected in msg for msg in evaluations[0].messages)
        )

    def test_pending_buy_reserves_cash(self) -> None:
        pending = normalize_pending_trades(
            [
                {
                    "symbol": "VOO.NYSE",
                    "action_type": "buy",
                    "quantity": Decimal("2"),
                    "status": "Submitted",
                    "price": Decimal("300"),
                    "currency": "USD",
                    "order_type": "LMT",
                }
            ]
        )
        reservations, warnings = _derive_reservations(pending)
        self.assertFalse(warnings)
        self.assertEqual(reservations.cash_by_currency["USD"], Decimal("600"))

    def test_pending_sell_reserves_shares(self) -> None:
        pending = normalize_pending_trades(
            [
                {
                    "symbol": "TSLA.NASDAQ",
                    "action_type": "sell",
                    "quantity": Decimal("10"),
                    "status": "Submitted",
                    "order_type": "LMT",
                }
            ]
        )
        reservations, warnings = _derive_reservations(pending)
        self.assertFalse(warnings)
        self.assertEqual(
            reservations.shares_by_symbol["TSLA.NASDAQ"],
            Decimal("10"),
        )

    def test_reserved_cash_blocks_buy(self) -> None:
        tol_doc = {
            "actions": [
                {
                    "buy": {
                        "symbol": "AAPL.NASDAQ",
                        "quantity": 10,
                        "using": ["CASH[USD]"],
                    }
                },
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "AAPL.NASDAQ",
                    "quantity": Decimal("5"),
                    "market_value": Decimal("500"),
                    "currency": "USD",
                }
            ],
        )

        evaluations = evaluate_actions(
            actions,
            snapshot,
            pending_trades=[
                {
                    "symbol": "VOO.NYSE",
                    "action_type": "buy",
                    "quantity": Decimal("5"),
                    "status": "Submitted",
                    "price": Decimal("150"),
                    "currency": "USD",
                    "order_type": "LMT",
                    "order_id": 123,
                }
            ],
        )
        self.assertTrue(evaluations[0].errors)
        self.assertTrue(
            any("Reserved by pending buys" in msg for msg in evaluations[0].errors)
        )

    def test_target_warns_on_pending_sell(self) -> None:
        tol_doc = {
            "actions": [
                {
                    "target": {
                        "symbol": "TSLA.NASDAQ",
                        "percent": 10,
                        "using": ["CASH[USD]", "NVDA.NASDAQ"],
                    }
                }
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "TSLA.NASDAQ",
                    "quantity": Decimal("10"),
                    "market_value": Decimal("1000"),
                    "currency": "USD",
                },
                {
                    "symbol": "NVDA.NASDAQ",
                    "quantity": Decimal("5"),
                    "market_value": Decimal("500"),
                    "currency": "USD",
                },
            ],
        )

        evaluations = evaluate_actions(
            actions,
            snapshot,
            pending_trades=[
                {
                    "symbol": "TSLA.NASDAQ",
                    "action_type": "sell",
                    "quantity": Decimal("10"),
                    "status": "Submitted",
                    "order_type": "LMT",
                    "order_id": 321,
                }
            ],
        )
        self.assertTrue(
            any(
                "Pending sells reserve shares for target symbol" in msg
                for msg in evaluations[0].warnings
            )
        )


if __name__ == "__main__":
    unittest.main()
