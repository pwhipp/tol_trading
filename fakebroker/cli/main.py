import argparse

from fakebroker.cli.handlers.fakebroker import handle_fakebroker
from tol.execution.broker.implementations.FakeBrokerAPI import IBKR_FAIL_REASONS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fakebroker",
        description="FakeBroker CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    market_parser = subparsers.add_parser(
        "market",
        help="Open or close a market for an exchange",
    )
    market_sub = market_parser.add_subparsers(dest="market_command", required=True)
    market_open = market_sub.add_parser("open", help="Open an exchange market")
    market_open.add_argument("exchange", help="Exchange code (e.g. NASDAQ)")
    market_close = market_sub.add_parser("close", help="Close an exchange market")
    market_close.add_argument("exchange", help="Exchange code (e.g. NASDAQ)")

    subparsers.add_parser("status", help="Show fake broker state as YAML")

    price_parser = subparsers.add_parser("price", help="Manage static prices")
    price_sub = price_parser.add_subparsers(dest="price_command", required=True)
    price_set = price_sub.add_parser("set", help="Set a static price")
    price_set.add_argument("symbol", help="Ticker symbol (e.g. NVDA)")
    price_set.add_argument("price", help="Price value")
    price_set.add_argument("currency", help="Currency code (e.g. USD)")
    price_set.add_argument(
        "--market",
        dest="market",
        help="Exchange code to append to the symbol",
    )

    cash_parser = subparsers.add_parser("cash", help="Manage cash holdings")
    cash_sub = cash_parser.add_subparsers(dest="cash_command", required=True)
    cash_set = cash_sub.add_parser("set", help="Set cash by currency")
    cash_set.add_argument("amount", help="Cash amount")
    cash_set.add_argument("currency", help="Currency code (e.g. USD)")

    order_parser = subparsers.add_parser("order", help="Inspect or fill orders")
    order_sub = order_parser.add_subparsers(dest="order_command", required=True)
    order_sub.add_parser("list", help="List open orders")
    order_fill = order_sub.add_parser("fill", help="Fill one or more orders")
    order_fill.add_argument(
        "order_ids",
        nargs="+",
        help="One or more broker order ids (e.g. FB-1 FB-2)",
    )
    order_fill.add_argument(
        "--quantity",
        dest="quantity",
        help="Optional fill quantity",
    )
    order_delete = order_sub.add_parser("delete", help="Delete one or more orders")
    order_delete.add_argument(
        "order_ids",
        nargs="+",
        help="One or more broker order ids (e.g. FB-1 FB-2)",
    )

    fail_parser = subparsers.add_parser("fail", help="Fail an order")
    fail_parser.add_argument("order_id", help="Broker order id (e.g. FB-1)")
    fail_parser.add_argument(
        "--reason",
        dest="reason",
        required=True,
        choices=IBKR_FAIL_REASONS,
        help="Failure reason",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handle_fakebroker(args)
