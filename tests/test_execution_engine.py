from __future__ import annotations

from pathlib import Path

import yaml

from tol.execution.broker import FakeBrokerAPI
from tol.execution.engine import ExecutionEngine


def _write_state(path: Path, state: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(state, handle, sort_keys=False)


def _read_state(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _basic_tol_doc() -> dict:
    return {
        "version": 1,
        "mode": "paper",
        "actions": [
            {
                "buy": {
                    "symbol": "VOO",
                    "quantity": 100,
                    "using": ["CASH (USD)"],
                }
            }
        ],
    }


def test_partial_fills(tmp_path: Path) -> None:
    broker_state = tmp_path / "broker.yaml"
    _write_state(
        broker_state,
        {
            "market": {"open": True},
            "portfolio": {"cash": {"USD": 100000}},
            "orders": {},
        },
    )

    broker = FakeBrokerAPI(broker_state)
    engine = ExecutionEngine(tmp_path / "engine.sqlite", broker)
    execution_id = engine.start_execution(_basic_tol_doc(), broker)
    engine.advance_execution(execution_id)

    state = _read_state(broker_state)
    order_id = next(iter(state["orders"]))
    state["orders"][order_id]["status"] = "PARTIAL"
    state["orders"][order_id]["filled_qty"] = 40
    _write_state(broker_state, state)

    engine.advance_execution(execution_id)
    status = engine.get_status(execution_id)
    assert status.actions[0]["status"] == "PARTIAL"

    state = _read_state(broker_state)
    state["orders"][order_id]["status"] = "FILLED"
    state["orders"][order_id]["filled_qty"] = 100
    _write_state(broker_state, state)

    engine.advance_execution(execution_id)
    status = engine.get_status(execution_id)
    assert status.execution["status"] == "COMPLETED"
    assert status.actions[0]["status"] == "FILLED"
    assert len(status.fills) == 2


def test_market_close_suspends(tmp_path: Path) -> None:
    broker_state = tmp_path / "broker.yaml"
    _write_state(
        broker_state,
        {
            "market": {"open": True},
            "portfolio": {"cash": {"USD": 100000}},
            "orders": {},
        },
    )

    broker = FakeBrokerAPI(broker_state)
    engine = ExecutionEngine(tmp_path / "engine.sqlite", broker)
    execution_id = engine.start_execution(_basic_tol_doc(), broker)
    engine.advance_execution(execution_id)

    state = _read_state(broker_state)
    state["market"]["open"] = False
    _write_state(broker_state, state)

    engine.advance_execution(execution_id)
    status = engine.get_status(execution_id)
    assert status.execution["status"] == "SUSPENDED"

    state = _read_state(broker_state)
    order_id = next(iter(state["orders"]))
    state["market"]["open"] = True
    state["orders"][order_id]["status"] = "FILLED"
    state["orders"][order_id]["filled_qty"] = 100
    _write_state(broker_state, state)

    engine.advance_execution(execution_id)
    status = engine.get_status(execution_id)
    assert status.execution["status"] == "COMPLETED"


def test_restart_between_advances(tmp_path: Path) -> None:
    broker_state = tmp_path / "broker.yaml"
    _write_state(
        broker_state,
        {
            "market": {"open": True},
            "portfolio": {"cash": {"USD": 100000}},
            "orders": {},
        },
    )

    broker = FakeBrokerAPI(broker_state)
    db_path = tmp_path / "engine.sqlite"
    engine = ExecutionEngine(db_path, broker)
    execution_id = engine.start_execution(_basic_tol_doc(), broker)
    engine.advance_execution(execution_id)

    state = _read_state(broker_state)
    order_id = next(iter(state["orders"]))
    state["orders"][order_id]["status"] = "FILLED"
    state["orders"][order_id]["filled_qty"] = 100
    _write_state(broker_state, state)

    restarted = ExecutionEngine(db_path, broker)
    restarted.advance_execution(execution_id)
    status = restarted.get_status(execution_id)
    assert status.execution["status"] == "COMPLETED"


def test_abort_with_open_orders(tmp_path: Path) -> None:
    broker_state = tmp_path / "broker.yaml"
    _write_state(
        broker_state,
        {
            "market": {"open": True},
            "portfolio": {"cash": {"USD": 100000}},
            "orders": {},
        },
    )

    broker = FakeBrokerAPI(broker_state)
    engine = ExecutionEngine(tmp_path / "engine.sqlite", broker)
    execution_id = engine.start_execution(_basic_tol_doc(), broker)
    engine.advance_execution(execution_id)

    engine.abort_execution(execution_id)
    status = engine.get_status(execution_id)
    assert status.execution["status"] == "ABORTED"
    assert status.actions[0]["status"] == "CANCELLED"

    state = _read_state(broker_state)
    order_id = next(iter(state["orders"]))
    assert state["orders"][order_id]["status"] == "CANCELLED"


def test_fake_broker_initializes_state(tmp_path: Path) -> None:
    broker_state = tmp_path / "broker.yaml"
    broker = FakeBrokerAPI(broker_state)
    snapshot = broker.get_portfolio_snapshot()

    state = _read_state(broker_state)
    assert state["portfolio"]["cash"]["USD"] == 1_000_000
    assert snapshot["portfolio"]["cash"]["USD"] == 1_000_000
