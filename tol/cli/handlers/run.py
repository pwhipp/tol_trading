import sys

from tol.cli.handlers.execution_helpers import resolve_broker, resolve_db_path
from tol.execution.engine import ExecutionEngine
from tol.load import load_tol_text


def handle_run(args) -> None:
    tol_text = sys.stdin.read()
    if not tol_text.strip():
        print("ERROR: No TOL document provided on stdin.", file=sys.stderr)
        sys.exit(1)

    try:
        tol_doc = load_tol_text(tol_text)
    except ValueError as exc:
        print(f"ERROR: Failed to parse TOL document: {exc}", file=sys.stderr)
        sys.exit(1)

    broker_api = resolve_broker(tol_doc.get("mode"))
    engine = ExecutionEngine(resolve_db_path(), broker_api)
    execution_id = engine.start_execution(tol_doc, broker_api)
    engine.advance_execution(execution_id)
    print(execution_id)
