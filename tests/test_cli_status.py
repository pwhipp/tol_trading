from __future__ import annotations

from pathlib import Path

import yaml

from tol import config as app_config
from tol.cli.handlers.execution_helpers import resolve_db_path
from tol.cli.handlers.status import handle_status
from tol.cli.main import build_parser
from tol.execution.broker import FakeBrokerAPI
from tol.execution.engine import ExecutionEngine


def _write_state(path: Path, state: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(state, handle, sort_keys=False)


def test_status_outputs_yaml_with_parsed_json(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app_config.get_config.cache_clear()
    settings = app_config.get_config()
    updated = app_config.set_setting(settings, "broker", "FakeBrokerAPI")
    updated.save()

    broker_state = tmp_path / "fake_broker_state.yaml"
    _write_state(
        broker_state,
        {
            "market": {"open": True},
            "portfolio": {"cash": {"USD": 100000}},
            "orders": {},
        },
    )

    broker = FakeBrokerAPI(broker_state)
    engine = ExecutionEngine(resolve_db_path(), broker)
    execution_id = engine.start_execution(
        {
            "version": 1,
            "mode": "paper",
            "actions": [
                {
                    "buy": {
                        "symbol": "VOO",
                        "quantity": 10,
                        "using": ["CASH (USD)"],
                    }
                }
            ],
        },
        broker,
    )
    engine.advance_execution(execution_id)

    args = build_parser().parse_args(["execute", "status", str(execution_id)])
    handle_status(args)

    output = capsys.readouterr().out
    payload = yaml.safe_load(output)

    assert payload["execution"]["tol_document"]["mode"] == "paper"
    assert payload["orders"][0]["trade"]["order_id"]
