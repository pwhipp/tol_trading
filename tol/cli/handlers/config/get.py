import sys

from tol import config as app_config


def handle_config_get(args) -> None:
    settings = app_config.get_config()
    try:
        value = app_config.get_setting(settings, args.category, args.key)
    except KeyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    if args.key is None:
        app_config.dump_category(settings, args.category, sys.stdout)
        return
    print(value if value is not None else "")
