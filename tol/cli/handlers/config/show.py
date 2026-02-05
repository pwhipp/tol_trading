from tol import config as app_config
from tol.cli.handlers.config.common import print_config


def handle_config_show(args) -> None:
    del args
    settings = app_config.get_config()
    print_config(settings)
