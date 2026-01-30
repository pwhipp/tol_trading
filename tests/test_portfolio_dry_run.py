from decimal import Decimal
import unittest

from tol.cli.handlers.portfolio_dry_run import (
    apply_pending_trades,
    build_portfolio_report,
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
            any("Order overlap" in msg for msg in evaluations[0].warnings)
        )

    def test_reserved_cash_blocks_buy(self) -> None:
        tol_doc = {
            "actions": [
                {"buy": {"symbol": "AAPL", "quantity": 10, "using": ["CASH"]}},
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
                    "symbol": "VOO",
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
            any(
                "Insufficient value to satisfy buy quantity." in msg
                for msg in evaluations[0].errors
            )
        )

    def test_target_uses_amended_snapshot(self) -> None:
        tol_doc = {
            "actions": [
                {
                    "target": {
                        "symbol": "TSLA",
                        "percent": 10,
                        "using": ["CASH", "NVDA"],
                    }
                }
            ]
        }
        actions = plan_actions(tol_doc)
        snapshot = build_snapshot(
            {"USD": Decimal("1000")},
            [
                {
                    "symbol": "TSLA",
                    "quantity": Decimal("10"),
                    "market_value": Decimal("1000"),
                    "currency": "USD",
                },
                {
                    "symbol": "NVDA",
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
                    "symbol": "TSLA",
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
                "Implied buy" in msg for msg in evaluations[0].messages
            )
        )

    def test_apply_pending_trades_amends_snapshot(self) -> None:
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
        pending = normalize_pending_trades(
            [
                {
                    "symbol": "AAPL",
                    "action_type": "buy",
                    "quantity": Decimal("2"),
                    "status": "Submitted",
                    "price": Decimal("110"),
                    "currency": "USD",
                },
                {
                    "symbol": "AAPL",
                    "action_type": "sell",
                    "quantity": Decimal("1"),
                    "status": "Submitted",
                    "price": Decimal("105"),
                    "currency": "USD",
                },
                {
                    "symbol": "MSFT",
                    "action_type": "buy",
                    "quantity": Decimal("1"),
                    "status": "Submitted",
                    "price": Decimal("50"),
                    "currency": "USD",
                },
            ]
        )

        amended_snapshot, warnings = apply_pending_trades(snapshot, pending)
        self.assertFalse(warnings)
        self.assertEqual(amended_snapshot.cash_by_currency["USD"], Decimal("835"))
        self.assertEqual(
            amended_snapshot.positions_by_symbol["AAPL"].quantity, Decimal("6")
        )
        self.assertEqual(
            amended_snapshot.positions_by_symbol["AAPL"].market_value, Decimal("615")
        )
        self.assertEqual(
            amended_snapshot.positions_by_symbol["MSFT"].quantity, Decimal("1")
        )

    def test_build_portfolio_report_includes_amended_values(self) -> None:
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
        pending = normalize_pending_trades(
            [
                {
                    "symbol": "AAPL",
                    "action_type": "buy",
                    "quantity": Decimal("2"),
                    "status": "Submitted",
                    "price": Decimal("100"),
                    "currency": "USD",
                }
            ]
        )
        amended_snapshot, _ = apply_pending_trades(snapshot, pending)
        report = build_portfolio_report(
            snapshot,
            amended_snapshot,
            pending,
            [],
        )
        self.assertIn("Orders:", report)
        self.assertTrue(
            any("USD: 1,000.00 [800.00]" in line for line in report)
        )
        self.assertTrue(
            any(
                "AAPL: 5 shares (≈ 500.00 USD) [7 shares (≈ 700.00 USD)]"
                in line
                for line in report
            )
        )


if __name__ == "__main__":
    unittest.main()
