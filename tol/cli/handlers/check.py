from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP


def pct(value: Decimal, total: Decimal) -> Decimal:
    if total == 0:
        return Decimal("0")
    return (value / total * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def handle_check(args) -> None:
    from tol.ibkr.gateway import IBKRGateway
    from tol.cli.handlers.pending_trades import normalize_pending_trades
    from tol.cli.handlers.portfolio_dry_run import (
        apply_pending_trades,
        build_snapshot,
        PortfolioSnapshot,
    )

    gw = IBKRGateway(args.mode)

    print("TOL Portfolio Check")
    print("----------------------------------------")
    print(f"Mode: {args.mode}")
    print()

    gw.connect()
    try:
        cash_by_ccy = gw.get_cash_by_currency()
        positions = gw.get_positions()
        pending_trades = gw.get_pending_trades()
    finally:
        gw.disconnect()

    snapshot = build_snapshot(cash_by_ccy, positions)
    normalized_orders = normalize_pending_trades(pending_trades)
    amended_snapshot, _ = apply_pending_trades(snapshot, normalized_orders)

    position_totals = _build_position_totals(snapshot)
    amended_position_totals = _build_position_totals(amended_snapshot)

    portfolio_totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    for ccy, amt in snapshot.cash_by_currency.items():
        portfolio_totals[ccy] += amt
    for ccy, amt in position_totals.items():
        portfolio_totals[ccy] += amt

    amended_totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    for ccy, amt in amended_snapshot.cash_by_currency.items():
        amended_totals[ccy] += amt
    for ccy, amt in amended_position_totals.items():
        amended_totals[ccy] += amt

    print("Cash:")
    cash_currencies = set(snapshot.cash_by_currency) | set(
        amended_snapshot.cash_by_currency
    )
    for ccy in sorted(cash_currencies):
        amt = snapshot.cash_by_currency.get(ccy, Decimal("0"))
        amended_amt = amended_snapshot.cash_by_currency.get(ccy, Decimal("0"))
        total = portfolio_totals[ccy]
        amended_total = amended_totals[ccy]
        line = (
            f"  {ccy}: {amt:>12,.2f}   "
            f"{pct(amt, total):>6}%"
        )
        if amended_amt != amt:
            line += (
                f" ({amended_amt:>12,.2f} "
                f"{pct(amended_amt, amended_total):>6}%)"
            )
        print(line)

    print()
    print("Positions:")
    symbols = set(snapshot.positions_by_symbol) | set(
        amended_snapshot.positions_by_symbol
    )
    for symbol in sorted(symbols):
        position = snapshot.positions_by_symbol.get(symbol)
        amended_position = amended_snapshot.positions_by_symbol.get(symbol)

        if position:
            sym = position.symbol
            qty = position.quantity
            mv = position.market_value
            ccy = position.currency
            total = portfolio_totals[ccy]
            line = (
                f"  {sym:<5} "
                f"{int(qty):>6} shares   "
                f"≈ {mv:>12,.2f} {ccy}   "
                f"{pct(mv, total):>6}%"
            )
            if amended_position:
                amended_qty = amended_position.quantity
                amended_mv = amended_position.market_value
                amended_ccy = amended_position.currency
                amended_total = amended_totals[amended_ccy]
                if amended_mv != mv or amended_qty != qty:
                    line += (
                        f" ({int(amended_qty):>6} shares "
                        f"≈ {amended_mv:>12,.2f} {amended_ccy} "
                        f"{pct(amended_mv, amended_total):>6}%)"
                    )
            print(line)
        elif amended_position:
            amended_qty = amended_position.quantity
            amended_mv = amended_position.market_value
            amended_ccy = amended_position.currency
            amended_total = amended_totals[amended_ccy]
            print(
                f"  ({symbol:<5} "
                f"{int(amended_qty):>6} shares   "
                f"≈ {amended_mv:>12,.2f} {amended_ccy}   "
                f"{pct(amended_mv, amended_total):>6}%)"
            )

    print()
    print("Positions value:")
    currencies = set(portfolio_totals) | set(amended_totals)
    for ccy in sorted(currencies):
        mv = position_totals.get(ccy, Decimal("0"))
        total = portfolio_totals[ccy]
        amended_mv = amended_position_totals.get(ccy, Decimal("0"))
        amended_total = amended_totals[ccy]
        line = f"  {ccy}: {mv:>12,.2f}   {pct(mv, total):>6}%"
        if amended_mv != mv:
            line += (
                f" ({amended_mv:>12,.2f} "
                f"{pct(amended_mv, amended_total):>6}%)"
            )
        print(line)

    print("----------------------------------------")


def _build_position_totals(
    snapshot: "PortfolioSnapshot",
) -> defaultdict[str, Decimal]:
    totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    for position in snapshot.positions_by_symbol.values():
        totals[position.currency] += position.market_value
    return totals
