"""Simple pre-change file snapshots for undo/rollback."""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings


@dataclass
class SnapshotEntry:
    id: str
    path: str
    existed: bool
    snapshot_file: str | None
    created_at: str
    agent: str
    reason: str


class UndoManager:
    def __init__(self) -> None:
        self.root = settings.data_dir / "snapshots"
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "index.json"
        self._entries: list[SnapshotEntry] = []
        self._load()

    def _load(self) -> None:
        if self._index_path.exists():
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            self._entries = [SnapshotEntry(**e) for e in data]
        else:
            self._entries = []

    def _save(self) -> None:
        payload = [asdict(e) for e in self._entries[-settings.max_undo_snapshots :]]
        self._index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._entries = [SnapshotEntry(**e) for e in payload]

    def snapshot(self, path: Path, agent: str, reason: str) -> SnapshotEntry:
        path = path.resolve()
        snap_id = str(uuid.uuid4())
        existed = path.exists() and path.is_file()
        snap_file: str | None = None
        if existed:
            dest = self.root / f"{snap_id}.bak"
            shutil.copy2(path, dest)
            snap_file = str(dest)
        entry = SnapshotEntry(
            id=snap_id,
            path=str(path),
            existed=existed,
            snapshot_file=snap_file,
            created_at=datetime.now(timezone.utc).isoformat(),
            agent=agent,
            reason=reason,
        )
        self._entries.append(entry)
        self._save()
        return entry

    def list_recent(self, limit: int = 20) -> list[SnapshotEntry]:
        return list(reversed(self._entries[-limit:]))

    def undo(self, snapshot_id: str) -> dict:
        entry = next((e for e in self._entries if e.id == snapshot_id), None)
        if not entry:
            raise KeyError(f"Snapshot not found: {snapshot_id}")
        target = Path(entry.path)
        if not entry.existed:
            if target.exists():
                target.unlink()
            return {"restored": False, "deleted": True, "path": entry.path}
        if not entry.snapshot_file:
            raise RuntimeError("Snapshot file missing")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry.snapshot_file, target)
        return {"restored": True, "deleted": False, "path": entry.path}


undo_manager = UndoManager()
