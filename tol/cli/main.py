import argparse

from tol.cli.handlers.check import handle_check
from tol.cli.handlers.config import handle_config
from tol.cli.handlers.describe import handle_describe
from tol.cli.handlers.generate import handle_generate
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
            "If specified without a value, defaults to 'portfolio'. "
            "Levels: 'local' validates the TOL file only; 'portfolio' also "
            "queries holdings and prices to compute quantities; 'broker' also "
            "connects to IBKR to validate order parameters."
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

    describe_parser = subparsers.add_parser(
        "describe",
        help="Describe a TOL document from stdin using the LLM",
    )

    describe_parser.add_argument(
        "--model",
        help="Override the LLM model for describing the document",
    )

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate a TOL document from stdin using the LLM",
    )

    generate_parser.add_argument(
        "--model",
        help="Override the LLM model for generating the document",
    )

    config_parser = subparsers.add_parser(
        "config",
        help="View or update LLM configuration settings",
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    config_subparsers.add_parser(
        "get",
        help="Get a configuration setting",
    ).add_argument("key", help="Setting name to retrieve")

    set_parser = config_subparsers.add_parser(
        "set",
        help="Set a configuration setting",
    )
    set_parser.add_argument("key", help="Setting name to update")
    set_parser.add_argument("value", help="Setting value")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    command_map = {
        "run": handle_run,
        "check": handle_check,
        "describe": handle_describe,
        "generate": handle_generate,
        "config": handle_config
    }

    def handle_error(args):
        parser.error(f"Unknown command - {args.command}")

    command_map.get(args.command, handle_error)(args)
