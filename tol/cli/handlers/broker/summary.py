from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from tol.cli.handlers.helpers.execution import get_broker_api
from tol.config import get_config


def handle_broker_summary(args) -> None:
    del args
    config = get_config()
    broker_api = get_broker_api(config.broker.mode)

    print("TOL Broker Summary")
    print("----------------------------------------")
    print(f"Trading mode: {config.broker.mode}")
    print()

    snapshot = broker_api.get_portfolio_snapshot()
    cash_by_ccy, positions = _normalize_snapshot(snapshot)

    position_totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    for position in positions:
        position_totals[position["currency"]] += position["market_value"]

    broker_totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    for currency, amount in cash_by_ccy.items():
        broker_totals[currency] += amount
    for currency, amount in position_totals.items():
        broker_totals[currency] += amount

    print("Cash:")
    for currency in sorted(cash_by_ccy):
        amount = cash_by_ccy[currency]
        total = broker_totals[currency]
        print(f"  {currency}: {amount:>12,.2f}   {_pct(amount, total):>6}%")

    print()
    print("Positions:")
    for position in sorted(positions, key=lambda item: item["symbol"]):
        symbol = position["symbol"]
        quantity = position["quantity"]
        market_value = position["market_value"]
        currency = position["currency"]
        total = broker_totals[currency]

        print(
            f"  {symbol:<5} {int(quantity):>6} shares   "
            f"≈ {market_value:>12,.2f} {currency}   {_pct(market_value, total):>6}%"
        )

    print()
    print("Positions value:")
    for currency in sorted(broker_totals):
        market_value = position_totals.get(currency, Decimal("0"))
        total = broker_totals[currency]
        print(f"  {currency}: {market_value:>12,.2f}   {_pct(market_value, total):>6}%")

    print("----------------------------------------")


def _pct(value: Decimal, total: Decimal) -> Decimal:
    if total == 0:
        return Decimal("0")
    return (value / total * Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _normalize_snapshot(snapshot: dict) -> tuple[dict[str, Decimal], list[dict]]:
    cash = snapshot.get("cash")
    positions = snapshot.get("positions")
    if isinstance(cash, dict) and isinstance(positions, list):
        cash_by_currency = {
            currency: Decimal(str(value)) for currency, value in cash.items()
        }
        return cash_by_currency, _normalize_positions(positions)

    portfolio = snapshot.get("portfolio", {})
    cash = portfolio.get("cash", {})
    positions = portfolio.get("positions", [])
    cash_by_currency = {
        currency: Decimal(str(value)) for currency, value in cash.items()
    }
    return cash_by_currency, _normalize_positions(positions)


def _normalize_positions(positions: list[dict]) -> list[dict]:
    normalized_positions: list[dict] = []
    for position in positions:
        normalized_position = dict(position)
        normalized_position["market_value"] = Decimal(
            str(normalized_position.get("market_value", 0))
        )
        normalized_positions.append(normalized_position)

    return normalized_positions
