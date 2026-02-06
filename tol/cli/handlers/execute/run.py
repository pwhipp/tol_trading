from __future__ import annotations

import sys
from argparse import Namespace
from decimal import Decimal, InvalidOperation
from typing import Any

from tabulate import tabulate

from tol.cli.handlers.execute.status import render_status
from tol.cli.handlers.helpers.execution import get_broker_api, resolve_db_path
from tol.config import get_config
from tol.execution.engine import ExecutionEngine
from tol.load import load_tol_text
from tol.parser.planner import PlannedAction, plan_actions


def handle_execute_run(args: Namespace) -> None:
    tol_text = sys.stdin.read()
    if not tol_text.strip():
        print("ERROR: No TOL document provided on stdin.", file=sys.stderr)
        sys.exit(1)

    try:
        tol_doc = load_tol_text(tol_text)
    except ValueError as exc:
        print(f"ERROR: Failed to parse TOL document: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(_render_dry_run_table(tol_doc))
        return

    config = get_config()
    broker_api = get_broker_api(tol_doc.get("mode"))
    engine = ExecutionEngine(resolve_db_path(), broker_api, tif=config.tif)
    execution_id = engine.start_execution(tol_doc, broker_api)
    engine.advance_execution(execution_id)
    status = engine.get_status(execution_id)
    print(render_status(status))


def _render_dry_run_table(tol_document: dict[str, Any]) -> str:
    config = get_config()
    planned_actions = plan_actions(tol_document)
    rows = [_to_dry_run_row(action, config.tif) for action in planned_actions]
    return tabulate(
        rows,
        headers=["Action", "Symbol", "Quantity", "TIF", "Would Submit"],
        tablefmt="github",
    )


def _to_dry_run_row(action: PlannedAction, tif: str | None) -> list[str]:
    quantity = _resolve_quantity_display(action)
    symbol = action.symbol or "-"
    return [
        action.derived_id,
        symbol,
        quantity,
        _normalize_tif(tif),
        _would_submit_display(action),
    ]


def _resolve_quantity_display(action: PlannedAction) -> str:
    if action.action_type == "fx":
        return "-"
    if action.quantity is None:
        return "ERROR"
    try:
        quantity = Decimal(str(action.quantity))
    except (InvalidOperation, ValueError):
        return "ERROR"
    if quantity <= 0:
        return "ERROR"
    return str(quantity)


def _would_submit_display(action: PlannedAction) -> str:
    if action.action_type == "fx":
        return "no"
    if _resolve_quantity_display(action) == "ERROR":
        return "no"
    return "yes"


def _normalize_tif(tif: str | None) -> str:
    normalized = str(tif).strip().upper() if tif is not None else ""
    return normalized or "GTC"
