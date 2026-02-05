from tol.cli.handlers.helpers.execution import get_broker_api
from tol.cli.handlers.helpers.pending_trades import (
    format_pending_trade,
    normalize_pending_trades,
)
from tol.config import get_config


def handle_broker_orders(args) -> None:
    del args
    config = get_config()
    broker_api = get_broker_api(config.mode)
    open_orders = broker_api.list_open_order_details()
    pending_trades = normalize_pending_trades(open_orders)

    print("TOL Broker Open Orders")
    print("----------------------------------------")
    print(f"Trading mode: {config.mode}")
    print()
    if not pending_trades:
        print("No open orders.")
        print("----------------------------------------")
        return
    for trade in pending_trades:
        print(f"  {format_pending_trade(trade)}")
    print("----------------------------------------")
