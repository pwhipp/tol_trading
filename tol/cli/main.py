import argparse

from tol.cli.handlers.check import handle_check
from tol.cli.handlers.config import handle_config
from tol.cli.handlers.describe import handle_describe
from tol.cli.handlers.generate import handle_generate
from tol.cli.handlers.abort import handle_abort
from tol.cli.handlers.resume import handle_resume
from tol.cli.handlers.run import handle_run
from tol.cli.handlers.status import handle_status
from tol.cli.handlers.test import handle_test

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

    run_parser = subparsers.add_parser(
        "run",
        help="Run a TOL orchestration",
    )
    run_parser.add_argument("file", help="Path to the TOL document")

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
        "--mode",
        choices=["paper", "live"],
        help="Override the configured trading mode for the generated document.",
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

    test_parser = subparsers.add_parser(
        "test",
        help="Run a lightweight CLI smoke test",
    )

    test_parser.add_argument(
        "--echo",
        action="store_true",
        help="Echo a confirmation message to stdout.",
    )

    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume the active execution",
    )

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

    abort_parser = subparsers.add_parser(
        "abort",
        help="Abort an execution",
    )
    abort_parser.add_argument(
        "execution_id",
        nargs="?",
        type=int,
        help="Execution ID (defaults to the active execution)",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    command_map = {
        "run": handle_run,
        "check": handle_check,
        "describe": handle_describe,
        "generate": handle_generate,
        "config": handle_config,
        "test": handle_test,
        "resume": handle_resume,
        "status": handle_status,
        "abort": handle_abort,
    }

    def handle_error(args):
        parser.error(f"Unknown command - {args.command}")

    command_map.get(args.command, handle_error)(args)
