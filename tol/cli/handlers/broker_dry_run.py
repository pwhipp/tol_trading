from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Callable, Iterable, Optional, Protocol

from tol.ibkr.gateway import IBKRGateway
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


@dataclass
class BrokerValidation:
    action_id: str
    action_type: str
    symbol: str
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_broker_dry_run(
    actions: Iterable[PlannedAction],
    mode: str,
    gateway_factory: Callable[[str], BrokerGateway] = IBKRGateway,
) -> list[str]:
    gateway = gateway_factory(mode)
    gateway.connect()
    try:
        results = [validate_action_with_broker(action, gateway) for action in actions]
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
    return lines


def validate_action_with_broker(
    action: PlannedAction,
    gateway: BrokerGateway,
) -> BrokerValidation:
    validation = BrokerValidation(
        action_id=action.derived_id,
        action_type=action.action_type,
        symbol=action.symbol,
    )

    sanitized_symbol = _sanitize_symbol(action.symbol, validation)
    if sanitized_symbol is None:
        return validation

    contract = _resolve_contract(gateway, sanitized_symbol, validation)
    if contract is None:
        return validation

    if action.action_type in {"buy", "sell"}:
        quantity = _resolve_share_quantity(action.quantity, validation)
        if quantity is None:
            return validation
        _validate_order_with_gateway(
            gateway,
            contract,
            action.action_type,
            quantity,
            validation,
        )
    elif action.action_type == "target":
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
    quantity: object,
    validation: BrokerValidation,
) -> Optional[Decimal]:
    if quantity is None:
        validation.errors.append("Order quantity is required for broker validation.")
        return None
    if isinstance(quantity, (int, Decimal)):
        return _coerce_decimal(quantity, validation)
    if isinstance(quantity, float):
        validation.warnings.append(
            "Float quantity interpreted as percent; broker validation skipped."
        )
        return None
    if isinstance(quantity, str):
        raw = quantity.strip().upper()
        if raw == "ALL" or raw.endswith("%"):
            validation.warnings.append(
                "Percent/ALL quantities need portfolio context; "
                "broker validation skipped."
            )
            return None
        return _coerce_decimal(raw, validation)
    validation.errors.append("Unsupported quantity type.")
    return None


def _coerce_decimal(
    value: object,
    validation: BrokerValidation,
) -> Optional[Decimal]:
    try:
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
