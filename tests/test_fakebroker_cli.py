from decimal import Decimal

from fakebroker.cli.handlers.fakebroker import FakeBrokerController
from tol.execution.broker.implementations.FakeBrokerAPI import (
    FakeBrokerAPI,
    FakeBrokerState,
)


def test_fakebroker_closed_market_submission(tmp_path):
    state_path = tmp_path / "fake_broker_state.yaml"
    state_manager = FakeBrokerState(state_path)
    state = state_manager.default_state()
    state["closed_markets"] = ["NASDAQ"]
    state_manager.save(state)

    api = FakeBrokerAPI(state_path)
    submission = api.submit_order(
        {
            "symbol": "NVDA.NASDAQ",
            "action_type": "buy",
            "quantity": 5,
        }
    )

    updated = state_manager.load()
    order = updated["orders"][submission.broker_order_id]
    assert order["status"] == "FAILED"
    assert order["failure_reason"] == "MARKET_CLOSED"
    assert order["trade"]["status"] == "FAILED"


def test_fakebroker_fill_buy_clamps_to_cash(tmp_path):
    state_path = tmp_path / "fake_broker_state.yaml"
    state_manager = FakeBrokerState(state_path)
    state = state_manager.default_state()
    state["portfolio"]["cash"]["USD"] = 1000
    state["prices"]["NVDA.NASDAQ"] = {"price": 500, "currency": "USD"}
    state["orders"]["FB-1"] = {
        "status": "SUBMITTED",
        "submitted_qty": 10.0,
        "filled_qty": 0.0,
        "average_price": None,
        "failure_reason": None,
        "trade": {
            "order_id": "FB-1",
            "status": "SUBMITTED",
            "filled_qty": 0.0,
            "avg_fill_price": None,
            "action_type": "buy",
            "symbol": "NVDA.NASDAQ",
            "submitted_qty": 10.0,
            "order_type": "MKT",
        },
    }
    state_manager.save(state)

    controller = FakeBrokerController(state_path)
    result = controller.fill_order("FB-1")

    updated = state_manager.load()
    order = updated["orders"]["FB-1"]
    assert result.filled_qty == Decimal("2")
    assert order["status"] == "PARTIAL"
    assert order["average_price"] == 500.0
    assert updated["portfolio"]["cash"]["USD"] == 0.0
    positions = updated["portfolio"]["positions"]
    assert positions == [
        {
            "symbol": "NVDA.NASDAQ",
            "quantity": 2.0,
            "market_value": 1000.0,
            "currency": "USD",
        }
    ]
