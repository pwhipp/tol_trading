import sys

from tol.cli.handlers.execution_helpers import get_broker_api, resolve_db_path
from tol.cli.handlers.status import render_status
from tol.config import get_config
from tol.execution.engine import ExecutionEngine
from tol.load import load_tol_text


def handle_execute(args) -> None:
    tol_text = sys.stdin.read()
    if not tol_text.strip():
        print("ERROR: No TOL document provided on stdin.", file=sys.stderr)
        sys.exit(1)

    try:
        tol_doc = load_tol_text(tol_text)
    except ValueError as exc:
        print(f"ERROR: Failed to parse TOL document: {exc}", file=sys.stderr)
        sys.exit(1)

    config = get_config()
    broker_api = get_broker_api(tol_doc.get("mode"))
    engine = ExecutionEngine(resolve_db_path(), broker_api, tif=config.tif)
    execution_id = engine.start_execution(tol_doc, broker_api)
    engine.advance_execution(execution_id)
    status = engine.get_status(execution_id)
    print(render_status(status))
