from pathlib import Path

from tol.cli.handlers.execution_helpers import resolve_broker, resolve_db_path
from tol.execution.engine import ExecutionEngine
from tol.load import load_tol


def handle_run(args) -> None:
    tol_path = Path(args.file)
    tol_doc = load_tol(tol_path)
    broker_api = resolve_broker(tol_doc.get("mode"))
    engine = ExecutionEngine(resolve_db_path(), broker_api)
    execution_id = engine.start_execution(tol_doc, broker_api)
    engine.advance_execution(execution_id)
    print(execution_id)
