import unittest
from decimal import Decimal

from tol.parser.planner import ParsedQuantity, parse_percent, parse_quantity


class TestPlannerParsing(unittest.TestCase):
    def test_parse_percent(self) -> None:
        self.assertEqual(parse_percent(10), Decimal("10"))
        self.assertEqual(parse_percent("10%"), Decimal("10"))
        self.assertEqual(parse_percent(" 12.5 "), Decimal("12.5"))

        with self.assertRaises(ValueError):
            parse_percent("")

        with self.assertRaises(ValueError):
            parse_percent("abc")

    def test_parse_quantity(self) -> None:
        self.assertEqual(
            parse_quantity(10),
            ParsedQuantity(kind="shares", value=Decimal("10")),
        )
        self.assertEqual(
            parse_quantity("10%"),
            ParsedQuantity(kind="percent", value=Decimal("10")),
        )
        self.assertEqual(
            parse_quantity("ALL"),
            ParsedQuantity(kind="all", value=None),
        )

        with self.assertRaises(ValueError):
            parse_quantity("")

        with self.assertRaises(ValueError):
            parse_quantity("oops")


if __name__ == "__main__":
    unittest.main()
