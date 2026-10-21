"""Human-in-the-loop approval for destructive agent actions."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

from app.config import settings

ActionType = Literal["write_file", "delete_file", "terminal"]
NotifyCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


@dataclass
class PendingAction:
    id: str
    action_type: ActionType
    agent: str
    summary: str
    payload: dict[str, Any]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ApprovalGate:
    """Queues actions that need user confirmation."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingAction] = {}
        self._futures: dict[str, asyncio.Future[bool]] = {}
        self.require_write = settings.require_write_approval
        self.require_terminal = settings.require_terminal_approval
        self.on_change: NotifyCallback | None = None

    def list_pending(self) -> list[PendingAction]:
        return list(self._pending.values())

    def configure(self, require_write: bool | None = None, require_terminal: bool | None = None) -> None:
        if require_write is not None:
            self.require_write = require_write
        if require_terminal is not None:
            self.require_terminal = require_terminal

    async def _notify(self, event: dict[str, Any]) -> None:
        if not self.on_change:
            return
        result = self.on_change(event)
        if hasattr(result, "__await__"):
            await result  # type: ignore[misc]

    async def request(
        self,
        action_type: ActionType,
        agent: str,
        summary: str,
        payload: dict[str, Any],
        *,
        force: bool = False,
    ) -> bool:
        needs = force
        if action_type in ("write_file", "delete_file") and self.require_write:
            needs = True
        if action_type == "terminal" and self.require_terminal:
            needs = True
        if not needs:
            return True

        action_id = str(uuid.uuid4())
        pending = PendingAction(
            id=action_id,
            action_type=action_type,
            agent=agent,
            summary=summary,
            payload=payload,
        )
        self._pending[action_id] = pending
        await self._notify({"type": "approval_needed", "action": asdict(pending)})
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        self._futures[action_id] = fut
        try:
            return await fut
        finally:
            self._pending.pop(action_id, None)
            self._futures.pop(action_id, None)

    def resolve(self, action_id: str, approved: bool) -> bool:
        fut = self._futures.get(action_id)
        if not fut or fut.done():
            return False
        fut.set_result(approved)
        return True


approval_gate = ApprovalGate()
