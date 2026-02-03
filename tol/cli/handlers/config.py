import sys

from tol import config as app_config


def handle_config(args) -> None:
    settings = app_config.get_config()

    if args.config_command is None:
        _print_config(settings)
        return

    if args.config_command == "get":
        try:
            value = app_config.get_setting(settings, args.key)
        except KeyError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        print(value if value is not None else "")
        return

    if args.config_command == "set":
        try:
            updated = app_config.set_setting(settings, args.key, args.value)
        except (KeyError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        updated.save()
        _print_config(updated)
        return

    print("ERROR: Unknown config command", file=sys.stderr)
    sys.exit(1)


def _print_config(settings: app_config.Config) -> None:
    app_config.dump_settings(settings, sys.stdout)
