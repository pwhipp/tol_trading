import sys
import argparse

from tol.cli.handlers.config import handle_config
from tol.cli.handlers.describe import handle_describe
from tol.cli.handlers.generate import handle_generate
from tol.cli.handlers.cancel import handle_cancel
from tol.cli.handlers.resume import handle_resume
from tol.cli.handlers.execute import handle_execute
from tol.cli.handlers.portfolio import (
    handle_portfolio_orders,
    handle_portfolio_summary,
)
from tol.cli.handlers.status import handle_status

OPENAI_LLM_MODELS = (
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tol",
        description="Trading Orchestration Language (TOL) CLI",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    execute_parser = subparsers.add_parser(
        "execute",
        help="Execute a TOL orchestration from stdin",
    )

    describe_parser = subparsers.add_parser(
        "describe",
        help="Describe a TOL document from stdin using the LLM",
    )

    describe_parser.add_argument(
        "--llm-model",
        dest="llm_model",
        choices=OPENAI_LLM_MODELS,
        help=(
            "Override the LLM model for describing the document. "
            "Defaults to the configured model."
        ),
    )

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate a TOL document from stdin using the LLM",
    )

    generate_parser.add_argument(
        "--echo",
        action="store_true",
        help=(
            "Echo the generated output to stderr, useful when piping stdout."
        ),
    )

    generate_parser.add_argument(
        "--llm-model",
        dest="llm_model",
        choices=OPENAI_LLM_MODELS,
        help=(
            "Override the LLM model for generating the document. "
            "Defaults to the configured model."
        ),
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

    status_parser = subparsers.add_parser(
        "status",
        help="Show execution status",
    )
    status_parser.add_argument(
        "execution_id",
        nargs="?",
        type=int,
        help="Execution ID (defaults to the active execution)",
    )

    cancel_parser = subparsers.add_parser(
        "cancel",
        help="Cancel an execution",
    )
    cancel_parser.add_argument(
        "execution_id",
        nargs="?",
        type=int,
        help="Execution ID (defaults to the active execution)",
    )

    portfolio_parser = subparsers.add_parser(
        "portfolio",
        help="Inspect portfolio holdings and orders",
    )
    portfolio_subparsers = portfolio_parser.add_subparsers(
        dest="portfolio_command",
        required=True,
    )
    portfolio_subparsers.add_parser(
        "summary",
        help="Summarize portfolio holdings and pricing",
    )
    portfolio_subparsers.add_parser(
        "orders",
        help="List open broker orders",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    command_map = {
        "execute": handle_execute,
        "describe": handle_describe,
        "generate": handle_generate,
        "config": handle_config,
        "resume": handle_resume,
        "status": handle_status,
        "cancel": handle_cancel,
        "portfolio": {
            "summary": handle_portfolio_summary,
            "orders": handle_portfolio_orders,
        },
    }

    def handle_error(args):
        parser.error(f"Unknown command - {args.command}")

    handler = command_map.get(args.command, handle_error)
    if isinstance(handler, dict):
        handler = handler.get(args.portfolio_command)

    try:
        handler(args)
    except ConnectionRefusedError:  # gateway reports the connection error to stderr already
        sys.exit(1)
