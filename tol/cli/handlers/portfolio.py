from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from tol.cli.handlers.pending_trades import (
    format_pending_trade,
    normalize_pending_trades,
)
from tol.cli.handlers.execution_helpers import get_broker_api
from tol.config import get_config


def handle_portfolio_summary(args) -> None:
    config = get_config()
    broker_api = get_broker_api(config.mode)

    print("TOL Portfolio Summary")
    print("----------------------------------------")
    print(f"Trading mode: {config.mode}")
    print()

    snapshot = broker_api.get_portfolio_snapshot()
    cash_by_ccy, positions = _normalize_snapshot(snapshot)

    position_totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    for position in positions:
        position_totals[position["currency"]] += position["market_value"]

    portfolio_totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    for ccy, amt in cash_by_ccy.items():
        portfolio_totals[ccy] += amt
    for ccy, amt in position_totals.items():
        portfolio_totals[ccy] += amt

    print("Cash:")
    for ccy in sorted(cash_by_ccy):
        amt = cash_by_ccy[ccy]
        total = portfolio_totals[ccy]
        print(
            f"  {ccy}: {amt:>12,.2f}   "
            f"{_pct(amt, total):>6}%"
        )

    print()
    print("Positions:")
    for position in sorted(positions, key=lambda item: item["symbol"]):
        sym = position["symbol"]
        qty = position["quantity"]
        mv = position["market_value"]
        ccy = position["currency"]
        total = portfolio_totals[ccy]

        print(
            f"  {sym:<5} "
            f"{int(qty):>6} shares   "
            f"≈ {mv:>12,.2f} {ccy}   "
            f"{_pct(mv, total):>6}%"
        )

    print()
    print("Positions value:")
    for ccy in sorted(portfolio_totals):
        mv = position_totals.get(ccy, Decimal("0"))
        total = portfolio_totals[ccy]
        print(
            f"  {ccy}: {mv:>12,.2f}   "
            f"{_pct(mv, total):>6}%"
        )

    print("----------------------------------------")


def handle_portfolio_orders(args) -> None:
    config = get_config()
    broker_api = get_broker_api(config.mode)
    open_orders = broker_api.list_open_order_details()
    pending_trades = normalize_pending_trades(open_orders)

    print("TOL Portfolio Open Orders")
    print("----------------------------------------")
    print(f"Trading mode: {config.mode}")
    print()
    if not pending_trades:
        print("No open orders.")
        print("----------------------------------------")
        return
    for trade in pending_trades:
        print(f"  {format_pending_trade(trade)}")
    print("----------------------------------------")


def _pct(value: Decimal, total: Decimal) -> Decimal:
    if total == 0:
        return Decimal("0")
    return (value / total * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _normalize_snapshot(snapshot: dict) -> tuple[dict[str, Decimal], list[dict]]:
    cash = snapshot.get("cash")
    positions = snapshot.get("positions")
    if isinstance(cash, dict) and isinstance(positions, list):
        cash_by_ccy = {
            ccy: Decimal(str(value)) for ccy, value in cash.items()
        }
        return cash_by_ccy, positions
    portfolio = snapshot.get("portfolio", {})
    cash = portfolio.get("cash", {})
    positions = portfolio.get("positions", [])
    cash_by_ccy = {
        ccy: Decimal(str(value)) for ccy, value in cash.items()
    }
    return cash_by_ccy, positions
