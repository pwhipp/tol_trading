from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from tol.execution.broker import BrokerAPI, OrderStatus
from tol.parser.planner import plan_actions
from tol.execution.store import ExecutionStore


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
        self._store = ExecutionStore(db_path)
        self._broker_api = broker_api

    def start_execution(self, tol_document: dict[str, Any], broker_api: BrokerAPI) -> int:
        self._broker_api = broker_api
        serialized = json.dumps(tol_document)
        now = _utc_now()
        actions = plan_actions(tol_document)
        if self._store.has_active_execution():
            raise RuntimeError("An execution is already RUNNING or SUSPENDED.")
        execution_id = self._store.create_execution(serialized, "QUEUED", now)
        action_rows = [
            {
                "action_id": action.derived_id,
                "action_type": action.action_type,
                "status": "BLOCKED",
            }
            for action in actions
        ]
        self._store.insert_actions(execution_id, action_rows)
        return execution_id

    def advance_execution(self, execution_id: int) -> None:
        broker_api = self._require_broker()
        execution = self._store.get_execution(execution_id)
        if execution is None:
            raise ValueError(f"Execution {execution_id} not found.")

        if execution["status"] in EXECUTION_TERMINAL:
            return

        if execution["status"] == "QUEUED":
            if self._store.has_active_execution(exclude_id=execution_id):
                return
            self._store.update_execution_status(execution_id, "RUNNING", _utc_now())
            execution = self._store.get_execution(execution_id)

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
        execution_id = self._store.find_active_execution_id()
        if execution_id is None:
            return None
        self.advance_execution(execution_id)
        return execution_id

    def abort_execution(self, execution_id: int) -> None:
        broker_api = self._require_broker()
        orders = self._store.list_open_orders(execution_id)
        for order in orders:
            broker_api.cancel_order(order["broker_order_id"])
        now = _utc_now()
        self._store.cancel_open_orders(execution_id, "CANCELLED")
        self._store.mark_execution_actions(execution_id, "CANCELLED")
        self._store.update_execution_status(execution_id, "ABORTED", now)

    def get_status(self, execution_id: int) -> ExecutionStatus:
        execution = self._store.get_execution(execution_id)
        if execution is None:
            raise ValueError(f"Execution {execution_id} not found.")
        actions = self._store.list_actions(execution_id)
        orders = self._store.list_orders(execution_id)
        fills = self._store.list_fills(execution_id)
        return ExecutionStatus(
            execution=dict(execution),
            actions=actions,
            orders=orders,
            fills=fills,
        )

    def _refresh_open_orders(
        self,
        execution_id: int,
        broker_api: BrokerAPI,
    ) -> None:
        orders = self._store.list_open_orders(execution_id)
        if not orders:
            return
        now = _utc_now()
        for order in orders:
            status = broker_api.get_order_status(order["broker_order_id"])
            self._record_fill_delta(order, status, now)
            self._store.update_order(order["id"], status.status, float(status.filled_qty))
            self._update_action_from_order(order["action_id"], status)

    def _update_action_from_order(
        self,
        action_row_id: int,
        order_status: OrderStatus,
    ) -> None:
        if order_status.status in ACTION_TERMINAL:
            next_status = order_status.status
        elif order_status.status == "PARTIAL":
            next_status = "PARTIAL"
        else:
            next_status = "SUBMITTED"
        self._store.update_action_status(action_row_id, next_status)

    def _record_fill_delta(
        self,
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
        self._store.insert_fill(order["id"], float(delta), price, now)

    def _refresh_action_ready_states(
        self,
        execution_id: int,
        dependency_map: dict[str, list[str]],
    ) -> None:
        actions = self._store.list_action_statuses(execution_id)
        action_status = {row["action_id"]: row["status"] for row in actions}
        updates = []
        for row in actions:
            if row["status"] in ACTION_TERMINAL | ACTION_OPEN:
                continue
            deps = dependency_map.get(row["action_id"], [])
            if all(action_status.get(dep) == "FILLED" for dep in deps):
                new_status = "READY"
            else:
                new_status = "BLOCKED"
            updates.append((new_status, row["id"]))
        if updates:
            self._store.update_action_statuses(updates)

    def _submit_ready_actions(
        self,
        execution_id: int,
        planned_actions: Iterable[Any],
        broker_api: BrokerAPI,
    ) -> None:
        tol_actions = {action.derived_id: action for action in planned_actions}
        ready_actions = self._store.list_ready_actions(execution_id)
        for row in ready_actions:
            action = tol_actions[row["action_id"]]
            if action.action_type == "fx":
                self._store.update_action_status(row["id"], "FILLED")
                continue
            quantity = self._resolve_quantity(action)
            order_spec = {
                "action_id": action.derived_id,
                "action_type": action.action_type,
                "symbol": action.symbol,
                "quantity": float(quantity),
            }
            broker_order_id = broker_api.submit_order(order_spec)
            self._store.insert_order(
                row["id"],
                broker_order_id,
                "SUBMITTED",
                float(quantity),
                0.0,
            )
            self._store.update_action_status(row["id"], "SUBMITTED")

    def _resolve_quantity(self, action: Any) -> Decimal:
        if action.quantity is None:
            raise ValueError(f"Action {action.derived_id} requires a quantity")
        quantity = Decimal(str(action.quantity))
        if quantity <= 0:
            raise ValueError(f"Action {action.derived_id} has invalid quantity")
        return quantity

    def _should_suspend(self, execution_id: int, broker_api: BrokerAPI) -> bool:
        open_orders = self._store.list_open_orders(execution_id)
        if not open_orders:
            return False
        snapshot = broker_api.get_portfolio_snapshot()
        market_open = snapshot.get("market_open")
        return market_open is False

    def _finalize_execution_if_complete(self, execution_id: int) -> None:
        actions = self._store.list_action_statuses(execution_id)
        statuses = {row["status"] for row in actions}
        if statuses and statuses.issubset({"FILLED"}):
            self._store.update_execution_status(execution_id, "COMPLETED", _utc_now())
            return
        if statuses & {"FAILED", "CANCELLED", "EXPIRED"}:
            self._store.update_execution_status(execution_id, "FAILED", _utc_now())

    def _set_execution_status(self, execution_id: int, status: str) -> None:
        self._store.update_execution_status(execution_id, status, _utc_now())

    def _require_broker(self) -> BrokerAPI:
        if self._broker_api is None:
            raise RuntimeError("Broker API has not been configured.")
        return self._broker_api


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
