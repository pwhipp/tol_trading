from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tol.execution.broker import BrokerAPI, FakeBrokerAPI, IBKRBrokerAPI
from tol.execution.store import ExecutionStore
from tol.llm import config as llm_config


def resolve_db_path() -> Path:
    settings = llm_config.load_settings()
    return settings.data_path / "tol_execution.sqlite3"


def resolve_broker(mode: str | None) -> BrokerAPI:
    settings = llm_config.load_settings()
    broker_name = settings.broker
    if broker_name == "FakeBrokerAPI":
        state_path = settings.data_path / "fake_broker_state.yaml"
        return FakeBrokerAPI(state_path)
    trading_mode = mode or settings.mode
    return IBKRBrokerAPI(trading_mode)


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
