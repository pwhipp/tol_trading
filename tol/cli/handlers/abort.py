from tol.cli.handlers.execution_helpers import (
    find_active_execution_id,
    lookup_execution_mode,
    get_broker_api,
    resolve_db_path,
)
from tol.execution.engine import ExecutionEngine


def handle_abort(args) -> None:
    db_path = resolve_db_path()
    execution_id = args.execution_id or find_active_execution_id(db_path)
    if execution_id is None:
        print("No execution found.")
        return
    mode = lookup_execution_mode(db_path, execution_id)
    broker_api = get_broker_api(mode)
    engine = ExecutionEngine(db_path, broker_api)
    engine.abort_execution(execution_id)
    print(execution_id)
