from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional

from tol.ibkr.gateway import IBKRGateway
from tol.parser.planner import PlannedAction


@dataclass(frozen=True)
class QuantitySpec:
    kind: str
    value: Optional[Decimal] = None


@dataclass(frozen=True)
class PortfolioPosition:
    symbol: str
    quantity: Decimal
    market_value: Decimal
    currency: str

    @property
    def price(self) -> Optional[Decimal]:
        if self.quantity == 0:
            return None
        return self.market_value / self.quantity


@dataclass(frozen=True)
class PortfolioSnapshot:
    cash_by_currency: dict[str, Decimal]
    positions_by_symbol: dict[str, PortfolioPosition]

    @property
    def total_cash(self) -> Decimal:
        return sum(self.cash_by_currency.values(), Decimal("0"))


@dataclass
class ActionEvaluation:
    action_id: str
    action_type: str
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    planned_trades: list["PlannedTrade"] = field(default_factory=list)


@dataclass(frozen=True)
class PlannedTrade:
    action_id: str
    action_type: str
    symbol: str
    quantity: Decimal
    price: Decimal
    currency: str


def normalize_quantity(quantity: object) -> Optional[QuantitySpec]:
    if quantity is None:
        return None
    if isinstance(quantity, QuantitySpec):
        return quantity
    if isinstance(quantity, int):
        return QuantitySpec(kind="shares", value=_coerce_decimal(quantity))
    if isinstance(quantity, (float, Decimal)):
        value = _coerce_decimal(quantity)
        if value > 1:
            raise ValueError("Float quantity must be <= 1.0 for percentages.")
        return QuantitySpec(kind="percent", value=value)
    if isinstance(quantity, str):
        raw = quantity.strip().upper()
        if raw == "ALL":
            return QuantitySpec(kind="all")
        if raw.endswith("%"):
            value = raw[:-1].strip()
            if not value:
                raise ValueError("Percent quantity is missing a value.")
            return QuantitySpec(
                kind="percent",
                value=_coerce_decimal(value) / Decimal("100"),
            )
        return QuantitySpec(kind="shares", value=_coerce_decimal(raw))
    raise TypeError(f"Unsupported quantity type: {type(quantity).__name__}")


def build_snapshot(
    cash_by_currency: dict[str, Decimal],
    positions: Iterable[dict[str, Decimal | str]],
) -> PortfolioSnapshot:
    positions_by_symbol: dict[str, PortfolioPosition] = {}
    for position in positions:
        symbol = str(position["symbol"])
        positions_by_symbol[symbol] = PortfolioPosition(
            symbol=symbol,
            quantity=_coerce_decimal(position["quantity"]),
            market_value=_coerce_decimal(position["market_value"]),
            currency=str(position["currency"]),
        )
    return PortfolioSnapshot(
        cash_by_currency={ccy: _coerce_decimal(amt) for ccy, amt in cash_by_currency.items()},
        positions_by_symbol=positions_by_symbol,
    )


def evaluate_actions(
    actions: Iterable[PlannedAction],
    snapshot: PortfolioSnapshot,
) -> list[ActionEvaluation]:
    evaluations: list[ActionEvaluation] = []
    for action in actions:
        evaluation = ActionEvaluation(
            action_id=action.derived_id,
            action_type=action.action_type,
        )
        if action.action_type == "sell":
            _evaluate_sell(action, snapshot, evaluation)
        elif action.action_type == "buy":
            _evaluate_buy(action, snapshot, evaluation)
        elif action.action_type == "target":
            _evaluate_target(action, snapshot, evaluation)
        else:
            evaluation.warnings.append(
                f"Unknown action type '{action.action_type}'."
            )
        evaluations.append(evaluation)
    return evaluations


def build_portfolio_report(
    snapshot: PortfolioSnapshot,
    evaluations: Iterable[ActionEvaluation],
) -> list[str]:
    lines: list[str] = []
    lines.append("Portfolio snapshot:")
    lines.append("Cash:")
    for ccy in sorted(snapshot.cash_by_currency):
        amt = snapshot.cash_by_currency[ccy]
        lines.append(f"  {ccy}: {amt:,.2f}")
    lines.append("Positions:")
    for symbol in sorted(snapshot.positions_by_symbol):
        position = snapshot.positions_by_symbol[symbol]
        lines.append(
            f"  {symbol}: {position.quantity} shares "
            f"(≈ {position.market_value:,.2f} {position.currency})"
        )
    lines.append("")
    lines.append("Dry run evaluation:")
    for evaluation in evaluations:
        lines.append(f"• {evaluation.action_id} ({evaluation.action_type})")
        for message in evaluation.messages:
            lines.append(f"  - {message}")
        for warning in evaluation.warnings:
            lines.append(f"  - WARNING: {warning}")
        for error in evaluation.errors:
            lines.append(f"  - ERROR: {error}")
    lines.append("")
    lines.append("Planned trades:")
    planned_trades = [
        trade
        for evaluation in evaluations
        for trade in evaluation.planned_trades
    ]
    if not planned_trades:
        lines.append("  (none)")
        return lines
    for trade in planned_trades:
        lines.append(
            "• "
            f"{trade.action_id} {trade.action_type.upper()} "
            f"{trade.symbol} {trade.quantity} @ "
            f"{trade.price:,.2f} {trade.currency}"
        )
    return lines


def run_portfolio_dry_run(
    actions: Iterable[PlannedAction],
    mode: str,
) -> list[str]:
    gateway = IBKRGateway(mode)
    gateway.connect()
    try:
        cash_by_currency = gateway.get_cash_by_currency()
        positions = gateway.get_positions()
    finally:
        gateway.disconnect()

    snapshot = build_snapshot(cash_by_currency, positions)
    evaluations = evaluate_actions(actions, snapshot)
    return build_portfolio_report(snapshot, evaluations)


def _evaluate_sell(
    action: PlannedAction,
    snapshot: PortfolioSnapshot,
    evaluation: ActionEvaluation,
) -> None:
    position = snapshot.positions_by_symbol.get(action.symbol)
    if not position:
        evaluation.errors.append(f"No holdings for {action.symbol}.")
        return

    quantity_spec = normalize_quantity(action.quantity)
    if quantity_spec is None:
        evaluation.errors.append("Sell action missing quantity.")
        return

    required_qty = _resolve_quantity(quantity_spec, position.quantity)
    if required_qty is None:
        evaluation.errors.append("Unable to resolve sell quantity.")
        return

    if required_qty > position.quantity:
        evaluation.errors.append(
            f"Requested {required_qty} shares exceeds holding of {position.quantity}."
        )
    else:
        evaluation.messages.append(
            f"Sell {required_qty} shares from {position.quantity} held."
        )

    if position.price is None:
        evaluation.warnings.append("Unable to determine price for sell valuation.")
    else:
        evaluation.messages.append(
            f"Estimated proceeds: {required_qty * position.price:,.2f} {position.currency}."
        )
        if not evaluation.errors:
            evaluation.planned_trades.append(
                PlannedTrade(
                    action_id=action.derived_id,
                    action_type="sell",
                    symbol=action.symbol,
                    quantity=required_qty,
                    price=position.price,
                    currency=position.currency,
                )
            )


def _evaluate_buy(
    action: PlannedAction,
    snapshot: PortfolioSnapshot,
    evaluation: ActionEvaluation,
) -> None:
    quantity_spec = normalize_quantity(action.quantity)
    if quantity_spec is None:
        evaluation.errors.append("Buy action missing quantity.")
        return

    available_value = Decimal("0")
    missing_sources: list[str] = []
    unresolved_sources: list[str] = []
    expected_currency = _resolve_expected_currency(action, snapshot)
    cash_warning_emitted = False

    for source, source_type in action.using_classified or []:
        if source_type == "cash":
            cash_value, warning = _resolve_cash_value(snapshot, expected_currency)
            available_value += cash_value
            if warning and not cash_warning_emitted:
                evaluation.warnings.append(warning)
                cash_warning_emitted = True
        elif source_type == "holding":
            position = snapshot.positions_by_symbol.get(source)
            if position:
                available_value += position.market_value
            else:
                missing_sources.append(source)
        elif source_type == "action":
            unresolved_sources.append(source)

    if missing_sources:
        evaluation.errors.append(
            "Missing holdings for sources: " + ", ".join(missing_sources)
        )

    if unresolved_sources:
        evaluation.warnings.append(
            "Cannot value action sources yet: " + ", ".join(unresolved_sources)
        )

    evaluation.messages.append(
        f"Available value from sources: {available_value:,.2f}."
    )

    price = None
    position = snapshot.positions_by_symbol.get(action.symbol)
    if position:
        price = position.price

    required_value, required_shares = _resolve_buy_requirements(
        quantity_spec, available_value, price
    )

    if required_value is not None:
        evaluation.messages.append(
            f"Estimated spend: {required_value:,.2f}."
        )
        if required_value > available_value:
            evaluation.errors.append(
                "Insufficient value to satisfy buy quantity."
            )

    if required_shares is not None:
        evaluation.messages.append(
            f"Estimated shares: {required_shares}."
        )
        if price is not None and not evaluation.errors:
            evaluation.planned_trades.append(
                PlannedTrade(
                    action_id=action.derived_id,
                    action_type="buy",
                    symbol=action.symbol,
                    quantity=required_shares,
                    price=price,
                    currency=(
                        expected_currency
                        or (position.currency if position else "USD")
                    ),
                )
            )
    elif price is None:
        evaluation.warnings.append(
            "Unable to estimate shares without a market price."
        )


def _evaluate_target(
    action: PlannedAction,
    snapshot: PortfolioSnapshot,
    evaluation: ActionEvaluation,
) -> None:
    if action.percent is None:
        evaluation.errors.append("Target action missing percent.")
        return

    percent = _coerce_decimal(action.percent) / Decimal("100")
    total_value = Decimal("0")
    missing_sources: list[str] = []
    invalid_sources: list[str] = []

    for source, source_type in action.using_classified or []:
        if source_type == "cash":
            total_value += snapshot.total_cash
        elif source_type == "holding":
            position = snapshot.positions_by_symbol.get(source)
            if position:
                total_value += position.market_value
            else:
                missing_sources.append(source)
        else:
            invalid_sources.append(source)

    if missing_sources:
        evaluation.errors.append(
            "Missing holdings for sources: " + ", ".join(missing_sources)
        )
    if invalid_sources:
        evaluation.errors.append(
            "Targets cannot depend on actions: " + ", ".join(invalid_sources)
        )

    desired_value = total_value * percent
    current_position = snapshot.positions_by_symbol.get(action.symbol)
    current_value = current_position.market_value if current_position else Decimal("0")
    delta = desired_value - current_value

    evaluation.messages.append(
        f"Target value: {desired_value:,.2f}; current value: {current_value:,.2f}."
    )

    price = current_position.price if current_position else None
    if price:
        shares = delta / price
        direction = "buy" if delta > 0 else "sell"
        evaluation.messages.append(
            f"Implied {direction} of {shares:.4f} shares."
        )
        if shares != 0 and not evaluation.errors:
            evaluation.planned_trades.append(
                PlannedTrade(
                    action_id=action.derived_id,
                    action_type=direction,
                    symbol=action.symbol,
                    quantity=abs(shares),
                    price=price,
                    currency=current_position.currency if current_position else "USD",
                )
            )
    else:
        evaluation.warnings.append(
            "Unable to estimate target shares without a market price."
        )


def _resolve_quantity(
    quantity_spec: QuantitySpec,
    available_qty: Decimal,
) -> Optional[Decimal]:
    if quantity_spec.kind == "all":
        return available_qty
    if quantity_spec.kind == "shares" and quantity_spec.value is not None:
        return quantity_spec.value
    if quantity_spec.kind == "percent" and quantity_spec.value is not None:
        return available_qty * quantity_spec.value
    return None


def _resolve_buy_requirements(
    quantity_spec: QuantitySpec,
    available_value: Decimal,
    price: Optional[Decimal],
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    if quantity_spec.kind == "all":
        if price is None:
            return available_value, None
        return available_value, available_value / price
    if quantity_spec.kind == "percent" and quantity_spec.value is not None:
        required_value = available_value * quantity_spec.value
        if price is None:
            return required_value, None
        return required_value, required_value / price
    if quantity_spec.kind == "shares" and quantity_spec.value is not None:
        if price is None:
            return None, quantity_spec.value
        return quantity_spec.value * price, quantity_spec.value
    return None, None


def _coerce_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid numeric value: {value}") from exc


def _resolve_expected_currency(
    action: PlannedAction,
    snapshot: PortfolioSnapshot,
) -> Optional[str]:
    position = snapshot.positions_by_symbol.get(action.symbol)
    if position:
        return position.currency
    if len(snapshot.cash_by_currency) == 1:
        return next(iter(snapshot.cash_by_currency.keys()))
    return None


def _resolve_cash_value(
    snapshot: PortfolioSnapshot,
    expected_currency: Optional[str],
) -> tuple[Decimal, Optional[str]]:
    if expected_currency is None:
        return snapshot.total_cash, (
            "Using total cash across currencies; no conversion applied."
        )
    cash_value = snapshot.cash_by_currency.get(expected_currency, Decimal("0"))
    if len(snapshot.cash_by_currency) > 1:
        warning = (
            f"Using cash in {expected_currency} only; other currencies are ignored."
        )
    else:
        warning = None
    return cash_value, warning
