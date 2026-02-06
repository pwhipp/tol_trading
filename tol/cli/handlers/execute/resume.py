from tol.cli.handlers.execute.status import render_status
from tol.cli.handlers.helpers.execution import (
    find_active_execution_id,
    get_broker_api,
    lookup_execution_mode,
    resolve_db_path,
)
from tol.config import get_config
from tol.execution.engine import ExecutionEngine


def handle_execute_resume(args) -> None:
    del args
    db_path = resolve_db_path()
    active_id = find_active_execution_id(db_path)
    if active_id is None:
        print("No active execution.")
        return
    mode = lookup_execution_mode(db_path, active_id)
    broker_api = get_broker_api(mode)
    config = get_config()
    engine = ExecutionEngine(db_path, broker_api, tif=config.execution.tif)
    engine.advance_execution(active_id)
    status = engine.get_status(active_id)
    print(render_status(status))
