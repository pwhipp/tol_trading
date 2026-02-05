from __future__ import annotations

import argparse

from tol.cli.parser_map import PARSER_MAP, ParserCommand


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tol",
        description="Trading Orchestration Language (TOL) CLI",
    )
    top_subparsers = parser.add_subparsers(dest="command", required=True)

    for command in PARSER_MAP:
        _add_command(top_subparsers, command)

    return parser


def _add_command(
    subparsers: argparse._SubParsersAction,
    command: ParserCommand,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        command.name,
        help=command.help,
        description=command.description or command.help,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    for argument in command.arguments:
        parser.add_argument(*argument["flags"], **argument["kwargs"])

    if command.handler is not None:
        parser.set_defaults(handler=command.handler)

    if command.subcommands:
        nested_subparsers = parser.add_subparsers(dest=f"{command.name}_command")
        if command.default_subcommand:
            parser.set_defaults(
                **{f"{command.name}_command": command.default_subcommand}
            )
            _bind_default_handler(
                parser,
                command.default_subcommand,
                command.subcommands,
            )
        for nested_command in command.subcommands:
            _add_command(nested_subparsers, nested_command)

    parser.epilog = _build_nested_help(command)
    return parser


def _bind_default_handler(
    parser: argparse.ArgumentParser,
    default_subcommand: str,
    subcommands: list[ParserCommand],
) -> None:
    for subcommand in subcommands:
        if subcommand.name == default_subcommand:
            if subcommand.handler is not None:
                parser.set_defaults(handler=subcommand.handler)
            return


def _build_nested_help(command: ParserCommand) -> str:
    if not command.subcommands:
        return ""

    lines = ["Subcommands:"]
    _append_subcommands(lines, command.subcommands, indent=2)
    return "\n".join(lines)


def _append_subcommands(
    lines: list[str],
    subcommands: list[ParserCommand],
    indent: int,
) -> None:
    for subcommand in subcommands:
        lines.append(f"{' ' * indent}{subcommand.name:<12}{subcommand.help}")
        if subcommand.subcommands:
            _append_subcommands(lines, subcommand.subcommands, indent=indent + 2)
