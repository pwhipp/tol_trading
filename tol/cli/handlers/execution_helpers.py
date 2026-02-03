from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from tol.execution.broker import BrokerAPI, FakeBrokerAPI, IBKRBrokerAPI
from tol.execution.store import ExecutionStore


def resolve_db_path() -> Path:
    return Path(os.environ.get("TOL_DB_PATH", "tol_execution.sqlite3"))


def resolve_broker(mode: str | None) -> BrokerAPI:
    fake_state = os.environ.get("TOL_FAKE_BROKER_STATE")
    if fake_state:
        return FakeBrokerAPI(Path(fake_state))
    broker_mode = mode or os.environ.get("TOL_IBKR_MODE", "paper")
    return IBKRBrokerAPI(broker_mode)


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
