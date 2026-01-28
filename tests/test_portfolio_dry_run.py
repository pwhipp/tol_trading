from decimal import Decimal
import unittest

from tol.cli.handlers.portfolio_dry_run import (
    _apply_pending_trades,
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

    def test_sell_insufficient_holdings(self) -> None:
        tol_doc = {
            "actions": [
                {"sell": {"symbol": "AAPL", "quantity": 10}},
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "AAPL",
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
                {"buy": {"symbol": "MSFT", "quantity": 5, "using": ["CASH"]}},
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "MSFT",
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
        self.assertEqual(evaluations[0].planned_trades[0].symbol, "MSFT")

    def test_buy_uses_matching_currency_cash(self) -> None:
        tol_doc = {
            "actions": [
                {"buy": {"symbol": "TSLA", "quantity": 1.0, "using": ["CASH"]}},
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("100"), "AUD": Decimal("200")},
            [
                {
                    "symbol": "TSLA",
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
                        "symbol": "AAPL",
                        "percent": 75,
                        "using": ["CASH", "AAPL"],
                    }
                }
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "AAPL",
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
                {"sell": {"symbol": "AAPL", "quantity": 5}},
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "AAPL",
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
                    "symbol": "AAPL",
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
            any("Pending trade conflict" in msg for msg in evaluations[0].warnings)
        )

    def test_pending_trade_does_not_reprice_existing_holdings(self) -> None:
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "AAPL",
                    "quantity": Decimal("10"),
                    "market_value": Decimal("1000"),
                    "currency": "USD",
                }
            ],
        )

        adjusted_snapshot, _ = _apply_pending_trades(
            snapshot,
            normalize_pending_trades(
                [
                    {
                        "symbol": "AAPL",
                        "action_type": "buy",
                        "quantity": Decimal("2"),
                        "status": "Submitted",
                        "price": Decimal("90"),
                        "currency": "USD",
                        "order_type": "LMT",
                    }
                ]
            ),
        )

        position = adjusted_snapshot.positions_by_symbol["AAPL"]
        self.assertEqual(position.quantity, Decimal("12"))
        self.assertEqual(position.market_value, Decimal("1200"))

    def test_pending_sell_uses_position_price_for_value(self) -> None:
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "TSLA",
                    "quantity": Decimal("10"),
                    "market_value": Decimal("1000"),
                    "currency": "USD",
                }
            ],
        )

        adjusted_snapshot, _ = _apply_pending_trades(
            snapshot,
            normalize_pending_trades(
                [
                    {
                        "symbol": "TSLA",
                        "action_type": "sell",
                        "quantity": Decimal("10"),
                        "status": "Submitted",
                        "price": Decimal("90"),
                        "currency": "USD",
                        "order_type": "LMT",
                    }
                ]
            ),
        )

        position = adjusted_snapshot.positions_by_symbol["TSLA"]
        self.assertEqual(position.quantity, Decimal("0"))
        self.assertEqual(position.market_value, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
