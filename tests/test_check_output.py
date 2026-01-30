from contextlib import redirect_stdout
from decimal import Decimal
import io
import unittest
from unittest.mock import patch

from tol.cli.handlers.check import handle_check


class _FakeGateway:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def get_cash_by_currency(self):
        return {"USD": Decimal("1000")}

    def get_positions(self):
        return [
            {
                "symbol": "NVDA",
                "quantity": Decimal("10"),
                "market_value": Decimal("1000"),
                "currency": "USD",
            }
        ]

    def get_pending_trades(self):
        return [
            {
                "symbol": "BHP",
                "action_type": "buy",
                "quantity": Decimal("2"),
                "status": "Submitted",
                "price": Decimal("100"),
                "currency": "USD",
                "order_type": "LMT",
            }
        ]


class _Args:
    def __init__(self, mode: str) -> None:
        self.mode = mode


class TestCheckOutput(unittest.TestCase):
    def test_check_includes_amended_values(self) -> None:
        buffer = io.StringIO()
        args = _Args(mode="paper")

        with patch("tol.ibkr.gateway.IBKRGateway", _FakeGateway):
            with redirect_stdout(buffer):
                handle_check(args)

        output = buffer.getvalue()
        self.assertIn("Cash:", output)
        self.assertIn(
            "  USD:     1,000.00   50.00% (    800.00  40.00%)", output
        )
        self.assertIn("Positions:", output)
        self.assertIn("  NVDA", output)
        self.assertIn("(BHP", output)
        self.assertIn("200.00 USD", output)
        self.assertIn("10.00%)", output)


if __name__ == "__main__":
    unittest.main()
