from tol.cli.handlers.helpers.execution import (
    find_active_execution_id,
    get_broker_api,
    lookup_execution_mode,
    resolve_db_path,
)
from tol.execution.engine import ExecutionEngine


def handle_execute_cancel(args) -> None:
    db_path = resolve_db_path()
    execution_id = args.execution_id or find_active_execution_id(db_path)
    if execution_id is None:
        print("No execution found.")
        return
    mode = lookup_execution_mode(db_path, execution_id)
    broker_api = get_broker_api(mode)
    engine = ExecutionEngine(db_path, broker_api)
    engine.cancel_execution(execution_id)
    print(execution_id)
