from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable


class ExecutionStore:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._ensure_schema()

    def create_execution(self, tol_document_json: str, status: str, now: str) -> int:
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO execution (tol_document_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (tol_document_json, status, now, now),
            )
            return int(cursor.lastrowid)

    def insert_actions(self, execution_id: int, actions: Iterable[dict[str, Any]]) -> None:
        with self.transaction() as conn:
            for action in actions:
                conn.execute(
                    """
                    INSERT INTO action
                        (execution_id, action_id, action_type, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        execution_id,
                        action["action_id"],
                        action["action_type"],
                        action["status"],
                    ),
                )

    def has_active_execution(self, exclude_id: int | None = None) -> bool:
        params: list[Any] = []
        query = "SELECT id FROM execution WHERE status IN ('RUNNING', 'SUSPENDED')"
        if exclude_id is not None:
            query += " AND id != ?"
            params.append(exclude_id)
        with self.connect() as conn:
            return conn.execute(query, params).fetchone() is not None

    def get_execution(self, execution_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM execution WHERE id = ?",
                (execution_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_execution_status(self, execution_id: int, status: str, now: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE execution SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, execution_id),
            )

    def list_actions(self, execution_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM action WHERE execution_id = ? ORDER BY id",
                (execution_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_action_statuses(self, execution_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, action_id, status FROM action WHERE execution_id = ?",
                (execution_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_ready_actions(self, execution_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, action_id, action_type, status
                FROM action
                WHERE execution_id = ?
                  AND status = 'READY'
                ORDER BY id
                """,
                (execution_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_action_status(self, action_row_id: int, status: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE action SET status = ? WHERE id = ?",
                (status, action_row_id),
            )

    def update_action_statuses(self, updates: Iterable[tuple[str, int]]) -> None:
        with self.transaction() as conn:
            for status, action_row_id in updates:
                conn.execute(
                    "UPDATE action SET status = ? WHERE id = ?",
                    (status, action_row_id),
                )

    def mark_execution_actions(self, execution_id: int, status: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE action
                SET status = ?
                WHERE execution_id = ?
                  AND status IN ('SUBMITTED', 'PARTIAL')
                """,
                (status, execution_id),
            )

    def list_orders(self, execution_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT "order".* FROM "order"
                JOIN action ON action.id = "order".action_id
                WHERE action.execution_id = ?
                ORDER BY "order".id
                """,
                (execution_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_fills(self, execution_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT fill.* FROM fill
                JOIN "order" ON "order".id = fill.order_id
                JOIN action ON action.id = "order".action_id
                WHERE action.execution_id = ?
                ORDER BY fill.id
                """,
                (execution_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_open_orders(self, execution_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
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
        return [dict(row) for row in rows]

    def find_active_execution_id(self) -> int | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM execution
                WHERE status IN ('RUNNING', 'SUSPENDED')
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
        return int(row["id"]) if row else None

    def update_order(self, order_id: int, status: str, filled_qty: float) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE "order"
                SET status = ?, filled_qty = ?
                WHERE id = ?
                """,
                (status, filled_qty, order_id),
            )

    def insert_order(
        self,
        action_id: int,
        broker_order_id: str,
        status: str,
        submitted_qty: float,
        filled_qty: float,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO "order"
                    (action_id, broker_order_id, status, submitted_qty, filled_qty)
                VALUES (?, ?, ?, ?, ?)
                """,
                (action_id, broker_order_id, status, submitted_qty, filled_qty),
            )

    def insert_fill(
        self,
        order_id: int,
        qty: float,
        price: float | None,
        timestamp: str,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO fill (order_id, qty, price, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, qty, price, timestamp),
            )

    def cancel_open_orders(self, execution_id: int, status: str) -> None:
        with self.transaction() as conn:
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
                (status, execution_id),
            )

    @contextmanager
    def transaction(self) -> Iterable[sqlite3.Connection]:
        with self.connect() as conn:
            conn.execute("BEGIN")
            try:
                yield conn
            except Exception:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema(self) -> None:
        with self.connect() as conn:
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
