from decimal import Decimal

from fakebroker.cli.handlers.fakebroker import FakeBrokerController
from fakebroker.cli.main import build_parser
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
    assert order["status"] == "SUBMITTED"
    assert order["failure_reason"] is None
    assert order["pending_reason"] == "MARKET_CLOSED"
    assert order["trade"]["status"] == "SUBMITTED"
    assert order["trade"]["pending_reason"] == "MARKET_CLOSED"


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


def test_fakebroker_order_delete_removes_matching_ids(tmp_path):
    state_path = tmp_path / "fake_broker_state.yaml"
    state_manager = FakeBrokerState(state_path)
    state = state_manager.default_state()
    state["orders"] = {
        "FB-1": {"status": "SUBMITTED", "trade": {}},
        "FB-2": {"status": "SUBMITTED", "trade": {}},
    }
    state_manager.save(state)

    controller = FakeBrokerController(state_path)
    deleted, missing = controller.delete_orders(["FB-1", "FB-3"])

    updated = state_manager.load()
    assert deleted == ["FB-1"]
    assert missing == ["FB-3"]
    assert "FB-1" not in updated["orders"]
    assert "FB-2" in updated["orders"]


def test_fakebroker_parser_supports_order_delete() -> None:
    args = build_parser().parse_args(["order", "delete", "FB-1", "FB-2"])

    assert args.command == "order"
    assert args.order_command == "delete"
    assert args.order_ids == ["FB-1", "FB-2"]
