"""Workspace filesystem tools with approval + undo."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Awaitable

from app.safety.approvals import approval_gate
from app.safety.undo import undo_manager


EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class FileSystemTools:
    def __init__(self, workspace: Path, on_event: EventCallback | None = None) -> None:
        self.workspace = workspace.resolve()
        self.on_event = on_event

    def _resolve(self, rel: str) -> Path:
        path = (self.workspace / rel).resolve()
        if not str(path).startswith(str(self.workspace)):
            raise PermissionError("Path escapes workspace")
        return path

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.workspace)).replace("\\", "/")
        except ValueError:
            return str(path)

    async def _emit(self, event: dict[str, Any]) -> None:
        if self.on_event:
            result = self.on_event(event)
            if hasattr(result, "__await__"):
                await result  # type: ignore[misc]

    def list_tree(self, max_depth: int = 6, max_entries: int = 2000) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        skip = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

        def walk(dir_path: Path, depth: int) -> None:
            if depth > max_depth or len(entries) >= max_entries:
                return
            try:
                children = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                return
            for child in children:
                if child.name in skip or child.name.startswith(".freeagent"):
                    continue
                rel = self._rel(child)
                if child.is_dir():
                    entries.append({"path": rel, "type": "dir", "name": child.name})
                    walk(child, depth + 1)
                else:
                    try:
                        size = child.stat().st_size
                    except OSError:
                        size = 0
                    entries.append(
                        {"path": rel, "type": "file", "name": child.name, "size": size}
                    )

        if self.workspace.exists():
            walk(self.workspace, 0)
        return entries

    def read_file(self, rel: str, max_bytes: int = 512_000) -> dict[str, Any]:
        path = self._resolve(rel)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(rel)
        data = path.read_bytes()
        truncated = len(data) > max_bytes
        text = data[:max_bytes].decode("utf-8", errors="replace")
        return {"path": rel, "content": text, "truncated": truncated, "size": len(data)}

    async def write_file(self, rel: str, content: str, agent: str = "coder") -> dict[str, Any]:
        path = self._resolve(rel)
        approved = await approval_gate.request(
            "write_file",
            agent,
            f"Write file: {rel}",
            {"path": rel, "content_preview": content[:500], "bytes": len(content.encode("utf-8"))},
        )
        if not approved:
            await self._emit({"type": "action_rejected", "action": "write_file", "path": rel})
            return {"ok": False, "rejected": True, "path": rel}

        undo_manager.snapshot(path, agent=agent, reason=f"write {rel}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        await self._emit({"type": "file_written", "path": rel, "agent": agent})
        return {"ok": True, "path": rel, "bytes": len(content.encode("utf-8"))}

    async def delete_file(self, rel: str, agent: str = "coder") -> dict[str, Any]:
        path = self._resolve(rel)
        if not path.exists():
            return {"ok": False, "error": "not found", "path": rel}
        approved = await approval_gate.request(
            "delete_file",
            agent,
            f"Delete file: {rel}",
            {"path": rel},
        )
        if not approved:
            return {"ok": False, "rejected": True, "path": rel}
        if path.is_file():
            undo_manager.snapshot(path, agent=agent, reason=f"delete {rel}")
            path.unlink()
        else:
            raise IsADirectoryError("Directory delete not supported in MVP")
        await self._emit({"type": "file_deleted", "path": rel, "agent": agent})
        return {"ok": True, "path": rel}

    def search(self, query: str, max_hits: int = 50) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        q = query.lower()
        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [
                d
                for d in dirs
                if d not in {".git", "node_modules", "__pycache__", ".venv", "venv", "dist"}
            ]
            for name in files:
                path = Path(root) / name
                try:
                    if path.stat().st_size > 1_000_000:
                        continue
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if q in line.lower():
                        hits.append(
                            {
                                "path": self._rel(path),
                                "line": i,
                                "text": line.strip()[:240],
                            }
                        )
                        if len(hits) >= max_hits:
                            return hits
        return hits
