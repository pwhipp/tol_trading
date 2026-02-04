import json

import yaml

from tol.cli.handlers.execution_helpers import (
    find_active_execution_id,
    lookup_execution_mode,
    get_broker_api,
    resolve_db_path,
)
from tol.execution.engine import ExecutionEngine


def handle_status(args) -> None:
    db_path = resolve_db_path()
    execution_id = args.execution_id or find_active_execution_id(db_path)
    if execution_id is None:
        print("No execution found.")
        return
    mode = lookup_execution_mode(db_path, execution_id)
    if mode is None:
        print("No execution found.")
        return
    broker_api = get_broker_api(mode)
    engine = ExecutionEngine(db_path, broker_api)
    status = engine.get_status(execution_id)
    print(
        yaml.safe_dump(
            _format_status_payload(status),
            sort_keys=False,
        )
    )


def _format_status_payload(status) -> dict:
    execution = dict(status.execution)
    tol_document = _parse_json_mapping(execution.get("tol_document_json"))
    if tol_document is not None:
        execution.pop("tol_document_json", None)
        execution["tol_document"] = tol_document

    orders = []
    for order in status.orders:
        order_row = dict(order)
        trade_payload = _parse_json_mapping(order_row.get("trade_json"))
        if trade_payload is not None:
            order_row.pop("trade_json", None)
            order_row["trade"] = trade_payload
        orders.append(order_row)

    return {
        "execution": execution,
        "actions": status.actions,
        "orders": orders,
        "fills": status.fills,
    }


def _parse_json_mapping(value) -> dict | None:
    if not value or not isinstance(value, str):
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None
