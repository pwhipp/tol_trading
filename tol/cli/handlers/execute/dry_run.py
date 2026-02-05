import sys

from tol.cli.handlers.execute.broker_dry_run import run_broker_dry_run
from tol.cli.handlers.execute.portfolio_dry_run import (
    build_portfolio_report,
    build_snapshot,
    evaluate_actions,
)
from tol.cli.handlers.helpers.execution import get_broker_api
from tol.config import get_config
from tol.load import load_tol_text
from tol.parser.planner import plan_actions


def _read_actions_from_stdin() -> tuple[dict, list]:
    tol_text = sys.stdin.read()
    if not tol_text.strip():
        print("ERROR: No TOL document provided on stdin.", file=sys.stderr)
        sys.exit(1)
    try:
        tol_doc = load_tol_text(tol_text)
    except ValueError as exc:
        print(f"ERROR: Failed to parse TOL document: {exc}", file=sys.stderr)
        sys.exit(1)
    actions = plan_actions(tol_doc)
    return tol_doc, actions


def handle_execute_dry_run_local(args) -> None:
    del args
    tol_doc, actions = _read_actions_from_stdin()
    print("Local dry run plan:")
    print(f"Mode: {tol_doc.get('mode', 'paper')}")
    if not actions:
        print("  (no actions)")
        return
    for action in actions:
        print(f"  - {action.derived_id}: {action.action_type} {action.symbol}")


def handle_execute_dry_run_portfolio(args) -> None:
    del args
    tol_doc, actions = _read_actions_from_stdin()
    mode = tol_doc.get("mode") or get_config().mode
    broker_api = get_broker_api(mode)
    snapshot = broker_api.get_portfolio_snapshot()
    normalized_snapshot = build_snapshot(
        snapshot.get("portfolio", {}).get("cash", {}),
        snapshot.get("portfolio", {}).get("positions", []),
    )
    evaluations = evaluate_actions(actions, normalized_snapshot)
    print("\n".join(build_portfolio_report(normalized_snapshot, evaluations)))


def handle_execute_dry_run_broker(args) -> None:
    del args
    tol_doc, actions = _read_actions_from_stdin()
    mode = tol_doc.get("mode") or get_config().mode
    print("\n".join(run_broker_dry_run(actions, mode=mode)))
