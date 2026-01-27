import unittest

from tol.ibkr.gateway import BrokerDryRunResult, IBKRGateway
from tol.parser.planner import PlannedAction


class StubIB:
    def __init__(self, resolvable_symbols: set[str]) -> None:
        self.resolvable_symbols = resolvable_symbols

    def qualifyContracts(self, contract):
        if contract.symbol in self.resolvable_symbols:
            return [contract]
        return []


class TestIBKRGateway(unittest.TestCase):
    def test_normalize_symbol(self) -> None:
        self.assertEqual(IBKRGateway.normalize_symbol(" aapl "), "AAPL")

        with self.assertRaises(ValueError):
            IBKRGateway.normalize_symbol(None)

        with self.assertRaises(ValueError):
            IBKRGateway.normalize_symbol(" ")

        with self.assertRaises(ValueError):
            IBKRGateway.normalize_symbol("BRK.B")

    def test_broker_dry_run(self) -> None:
        gateway = IBKRGateway("paper")
        gateway.ib = StubIB({"AAPL"})

        actions = [
            PlannedAction(
                index=0,
                action_type="buy",
                symbol="AAPL",
                quantity="10",
                derived_id="buyAAPL",
                depends_on=[],
            ),
            PlannedAction(
                index=1,
                action_type="buy",
                symbol="msft",
                quantity="5",
                derived_id="buyMSFT",
                depends_on=[],
            ),
            PlannedAction(
                index=2,
                action_type="buy",
                symbol="bad.symbol",
                quantity="1",
                derived_id="buyBAD",
                depends_on=[],
            ),
        ]

        results = gateway.broker_dry_run(actions)
        self.assertEqual(len(results), 3)

        expected = [
            BrokerDryRunResult(
                action_id="buyAAPL",
                symbol="AAPL",
                status="ok",
                details="Contract resolved.",
            ),
            BrokerDryRunResult(
                action_id="buyMSFT",
                symbol="MSFT",
                status="unresolved_contract",
                details="No matching contract found.",
            ),
            BrokerDryRunResult(
                action_id="buyBAD",
                symbol="bad.symbol",
                status="invalid_symbol",
                details="Symbol must be alphanumeric",
            ),
        ]

        self.assertEqual(results, expected)


if __name__ == "__main__":
    unittest.main()
