import argparse
import sys
from pathlib import Path
import yaml

from tol.parser.planner import plan_actions


def build_parser():
    parser = argparse.ArgumentParser(
        prog="tol",
        description="Trading Orchestration Language (TOL) CLI"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run or simulate a TOL orchestration"
    )

    run_parser.add_argument(
        "tol_file",
        type=Path,
        help="Path to TOL YAML file"
    )

    run_parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        required=True,
        help="Execution mode (paper or live)"
    )

    run_parser.add_argument(
        "--dry-run",
        nargs="?",
        const="portfolio",
        choices=["local", "portfolio", "broker"],
        help=(
            "Perform a dry run without executing orders. "
            "If specified without a value, defaults to 'portfolio'."
        )
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        handle_run(args)
    else:
        parser.error("Unknown command")


def handle_run(args):
    tol_file = args.tol_file
    mode = args.mode
    dry_run = args.dry_run

    print("TOL CLI — Proof of Concept")
    print("-" * 40)

    if not tol_file.exists():
        print(f"ERROR: TOL file not found: {tol_file}")
        sys.exit(1)

    print(f"TOL file        : {tol_file}")
    print(f"Execution mode  : {mode}")

    if dry_run:
        print(f"Dry run level   : {dry_run}")
    else:
        print("Dry run         : NO (execution requested)")

    print()
    print("Planned behaviour:")
    print("-" * 20)

    if dry_run is None:
        if mode == "live":
            print("• This would EXECUTE trades against the LIVE IBKR account.")
            print("• Orders would be placed and persisted.")
        else:
            print("• This would EXECUTE trades against the PAPER IBKR account.")
            print("• Orders would be placed and persisted.")

    elif dry_run == "local":
        print("• Parse and validate the TOL document only.")
        print("• Build dependency graph.")
        print("• NO portfolio queries.")
        print("• NO price queries.")
        print("• NO broker connectivity.")

    elif dry_run == "portfolio":
        print("• Parse and validate the TOL document.")
        print("• Build dependency graph.")
        print("• Query portfolio holdings.")
        print("• Query market prices.")
        print("• Compute quantities and targets.")
        print("• Detect obvious errors (insufficient holdings, absurd quantities).")
        print("• NO orders will be placed.")

    elif dry_run == "broker":
        print("• Parse and validate the TOL document.")
        print("• Build dependency graph.")
        print("• Connect to IBKR gateway.")
        print("• Resolve contracts.")
        print("• Validate order parameters with broker.")
        print("• NO orders will be placed.")

    print()
    print("NOTE:")
    print("• This is a stub CLI.")
    print("• No actions have been executed.")
    print("• No state has been persisted.")
    print("• This interface is designed to be shared with a future GUI.")

    print("-" * 40)

    print()
    print("Derived execution plan:")
    print("-" * 20)

    with open(tol_file, "r") as f:
        tol_doc = yaml.safe_load(f)

    actions = plan_actions(tol_doc)

    for action in actions:
        print(f"• {action.derived_id}")
        print(f"    type        : {action.action_type}")
        print(f"    symbol      : {action.symbol}")
        if action.quantity is not None:
            print(f"    quantity    : {action.quantity}")
        if action.percent is not None:
            print(f"    percent     : {action.percent}")
        if action.using_classified:
            print("    using:")
            for source, kind in action.using_classified:
                print(f"      - {source:<10} ({kind})")
        if action.depends_on:
            print(f"    depends_on  : {action.depends_on}")
