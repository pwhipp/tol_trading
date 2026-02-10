from __future__ import annotations

import io
from pathlib import Path

import yaml

from tol import config as app_config
from tol.cli.handlers.execute.run import handle_execute_run
from tol.cli.handlers.execute.resume import handle_execute_resume
from tol.cli.handlers.helpers.execution import resolve_db_path
from tol.cli.main import build_parser
from tol.execution.broker import FakeBrokerAPI
from tol.execution.engine import ExecutionEngine


def _write_state(path: Path, state: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(state, handle, sort_keys=False)


def _tol_doc_text() -> str:
    return """version: 1
mode: paper
actions:
  - buy:
      symbol: VOO
      quantity: 1
      using:
        - CASH (USD)
"""


def _configure_fake_broker(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app_config.get_config.cache_clear()
    settings = app_config.get_config()
    updated = app_config.set_setting(settings, "broker", "api", "FakeBrokerAPI")
    updated.save()
    return app_config.get_config_path().parent


def test_execute_outputs_status_yaml(tmp_path: Path, capsys, monkeypatch) -> None:
    _configure_fake_broker(monkeypatch, tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(_tol_doc_text()))

    args = build_parser().parse_args(["execute", "run"])
    handle_execute_run(args)

    output = capsys.readouterr().out
    payload = yaml.safe_load(output)

    assert payload["execution"]["status"] in {"RUNNING", "SUSPENDED"}
    assert payload["execution"]["tol_document"]["mode"] == "paper"


def test_resume_outputs_status_yaml(tmp_path: Path, capsys, monkeypatch) -> None:
    config_dir = _configure_fake_broker(monkeypatch, tmp_path)
    broker_state = config_dir / "fake_broker_state.yaml"
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
    execution_id = engine.start_execution(yaml.safe_load(_tol_doc_text()), broker)
    engine.advance_execution(execution_id)

    args = build_parser().parse_args(["execute", "resume"])
    handle_execute_resume(args)

    output = capsys.readouterr().out
    payload = yaml.safe_load(output)

    assert payload["execution"]["id"] == execution_id
    assert payload["execution"]["status"] in {"RUNNING", "SUSPENDED", "COMPLETED"}

