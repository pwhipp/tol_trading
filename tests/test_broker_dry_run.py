from decimal import Decimal
import unittest

from tol.cli.handlers.broker_dry_run import (
    run_broker_dry_run,
    validate_action_with_broker,
)
from tol.parser.planner import plan_actions


class FakeGateway:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.connected = False
        self.disconnected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.disconnected = True

    def qualify_stock_contract(
        self,
        symbol: str,
        currency: str = "USD",
        exchange: str = "SMART",
    ):
        if symbol.split(".")[0] == "BAD":
            return None
        return {"symbol": symbol, "currency": currency, "exchange": exchange}

    def validate_order(
        self,
        contract: object,
        action_type: str,
        quantity: Decimal,
    ) -> dict:
        return {"status": "Validated"}

    def get_market_snapshot(self, contract: object) -> dict:
        symbol = contract["symbol"] if isinstance(contract, dict) else "UNKNOWN"
        base_symbol = symbol.split(".")[0]
        return {
            "price": Decimal("250.00"),
            "currency": "USD",
            "is_open": base_symbol != "CLOSED",
        }

    def get_cash_by_currency(self) -> dict[str, Decimal]:
        return {"USD": Decimal("1000")}

    def get_pending_trades(self) -> list[dict]:
        return []


class TestBrokerDryRun(unittest.TestCase):
    def test_validate_buy_action(self) -> None:
        tol_doc = {
            "actions": [
                {"buy": {"symbol": "AAPL.NASDAQ", "quantity": 5}},
            ]
        }
        actions = plan_actions(tol_doc)
        validation = validate_action_with_broker(actions[0], FakeGateway("paper"))

        self.assertFalse(validation.errors)
        self.assertTrue(
            any("Resolved contract" in msg for msg in validation.messages)
        )
        self.assertTrue(
            any("Broker validation status" in msg for msg in validation.messages)
        )
        self.assertEqual(len(validation.planned_trades), 1)
        self.assertEqual(validation.planned_trades[0].symbol, "AAPL.NASDAQ")

    def test_validate_symbol_failure(self) -> None:
        tol_doc = {
            "actions": [
                {"buy": {"symbol": "BAD.NYSE", "quantity": 1}},
            ]
        }
        actions = plan_actions(tol_doc)
        validation = validate_action_with_broker(actions[0], FakeGateway("paper"))

        self.assertTrue(validation.errors)

    def test_percent_quantity_warns(self) -> None:
        tol_doc = {
            "actions": [
                {"sell": {"symbol": "AAPL.NASDAQ", "quantity": "50%"}},
            ]
        }
        actions = plan_actions(tol_doc)
        validation = validate_action_with_broker(actions[0], FakeGateway("paper"))

        self.assertTrue(validation.warnings)
        self.assertFalse(validation.errors)

    def test_percent_buy_resolves_quantity(self) -> None:
        tol_doc = {
            "actions": [
                {"buy": {"symbol": "AAPL.NASDAQ", "quantity": 0.5}},
            ]
        }
        actions = plan_actions(tol_doc)
        validation = validate_action_with_broker(actions[0], FakeGateway("paper"))

        self.assertFalse(validation.errors)
        self.assertEqual(len(validation.planned_trades), 1)

    def test_market_closed_warning(self) -> None:
        tol_doc = {
            "actions": [
                {"buy": {"symbol": "CLOSED.NYSE", "quantity": 1}},
            ]
        }
        actions = plan_actions(tol_doc)
        validation = validate_action_with_broker(actions[0], FakeGateway("paper"))

        self.assertTrue(
            any("Market appears closed" in msg for msg in validation.warnings)
        )
        self.assertEqual(len(validation.planned_trades), 1)

    def test_run_broker_dry_run_disconnects(self) -> None:
        tol_doc = {
            "actions": [
                {"buy": {"symbol": "AAPL.NASDAQ", "quantity": 1}},
            ]
        }
        actions = plan_actions(tol_doc)
        gateway = FakeGateway("paper")

        def factory(_: str) -> FakeGateway:
            return gateway

        run_broker_dry_run(actions, "paper", gateway_factory=factory)

        self.assertTrue(gateway.connected)
        self.assertTrue(gateway.disconnected)

    def test_pending_trade_conflict_warns(self) -> None:
        tol_doc = {
            "actions": [
                {"buy": {"symbol": "AAPL.NASDAQ", "quantity": 1}},
            ]
        }
        actions = plan_actions(tol_doc)
        validation = validate_action_with_broker(
            actions[0],
            FakeGateway("paper"),
            pending_trades=[
                {
                    "symbol": "AAPL.NASDAQ",
                    "action_type": "sell",
                    "quantity": Decimal("2"),
                    "status": "Submitted",
                    "price": Decimal("190"),
                    "currency": "USD",
                    "order_type": "LMT",
                }
            ],
        )

        self.assertTrue(
            any("Pending trade overlap" in msg for msg in validation.warnings)
        )

    def test_convert_action_checks_cash(self) -> None:
        tol_doc = {
            "actions": [
                {"convert": {"amount": "$500 (USD)", "to": "AUD"}},
            ]
        }
        actions = plan_actions(tol_doc)
        validation = validate_action_with_broker(actions[0], FakeGateway("paper"))

        self.assertFalse(validation.errors)
        expected = "Convert $500 (USD) to AUD."
        self.assertTrue(
            any(expected in msg for msg in validation.messages)
        )

    def test_convert_action_insufficient_cash(self) -> None:
        tol_doc = {
            "actions": [
                {"convert": {"amount": "$2,000 (USD)", "to": "AUD"}},
            ]
        }
        actions = plan_actions(tol_doc)
        validation = validate_action_with_broker(actions[0], FakeGateway("paper"))

        self.assertTrue(validation.errors)

    def test_convert_action_same_currency_invalid(self) -> None:
        tol_doc = {
            "actions": [
                {"convert": {"amount": "$25 (USD)", "to": "USD"}},
            ]
        }
        actions = plan_actions(tol_doc)
        validation = validate_action_with_broker(actions[0], FakeGateway("paper"))

        self.assertTrue(validation.errors)


if __name__ == "__main__":
    unittest.main()
