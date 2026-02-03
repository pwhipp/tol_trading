from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tol.execution.broker import BrokerAPI, FakeBrokerAPI, IBKRBrokerAPI
from tol.execution.store import ExecutionStore
from tol import config as app_config


def resolve_db_path() -> Path:
    config_dir = app_config.get_config_path().parent
    return config_dir / "tol_execution.sqlite3"


def resolve_broker(mode: str | None) -> BrokerAPI:
    settings = app_config.get_config()
    broker_name = settings.broker
    config_dir = app_config.get_config_path().parent
    broker_map = {
        "FakeBrokerAPI": lambda: FakeBrokerAPI(
            config_dir / "fake_broker_state.yaml"
        ),
        "IBKRBrokerAPI": lambda: IBKRBrokerAPI(mode or settings.mode),
    }
    if broker_name not in broker_map:
        raise ValueError(f"Unknown broker setting: {broker_name}")
    return broker_map[broker_name]()


def lookup_execution_mode(db_path: Path, execution_id: int) -> str | None:
    execution = _load_execution(db_path, execution_id)
    if execution is None:
        return None
    try:
        tol_doc = json.loads(execution["tol_document_json"])
    except json.JSONDecodeError:
        return None
    mode = tol_doc.get("mode")
    return mode if isinstance(mode, str) else None


def find_active_execution_id(db_path: Path) -> int | None:
    store = ExecutionStore(db_path)
    return store.find_active_execution_id()


def _load_execution(db_path: Path, execution_id: int) -> dict[str, Any] | None:
    store = ExecutionStore(db_path)
    return store.get_execution(execution_id)
