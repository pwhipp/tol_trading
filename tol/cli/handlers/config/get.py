import sys

from tol import config as app_config


def handle_config_get(args) -> None:
    settings = app_config.get_config()
    try:
        value = app_config.get_setting(settings, args.key)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(value if value is not None else "")
