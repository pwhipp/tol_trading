import sys

from tol.llm import config as llm_config
from tol.llm.settings import LlmSettings


def handle_config(args) -> None:
    settings = llm_config.load_settings()

    if args.config_command is None:
        _print_config(settings)
        return

    if args.config_command == "get":
        try:
            value = llm_config.get_setting(settings, args.key)
        except KeyError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        print(value if value is not None else "")
        return

    if args.config_command == "set":
        try:
            updated = llm_config.set_setting(settings, args.key, args.value)
        except (KeyError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        llm_config.write_settings(updated)
        _print_config(updated)
        return

    print("ERROR: Unknown config command", file=sys.stderr)
    sys.exit(1)


def _print_config(settings: LlmSettings) -> None:
    llm_config.dump_settings(settings, sys.stdout)
