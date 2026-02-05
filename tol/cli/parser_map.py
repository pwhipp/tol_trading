from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tol.cli.handlers.config.get import handle_config_get
from tol.cli.handlers.config.set import handle_config_set
from tol.cli.handlers.config.show import handle_config_show
from tol.cli.handlers.describe import handle_describe
from tol.cli.handlers.execute.cancel import handle_execute_cancel
from tol.cli.handlers.execute.resume import handle_execute_resume
from tol.cli.handlers.execute.run import handle_execute_run
from tol.cli.handlers.execute.status import handle_execute_status
from tol.cli.handlers.generate import handle_generate
from tol.cli.handlers.broker.orders import handle_broker_orders
from tol.cli.handlers.broker.price import handle_broker_price
from tol.cli.handlers.broker.summary import handle_broker_summary


OPENAI_LLM_MODELS = (
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
)


@dataclass
class ParserCommand:
    name: str
    help: str
    description: str | None = None
    handler: Callable | None = None
    arguments: list[dict] = field(default_factory=list)
    subcommands: list["ParserCommand"] = field(default_factory=list)
    default_subcommand: str | None = None


PARSER_MAP = [
    ParserCommand(
        name="execute",
        help="Execute, inspect, and control TOL executions.",
        description="Execute, inspect, and control TOL executions.",
        subcommands=[
            ParserCommand(
                name="run",
                help="Execute a TOL orchestration from stdin.",
                handler=handle_execute_run,
            ),
            ParserCommand(
                name="status",
                help="Show execution status.",
                handler=handle_execute_status,
                arguments=[
                    {
                        "flags": ["execution_id"],
                        "kwargs": {
                            "nargs": "?",
                            "type": int,
                            "help": "Execution ID (defaults to the active execution)",
                        },
                    }
                ],
            ),
            ParserCommand(
                name="cancel",
                help="Cancel an execution.",
                handler=handle_execute_cancel,
                arguments=[
                    {
                        "flags": ["execution_id"],
                        "kwargs": {
                            "nargs": "?",
                            "type": int,
                            "help": "Execution ID (defaults to the active execution)",
                        },
                    }
                ],
            ),
            ParserCommand(
                name="resume",
                help="Resume the active execution.",
                handler=handle_execute_resume,
            ),
        ],
        default_subcommand="run",
    ),
    ParserCommand(
        name="describe",
        help="Describe a TOL document from stdin using the LLM.",
        handler=handle_describe,
        arguments=[
            {
                "flags": ["--llm-model"],
                "kwargs": {
                    "dest": "llm_model",
                    "choices": OPENAI_LLM_MODELS,
                    "help": (
                        "Override the LLM model for describing the document. "
                        "Defaults to the configured model."
                    ),
                },
            }
        ],
    ),
    ParserCommand(
        name="generate",
        help="Generate a TOL document from stdin using the LLM.",
        handler=handle_generate,
        arguments=[
            {
                "flags": ["--echo"],
                "kwargs": {
                    "action": "store_true",
                    "help": "Echo generated output to stderr.",
                },
            },
            {
                "flags": ["--llm-model"],
                "kwargs": {
                    "dest": "llm_model",
                    "choices": OPENAI_LLM_MODELS,
                    "help": (
                        "Override the LLM model for generating the document. "
                        "Defaults to the configured model."
                    ),
                },
            },
        ],
    ),
    ParserCommand(
        name="config",
        help="View or update configuration settings.",
        subcommands=[
            ParserCommand(
                name="show",
                help="Show current configuration settings.",
                handler=handle_config_show,
            ),
            ParserCommand(
                name="get",
                help="Get a configuration setting.",
                handler=handle_config_get,
                arguments=[
                    {
                        "flags": ["key"],
                        "kwargs": {"help": "Setting name to retrieve"},
                    }
                ],
            ),
            ParserCommand(
                name="set",
                help="Set a configuration setting.",
                handler=handle_config_set,
                arguments=[
                    {
                        "flags": ["key"],
                        "kwargs": {"help": "Setting name to update"},
                    },
                    {
                        "flags": ["value"],
                        "kwargs": {"help": "Setting value"},
                    },
                ],
            ),
        ],
        default_subcommand="show",
    ),
    ParserCommand(
        name="broker",
        help="Inspect broker account holdings and orders.",
        description="Inspect broker account holdings and orders.",
        subcommands=[
            ParserCommand(
                name="summary",
                help="Summarize broker account holdings and pricing.",
                handler=handle_broker_summary,
            ),
            ParserCommand(
                name="orders",
                help="List open broker orders.",
                handler=handle_broker_orders,
            ),
            ParserCommand(
                name="price",
                help="Fetch broker price snapshots for one or more tickers.",
                handler=handle_broker_price,
                arguments=[
                    {
                        "flags": ["tickers"],
                        "kwargs": {
                            "nargs": "+",
                            "help": "Ticker(s), optionally with .EXCHANGE suffix",
                        },
                    },
                    {
                        "flags": ["--watch"],
                        "kwargs": {
                            "choices": ("reset", "add"),
                            "default": "reset",
                            "help": "Update broker_watched_tickers using reset or add mode",
                        },
                    },
                ],
            ),
        ],
    ),
]
