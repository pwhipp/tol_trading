from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import sqlite3

from tol.execution.broker import BrokerAPI, FakeBrokerAPI, IBKRBrokerAPI


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
    try:
        with _connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT id FROM execution
                WHERE status IN ('RUNNING', 'SUSPENDED')
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    return int(row["id"]) if row else None


def _load_execution(db_path: Path, execution_id: int) -> dict[str, Any] | None:
    try:
        with _connect(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM execution WHERE id = ?",
                (execution_id,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
