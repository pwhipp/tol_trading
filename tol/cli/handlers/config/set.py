import sys

from tol import config as app_config
from tol.cli.handlers.config.common import print_config


def handle_config_set(args) -> None:
    settings = app_config.get_config()
    try:
        updated = app_config.set_setting(settings, args.category, args.key, args.value)
    except (KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    updated.save()
    print_config(updated)
