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
        if symbol == "BAD":
            return None
        return {"symbol": symbol, "currency": currency, "exchange": exchange}

    def validate_order(
        self,
        contract: object,
        action_type: str,
        quantity: Decimal,
    ) -> dict:
        return {"status": "Validated"}


class TestBrokerDryRun(unittest.TestCase):
    def test_validate_buy_action(self) -> None:
        tol_doc = {
            "actions": [
                {"buy": {"symbol": "AAPL", "quantity": 5}},
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

    def test_validate_symbol_failure(self) -> None:
        tol_doc = {
            "actions": [
                {"buy": {"symbol": "BAD", "quantity": 1}},
            ]
        }
        actions = plan_actions(tol_doc)
        validation = validate_action_with_broker(actions[0], FakeGateway("paper"))

        self.assertTrue(validation.errors)

    def test_percent_quantity_warns(self) -> None:
        tol_doc = {
            "actions": [
                {"sell": {"symbol": "AAPL", "quantity": "50%"}},
            ]
        }
        actions = plan_actions(tol_doc)
        validation = validate_action_with_broker(actions[0], FakeGateway("paper"))

        self.assertTrue(validation.warnings)
        self.assertFalse(validation.errors)

    def test_run_broker_dry_run_disconnects(self) -> None:
        tol_doc = {
            "actions": [
                {"buy": {"symbol": "AAPL", "quantity": 1}},
            ]
        }
        actions = plan_actions(tol_doc)
        gateway = FakeGateway("paper")

        def factory(_: str) -> FakeGateway:
            return gateway

        run_broker_dry_run(actions, "paper", gateway_factory=factory)

        self.assertTrue(gateway.connected)
        self.assertTrue(gateway.disconnected)


if __name__ == "__main__":
    unittest.main()
