from decimal import Decimal
import unittest

from tol.cli.handlers.portfolio_dry_run import (
    build_snapshot,
    evaluate_actions,
    normalize_quantity,
)
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


if __name__ == "__main__":
    unittest.main()
