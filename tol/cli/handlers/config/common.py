import sys

from tol import config as app_config


def print_config(settings: app_config.Config) -> None:
    app_config.dump_settings(settings, sys.stdout)
