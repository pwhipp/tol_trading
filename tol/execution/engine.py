from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import sqlite3

from tol.execution.broker import BrokerAPI, OrderStatus
from tol.parser.planner import plan_actions


EXECUTION_ACTIVE = {"RUNNING", "SUSPENDED"}
EXECUTION_TERMINAL = {"COMPLETED", "FAILED", "ABORTED"}
ACTION_TERMINAL = {"FILLED", "FAILED", "CANCELLED", "EXPIRED"}
ACTION_OPEN = {"SUBMITTED", "PARTIAL"}


@dataclass(frozen=True)
class ExecutionStatus:
    execution: dict[str, Any]
    actions: list[dict[str, Any]]
    orders: list[dict[str, Any]]
    fills: list[dict[str, Any]]


class ExecutionEngine:
    def __init__(
        self,
        db_path: Path | str,
        broker_api: BrokerAPI | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._broker_api = broker_api
        self._ensure_schema()

    def start_execution(self, tol_document: dict[str, Any], broker_api: BrokerAPI) -> int:
        self._broker_api = broker_api
        serialized = json.dumps(tol_document)
        now = _utc_now()
        actions = plan_actions(tol_document)

        with self._transaction() as conn:
            if self._has_active_execution(conn):
                raise RuntimeError("An execution is already RUNNING or SUSPENDED.")
            cursor = conn.execute(
                """
                INSERT INTO execution (tol_document_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (serialized, "QUEUED", now, now),
            )
            execution_id = cursor.lastrowid
            for action in actions:
                conn.execute(
                    """
                    INSERT INTO action
                        (execution_id, action_id, action_type, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (execution_id, action.derived_id, action.action_type, "BLOCKED"),
                )
            return int(execution_id)

    def advance_execution(self, execution_id: int) -> None:
        broker_api = self._require_broker()
        execution = self._get_execution(execution_id)
        if execution is None:
            raise ValueError(f"Execution {execution_id} not found.")

        if execution["status"] in EXECUTION_TERMINAL:
            return

        if execution["status"] == "QUEUED":
            with self._transaction() as conn:
                if self._has_active_execution(conn, exclude_id=execution_id):
                    return
                now = _utc_now()
                conn.execute(
                    "UPDATE execution SET status = ?, updated_at = ? WHERE id = ?",
                    ("RUNNING", now, execution_id),
                )
            execution = self._get_execution(execution_id)

        if execution["status"] not in EXECUTION_ACTIVE:
            return

        tol_document = json.loads(execution["tol_document_json"])
        planned_actions = plan_actions(tol_document)
        dependency_map = {
            action.derived_id: action.depends_on for action in planned_actions
        }

        self._refresh_open_orders(execution_id, broker_api)
        self._refresh_action_ready_states(execution_id, dependency_map)
        self._submit_ready_actions(execution_id, planned_actions, broker_api)
        self._refresh_open_orders(execution_id, broker_api)

        if self._should_suspend(execution_id, broker_api):
            self._set_execution_status(execution_id, "SUSPENDED")
            return

        self._finalize_execution_if_complete(execution_id)

    def resume_all(self) -> int | None:
        broker_api = self._require_broker()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT id FROM execution
                WHERE status IN ('RUNNING', 'SUSPENDED')
                ORDER BY created_at ASC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
        if row is None:
            return None
        execution_id = int(row["id"])
        self.advance_execution(execution_id)
        return execution_id

    def abort_execution(self, execution_id: int) -> None:
        broker_api = self._require_broker()
        orders = self._list_open_orders(execution_id)
        for order in orders:
            broker_api.cancel_order(order["broker_order_id"])
        now = _utc_now()
        with self._transaction() as conn:
            conn.execute(
                """
                UPDATE "order"
                SET status = ?
                WHERE id IN (
                    SELECT "order".id
                    FROM "order"
                    JOIN action ON action.id = "order".action_id
                    WHERE action.execution_id = ?
                      AND "order".status IN ('SUBMITTED', 'PARTIAL')
                )
                """,
                ("CANCELLED", execution_id),
            )
            conn.execute(
                """
                UPDATE action
                SET status = ?
                WHERE execution_id = ?
                  AND status IN ('SUBMITTED', 'PARTIAL')
                """,
                ("CANCELLED", execution_id),
            )
            conn.execute(
                "UPDATE execution SET status = ?, updated_at = ? WHERE id = ?",
                ("ABORTED", now, execution_id),
            )

    def get_status(self, execution_id: int) -> ExecutionStatus:
        execution = self._get_execution(execution_id)
        if execution is None:
            raise ValueError(f"Execution {execution_id} not found.")
        with self._connect() as conn:
            actions = conn.execute(
                "SELECT * FROM action WHERE execution_id = ? ORDER BY id",
                (execution_id,),
            ).fetchall()
            orders = conn.execute(
                """
                SELECT "order".* FROM "order"
                JOIN action ON action.id = "order".action_id
                WHERE action.execution_id = ?
                ORDER BY "order".id
                """,
                (execution_id,),
            ).fetchall()
            fills = conn.execute(
                """
                SELECT fill.* FROM fill
                JOIN "order" ON "order".id = fill.order_id
                JOIN action ON action.id = "order".action_id
                WHERE action.execution_id = ?
                ORDER BY fill.id
                """,
                (execution_id,),
            ).fetchall()
        return ExecutionStatus(
            execution=dict(execution),
            actions=[dict(action) for action in actions],
            orders=[dict(order) for order in orders],
            fills=[dict(fill) for fill in fills],
        )

    def _refresh_open_orders(
        self,
        execution_id: int,
        broker_api: BrokerAPI,
    ) -> None:
        orders = self._list_open_orders(execution_id)
        if not orders:
            return
        now = _utc_now()
        with self._transaction() as conn:
            for order in orders:
                status = broker_api.get_order_status(order["broker_order_id"])
                self._record_fill_delta(conn, order, status, now)
                conn.execute(
                    """
                    UPDATE "order"
                    SET status = ?, filled_qty = ?
                    WHERE id = ?
                    """,
                    (status.status, float(status.filled_qty), order["id"]),
                )
                self._update_action_from_order(
                    conn,
                    order["action_id"],
                    status,
                )

    def _update_action_from_order(
        self,
        conn: sqlite3.Connection,
        action_row_id: int,
        order_status: OrderStatus,
    ) -> None:
        if order_status.status in ACTION_TERMINAL:
            next_status = order_status.status
        elif order_status.status == "PARTIAL":
            next_status = "PARTIAL"
        else:
            next_status = "SUBMITTED"
        conn.execute(
            "UPDATE action SET status = ? WHERE id = ?",
            (next_status, action_row_id),
        )

    def _record_fill_delta(
        self,
        conn: sqlite3.Connection,
        order: dict[str, Any],
        status: OrderStatus,
        now: str,
    ) -> None:
        previous_filled = Decimal(str(order["filled_qty"] or 0))
        if status.filled_qty <= previous_filled:
            return
        delta = status.filled_qty - previous_filled
        price = None
        if status.average_price is not None:
            price = float(status.average_price)
        conn.execute(
            """
            INSERT INTO fill (order_id, qty, price, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (order["id"], float(delta), price, now),
        )

    def _refresh_action_ready_states(
        self,
        execution_id: int,
        dependency_map: dict[str, list[str]],
    ) -> None:
        with self._transaction() as conn:
            actions = conn.execute(
                "SELECT id, action_id, status FROM action WHERE execution_id = ?",
                (execution_id,),
            ).fetchall()
            action_status = {row["action_id"]: row["status"] for row in actions}
            for row in actions:
                if row["status"] in ACTION_TERMINAL | ACTION_OPEN:
                    continue
                deps = dependency_map.get(row["action_id"], [])
                if all(action_status.get(dep) == "FILLED" for dep in deps):
                    new_status = "READY"
                else:
                    new_status = "BLOCKED"
                conn.execute(
                    "UPDATE action SET status = ? WHERE id = ?",
                    (new_status, row["id"]),
                )

    def _submit_ready_actions(
        self,
        execution_id: int,
        planned_actions: Iterable[Any],
        broker_api: BrokerAPI,
    ) -> None:
        tol_actions = {action.derived_id: action for action in planned_actions}
        with self._transaction() as conn:
            ready_actions = conn.execute(
                """
                SELECT id, action_id, action_type, status
                FROM action
                WHERE execution_id = ?
                  AND status = 'READY'
                ORDER BY id
                """,
                (execution_id,),
            ).fetchall()
            for row in ready_actions:
                action = tol_actions[row["action_id"]]
                if action.action_type == "fx":
                    conn.execute(
                        "UPDATE action SET status = ? WHERE id = ?",
                        ("FILLED", row["id"]),
                    )
                    continue
                quantity = self._resolve_quantity(action)
                order_spec = {
                    "action_id": action.derived_id,
                    "action_type": action.action_type,
                    "symbol": action.symbol,
                    "quantity": float(quantity),
                }
                broker_order_id = broker_api.submit_order(order_spec)
                conn.execute(
                    """
                    INSERT INTO "order"
                        (action_id, broker_order_id, status, submitted_qty, filled_qty)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (row["id"], broker_order_id, "SUBMITTED", float(quantity), 0.0),
                )
                conn.execute(
                    "UPDATE action SET status = ? WHERE id = ?",
                    ("SUBMITTED", row["id"]),
                )

    def _resolve_quantity(self, action: Any) -> Decimal:
        if action.quantity is None:
            raise ValueError(f"Action {action.derived_id} requires a quantity")
        quantity = Decimal(str(action.quantity))
        if quantity <= 0:
            raise ValueError(f"Action {action.derived_id} has invalid quantity")
        return quantity

    def _should_suspend(self, execution_id: int, broker_api: BrokerAPI) -> bool:
        open_orders = self._list_open_orders(execution_id)
        if not open_orders:
            return False
        snapshot = broker_api.get_portfolio_snapshot()
        market_open = snapshot.get("market_open")
        return market_open is False

    def _finalize_execution_if_complete(self, execution_id: int) -> None:
        with self._transaction() as conn:
            actions = conn.execute(
                "SELECT status FROM action WHERE execution_id = ?",
                (execution_id,),
            ).fetchall()
            statuses = {row["status"] for row in actions}
            if statuses and statuses.issubset({"FILLED"}):
                self._set_execution_status(execution_id, "COMPLETED", conn=conn)
                return
            if statuses & {"FAILED", "CANCELLED", "EXPIRED"}:
                self._set_execution_status(execution_id, "FAILED", conn=conn)

    def _set_execution_status(
        self,
        execution_id: int,
        status: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        now = _utc_now()
        if conn is None:
            with self._transaction() as connection:
                connection.execute(
                    "UPDATE execution SET status = ?, updated_at = ? WHERE id = ?",
                    (status, now, execution_id),
                )
        else:
            conn.execute(
                "UPDATE execution SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, execution_id),
            )

    def _list_open_orders(self, execution_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            orders = conn.execute(
                """
                SELECT "order".id, "order".broker_order_id, "order".filled_qty,
                       "order".action_id
                FROM "order"
                JOIN action ON action.id = "order".action_id
                WHERE action.execution_id = ?
                  AND "order".status IN ('SUBMITTED', 'PARTIAL')
                """,
                (execution_id,),
            ).fetchall()
        return [dict(row) for row in orders]

    def _get_execution(self, execution_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM execution WHERE id = ?", (execution_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def _has_active_execution(
        self, conn: sqlite3.Connection, exclude_id: int | None = None
    ) -> bool:
        params: list[Any] = []
        query = "SELECT id FROM execution WHERE status IN ('RUNNING', 'SUSPENDED')"
        if exclude_id is not None:
            query += " AND id != ?"
            params.append(exclude_id)
        return conn.execute(query, params).fetchone() is not None

    @contextmanager
    def _transaction(self) -> Iterable[sqlite3.Connection]:
        with self._connect() as conn:
            conn.execute("BEGIN")
            try:
                yield conn
            except Exception:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS execution (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tol_document_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS action (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id INTEGER NOT NULL,
                    action_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (execution_id) REFERENCES execution(id)
                );

                CREATE TABLE IF NOT EXISTS "order" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id INTEGER NOT NULL,
                    broker_order_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    submitted_qty REAL NOT NULL,
                    filled_qty REAL NOT NULL,
                    FOREIGN KEY (action_id) REFERENCES action(id)
                );

                CREATE TABLE IF NOT EXISTS fill (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    qty REAL NOT NULL,
                    price REAL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES "order"(id)
                );
                """
            )

    def _require_broker(self) -> BrokerAPI:
        if self._broker_api is None:
            raise RuntimeError("Broker API has not been configured.")
        return self._broker_api


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
