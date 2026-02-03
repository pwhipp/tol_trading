import json

from tol.cli.handlers.execution_helpers import (
    find_active_execution_id,
    lookup_execution_mode,
    resolve_broker,
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
    broker_api = resolve_broker(mode)
    engine = ExecutionEngine(db_path, broker_api)
    status = engine.get_status(execution_id)
    print(
        json.dumps(
            {
                "execution": status.execution,
                "actions": status.actions,
                "orders": status.orders,
                "fills": status.fills,
            },
            indent=2,
        )
    )
