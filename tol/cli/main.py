import argparse
from pathlib import Path

from tol.cli.handlers.check import handle_check
from tol.cli.handlers.run import handle_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tol",
        description="Trading Orchestration Language (TOL) CLI",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run or simulate a TOL orchestration",
    )

    run_parser.add_argument(
        "tol_file",
        type=Path,
        help="Path to TOL YAML file",
    )

    run_parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        required=True,
        help="Execution mode (paper or live)",
    )

    run_parser.add_argument(
        "--dry-run",
        nargs="?",
        const="portfolio",
        choices=["local", "portfolio", "broker"],
        help=(
            "Perform a dry run without executing orders. "
            "If specified without a value, defaults to 'portfolio'."
        ),
    )

    check_parser = subparsers.add_parser(
        "check",
        help="Check portfolio holdings and pricing via IBKR API",
    )

    check_parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        required=True,
        help="Broker mode to check (paper or live)",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        handle_run(args)
    elif args.command == "check":
        handle_check(args)
    else:
        parser.error("Unknown command")
