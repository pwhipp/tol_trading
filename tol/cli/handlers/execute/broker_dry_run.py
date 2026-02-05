from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re
from typing import Callable, Iterable, Optional, Protocol

from tol.ibkr.gateway import IBKRGateway
from tol.exchange import resolve_exchange_currency
from tol.cli.handlers.helpers.pending_trades import (
    PendingTrade,
    format_pending_trade,
    normalize_pending_trades,
)
from tol.parser.planner import PlannedAction


class BrokerGateway(Protocol):
    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def qualify_stock_contract(
        self,
        symbol: str,
        currency: str = "USD",
        exchange: str = "SMART",
    ) -> object: ...

    def validate_order(
        self,
        contract: object,
        action_type: str,
        quantity: Decimal,
    ) -> dict: ...

    def get_market_snapshot(self, contract: object) -> dict: ...

    def get_cash_by_currency(self) -> dict[str, Decimal]: ...

    def get_pending_trades(self) -> list[dict]: ...


@dataclass
class BrokerValidation:
    action_id: str
    action_type: str
    symbol: str
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


def run_broker_dry_run(
    actions: Iterable[PlannedAction],
    mode: str,
    gateway_factory: Callable[[str], BrokerGateway] = IBKRGateway,
) -> list[str]:
    gateway = gateway_factory(mode)
    gateway.connect()
    try:
        pending_trades = normalize_pending_trades(gateway.get_pending_trades())
        results = [
            validate_action_with_broker(
                action,
                gateway,
                pending_trades=pending_trades,
            )
            for action in actions
        ]
    finally:
        gateway.disconnect()
    return build_broker_report(results)


def build_broker_report(
    results: Iterable[BrokerValidation],
) -> list[str]:
    lines: list[str] = []
    lines.append("Broker dry run evaluation:")
    for result in results:
        lines.append(f"• {result.action_id} ({result.action_type})")
        for message in result.messages:
            lines.append(f"  - {message}")
        for warning in result.warnings:
            lines.append(f"  - WARNING: {warning}")
        for error in result.errors:
            lines.append(f"  - ERROR: {error}")
    lines.append("")
    lines.append("Planned trades:")
    planned_trades = [
        trade
        for result in results
        for trade in result.planned_trades
    ]
    if not planned_trades:
        lines.append("  (none)")
        return lines
    for trade in planned_trades:
        lines.append(
            "• "
            f"{trade.action_id} {trade.action_type.upper()} "
            f"{trade.symbol} {_format_quantity(trade.quantity)} @ "
            f"{trade.price:,.2f} {trade.currency}"
        )
    return lines


def validate_action_with_broker(
    action: PlannedAction,
    gateway: BrokerGateway,
    pending_trades: Optional[list[PendingTrade]] = None,
) -> BrokerValidation:
    validation = BrokerValidation(
        action_id=action.derived_id,
        action_type=action.action_type,
        symbol=action.symbol,
    )
    normalized_pending = normalize_pending_trades(pending_trades)

    if action.action_type == "fx":
        _validate_fx_action(
            action,
            gateway,
            normalized_pending,
            validation,
        )
        return validation

    sanitized_symbol = _sanitize_symbol(action.symbol, validation)
    if sanitized_symbol is None:
        return validation

    contract = _resolve_contract(gateway, sanitized_symbol, validation)
    if contract is None:
        return validation

    _append_pending_trade_warnings(action, validation, normalized_pending)

    if action.action_type in {"buy", "sell"}:
        if not _validate_using_currency(action, validation):
            return validation
        market_snapshot = _resolve_market_snapshot(
            gateway,
            contract,
            validation,
        )
        quantity = _resolve_share_quantity(
            action,
            gateway,
            market_snapshot,
            validation,
            pending_trades=normalized_pending,
        )
        if quantity is None:
            return validation
        _validate_order_with_gateway(
            gateway,
            contract,
            action.action_type,
            quantity,
            validation,
        )
        if market_snapshot:
            _append_planned_trade(
                action,
                quantity,
                market_snapshot,
                validation,
            )
    elif action.action_type == "target":
        if not _validate_using_currency(action, validation):
            return validation
        validation.warnings.append(
            "Target actions require portfolio context to derive shares."
        )
    else:
        validation.warnings.append(
            f"Unknown action type '{action.action_type}'."
        )

    return validation


def _sanitize_symbol(
    symbol: object,
    validation: BrokerValidation,
) -> Optional[str]:
    if not isinstance(symbol, str):
        validation.errors.append("Symbol must be a string.")
        return None
    sanitized = symbol.strip().upper()
    if not sanitized:
        validation.errors.append("Symbol cannot be empty.")
        return None
    return sanitized


def _resolve_contract(
    gateway: BrokerGateway,
    symbol: str,
    validation: BrokerValidation,
) -> Optional[object]:
    try:
        contract = gateway.qualify_stock_contract(symbol)
    except Exception as exc:  # pragma: no cover - defensive for broker errors
        validation.errors.append(f"Failed to resolve contract: {exc}.")
        return None
    if not contract:
        validation.errors.append("Unable to resolve broker contract.")
        return None
    validation.messages.append(f"Resolved contract for {symbol}.")
    return contract


def _resolve_share_quantity(
    action: PlannedAction,
    gateway: BrokerGateway,
    market_snapshot: Optional[dict],
    validation: BrokerValidation,
    pending_trades: Optional[list[PendingTrade]] = None,
) -> Optional[Decimal]:
    quantity = action.quantity
    if quantity is None:
        validation.errors.append("Order quantity is required for broker validation.")
        return None
    if isinstance(quantity, (int, Decimal)):
        return _coerce_decimal(quantity, validation)
    if isinstance(quantity, float):
        if quantity > 1:
            return _coerce_decimal(quantity, validation)
        return _resolve_percent_quantity(
            action,
            gateway,
            Decimal(str(quantity)),
            market_snapshot,
            validation,
            pending_trades=pending_trades,
        )
    if isinstance(quantity, str):
        raw = quantity.strip().upper()
        if raw == "ALL":
            return _resolve_percent_quantity(
                action,
                gateway,
                Decimal("1"),
                market_snapshot,
                validation,
                pending_trades=pending_trades,
            )
        if raw.endswith("%"):
            value = raw[:-1].strip()
            if not value:
                validation.errors.append("Percent quantity is missing a value.")
                return None
            percent = _coerce_decimal(value, validation)
            if percent is None:
                return None
            return _resolve_percent_quantity(
                action,
                gateway,
                percent / Decimal("100"),
                market_snapshot,
                validation,
                pending_trades=pending_trades,
            )
        return _coerce_decimal(raw, validation)
    validation.errors.append("Unsupported quantity type.")
    return None


def _resolve_market_snapshot(
    gateway: BrokerGateway,
    contract: object,
    validation: BrokerValidation,
) -> Optional[dict]:
    try:
        snapshot = gateway.get_market_snapshot(contract)
    except Exception as exc:  # pragma: no cover - broker issues
        validation.warnings.append(f"Failed to retrieve market price: {exc}.")
        return None
    price = snapshot.get("price") if isinstance(snapshot, dict) else None
    if price is None:
        validation.warnings.append("Market price unavailable for trade preview.")
        return None
    is_open = snapshot.get("is_open") if isinstance(snapshot, dict) else None
    if is_open is False:
        validation.warnings.append(
            "Market appears closed; using last known price."
        )
    currency = snapshot.get("currency") if isinstance(snapshot, dict) else None
    snapshot["currency"] = currency or "USD"
    return snapshot


def _resolve_percent_quantity(
    action: PlannedAction,
    gateway: BrokerGateway,
    percent: Decimal,
    market_snapshot: Optional[dict],
    validation: BrokerValidation,
    pending_trades: Optional[list[PendingTrade]] = None,
) -> Optional[Decimal]:
    if action.action_type != "buy":
        validation.warnings.append(
            "Percent quantities for sells need portfolio context; "
            "broker validation skipped."
        )
        return None
    if market_snapshot is None or market_snapshot.get("price") is None:
        validation.warnings.append(
            "Market price unavailable; cannot resolve percent quantity."
        )
        return None
    expected_currency = market_snapshot.get("currency")
    cash_by_currency = _apply_pending_trades_to_cash(
        gateway.get_cash_by_currency(),
        pending_trades or [],
        validation,
    )
    cash_value, warning = _resolve_cash_value(cash_by_currency, expected_currency)
    if warning:
        validation.warnings.append(warning)
    if cash_value <= 0:
        validation.errors.append("No cash available to satisfy percent quantity.")
        return None
    return (cash_value * percent) / market_snapshot["price"]


def _apply_pending_trades_to_cash(
    cash_by_currency: dict[str, Decimal],
    pending_trades: list[PendingTrade],
    validation: BrokerValidation,
) -> dict[str, Decimal]:
    if not pending_trades:
        return cash_by_currency
    adjusted_cash = dict(cash_by_currency)
    for trade in pending_trades:
        if trade.price is None:
            validation.warnings.append(
                f"Pending {trade.action_type} {trade.symbol} lacks pricing; "
                "cash impact not applied."
            )
            continue
        if trade.action_type == "buy":
            currency = trade.currency or "USD"
            cash_delta = trade.price * trade.quantity
            adjusted_cash[currency] = (
                adjusted_cash.get(currency, Decimal("0")) - cash_delta
            )
    return adjusted_cash


def _append_pending_trade_warnings(
    action: PlannedAction,
    validation: BrokerValidation,
    pending_trades: list[PendingTrade],
) -> None:
    action_symbol = str(action.symbol).strip().upper()
    conflicts = [
        trade
        for trade in pending_trades
        if trade.symbol == action_symbol and _is_overlapping_trade(action, trade)
    ]
    for trade in conflicts:
        validation.warnings.append(
            "Pending trade overlap: " + format_pending_trade(trade) + "."
        )


def _is_overlapping_trade(action: PlannedAction, trade: PendingTrade) -> bool:
    if action.action_type == "target":
        return True
    return action.action_type in {"buy", "sell"}


def _resolve_cash_value(
    cash_by_currency: dict[str, Decimal],
    expected_currency: Optional[str],
) -> tuple[Decimal, Optional[str]]:
    total_cash = sum(cash_by_currency.values(), Decimal("0"))
    if expected_currency is None:
        return total_cash, (
            "Using total cash across currencies; no conversion applied."
        )
    cash_value = cash_by_currency.get(expected_currency, Decimal("0"))
    if len(cash_by_currency) > 1:
        warning = (
            f"Using cash in {expected_currency} only; other currencies are ignored."
        )
    else:
        warning = None
    return cash_value, warning


def _append_planned_trade(
    action: PlannedAction,
    quantity: Decimal,
    snapshot: dict,
    validation: BrokerValidation,
) -> None:
    if validation.errors:
        return
    validation.planned_trades.append(
        PlannedTrade(
            action_id=action.derived_id,
            action_type=action.action_type,
            symbol=action.symbol,
            quantity=quantity,
            price=snapshot["price"],
            currency=snapshot["currency"],
        )
    )


def _format_quantity(value: Decimal) -> str:
    if value == value.to_integral_value():
        return f"{value:,.0f}"
    return f"{value:,.4f}".rstrip("0").rstrip(".")


def _validate_using_currency(
    action: PlannedAction,
    validation: BrokerValidation,
) -> bool:
    if action.action_type not in {"buy", "target"}:
        return True
    expected_currency = _resolve_exchange_currency(action.symbol)
    if not expected_currency:
        return True
    cash_currencies = [
        currency
        for source, source_type in action.using_classified or []
        if source_type == "cash"
        for currency in [_extract_cash_currency(source)]
        if currency
    ]
    for currency in cash_currencies:
        if currency != expected_currency:
            validation.errors.append(
                "Using cash in "
                f"{currency} does not match exchange currency {expected_currency}."
            )
            return False
    return True


def _extract_cash_currency(source: str) -> Optional[str]:
    match = re.fullmatch(r"CASH \(([A-Z]{3})\)", source)
    if not match:
        return None
    return match.group(1)


def _resolve_exchange_currency(symbol: str) -> Optional[str]:
    if "." not in symbol:
        return None
    _, exchange = symbol.rsplit(".", 1)
    return resolve_exchange_currency(exchange)


def _validate_fx_action(
    action: PlannedAction,
    gateway: BrokerGateway,
    pending_trades: list[PendingTrade],
    validation: BrokerValidation,
) -> None:
    source = _parse_currency_code(action.from_currency)
    destination = _parse_currency_code(action.to_currency)
    if not source:
        validation.errors.append("FX actions require a source currency.")
        return
    if not destination:
        validation.errors.append("FX actions require a destination currency.")
        return
    if destination == source:
        validation.errors.append(
            "FX destination must differ from the source currency."
        )
        return
    cash_by_currency = _apply_pending_trades_to_cash(
        gateway.get_cash_by_currency(),
        pending_trades,
        validation,
    )
    available = cash_by_currency.get(source, Decimal("0"))
    amount = _resolve_fx_quantity(
        action.quantity,
        source,
        available,
        validation,
    )
    if amount is None:
        return
    validation.messages.append(
        f"Convert {amount:,.2f} {source} to {destination}."
    )


def _parse_money(
    value: str,
    validation: BrokerValidation,
) -> Optional[tuple[Decimal, str]]:
    match = re.fullmatch(
        r"(?P<symbol>[$€£¥])\s*(?P<amount>[0-9][0-9,]*"
        r"(?:\.[0-9]{1,2})?)\s*\((?P<ccy>[A-Za-z]{3})\)",
        value.strip(),
    )
    if not match:
        validation.errors.append("FX quantity must be formatted as $1,000 (USD).")
        return None
    amount_text = match.group("amount").replace(",", "")
    currency = match.group("ccy").upper()
    amount = _coerce_decimal(amount_text, validation)
    if amount is None:
        return None
    if amount <= 0:
        validation.errors.append("FX quantity must be positive.")
        return None
    return amount, currency


def _parse_currency_code(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    match = re.fullmatch(r"[A-Z]{3}", value.strip().upper())
    if not match:
        return None
    return match.group(0)


def _resolve_fx_quantity(
    quantity: object,
    source_currency: str,
    available_cash: Decimal,
    validation: BrokerValidation,
) -> Optional[Decimal]:
    if quantity is None:
        validation.errors.append("FX actions require a quantity.")
        return None
    if isinstance(quantity, str):
        parsed = _parse_money(quantity, validation)
        if parsed is not None:
            amount, currency = parsed
            if currency != source_currency:
                validation.errors.append(
                    "FX quantity currency must match the source currency."
                )
                return None
            return _validate_fx_amount(amount, source_currency, available_cash, validation)
        raw = quantity.strip().replace(",", "")
        if raw.upper() == "ALL":
            return _validate_fx_amount(
                available_cash,
                source_currency,
                available_cash,
                validation,
            )
        if raw.endswith("%"):
            value = raw[:-1].strip()
            if not value:
                validation.errors.append("Percent quantity is missing a value.")
                return None
            percent = _coerce_decimal(value, validation)
            if percent is None:
                return None
            amount = available_cash * (percent / Decimal("100"))
            return _validate_fx_amount(
                amount,
                source_currency,
                available_cash,
                validation,
            )
        amount = _coerce_decimal(raw, validation)
        if amount is None:
            return None
        return _validate_fx_amount(
            amount,
            source_currency,
            available_cash,
            validation,
        )
    if isinstance(quantity, (int, float, Decimal)):
        amount = _coerce_decimal(quantity, validation)
        if amount is None:
            return None
        return _validate_fx_amount(
            amount,
            source_currency,
            available_cash,
            validation,
        )
    validation.errors.append("Unsupported FX quantity type.")
    return None


def _validate_fx_amount(
    amount: Decimal,
    currency: str,
    available_cash: Decimal,
    validation: BrokerValidation,
) -> Optional[Decimal]:
    if amount <= 0:
        validation.errors.append("FX quantity must be positive.")
        return None
    if amount > available_cash:
        validation.errors.append(
            f"Insufficient {currency} cash to convert {amount:,.2f}."
        )
        return None
    return amount


def _coerce_decimal(
    value: object,
    validation: BrokerValidation,
) -> Optional[Decimal]:
    try:
        if isinstance(value, str):
            value = value.replace(",", "")
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        validation.errors.append(f"Invalid numeric value: {value}.")
        return None


def _validate_order_with_gateway(
    gateway: BrokerGateway,
    contract: object,
    action_type: str,
    quantity: Decimal,
    validation: BrokerValidation,
) -> None:
    if quantity <= 0:
        validation.errors.append("Order quantity must be positive.")
        return
    try:
        result = gateway.validate_order(contract, action_type, quantity)
    except Exception as exc:  # pragma: no cover - broker issues
        validation.errors.append(f"Broker validation failed: {exc}.")
        return

    status = result.get("status") if isinstance(result, dict) else None
    if status:
        validation.messages.append(f"Broker validation status: {status}.")
    else:
        validation.messages.append("Broker validation completed.")
