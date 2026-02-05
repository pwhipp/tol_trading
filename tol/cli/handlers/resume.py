from tol.cli.handlers.execution_helpers import (
    find_active_execution_id,
    lookup_execution_mode,
    get_broker_api,
    resolve_db_path,
)
from tol.cli.handlers.status import render_status
from tol.config import get_config
from tol.execution.engine import ExecutionEngine


def handle_resume(args) -> None:
    db_path = resolve_db_path()
    active_id = find_active_execution_id(db_path)
    if active_id is None:
        print("No active execution.")
        return
    mode = lookup_execution_mode(db_path, active_id)
    broker_api = get_broker_api(mode)
    config = get_config()
    engine = ExecutionEngine(db_path, broker_api, tif=config.tif)
    engine.advance_execution(active_id)
    status = engine.get_status(active_id)
    print(render_status(status))
