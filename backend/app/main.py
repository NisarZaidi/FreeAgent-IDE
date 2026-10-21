"""FreeAgent IDE FastAPI application."""

from __future__ import annotations

import asyncio
import json
import platform
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import __version__
from app.agents.orchestrator import AgentOrchestrator
from app.config import settings
from app.models.router import model_router
from app.safety.approvals import approval_gate
from app.safety.undo import undo_manager
from app.tools.filesystem import FileSystemTools
from app.tools.git_tools import GitTools
from app.tools.terminal import terminal_manager

app = FastAPI(title=settings.app_name, version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory app state
_workspace: Path | None = settings.workspace_root
_ws_clients: set[WebSocket] = set()
_active_orchestrator: AgentOrchestrator | None = None


@app.on_event("startup")
async def _startup() -> None:
    approval_gate.on_change = broadcast


class OpenWorkspaceRequest(BaseModel):
    path: str


class WriteFileRequest(BaseModel):
    path: str
    content: str


class ModelSelectRequest(BaseModel):
    provider: Literal["ollama", "openai"] | None = None
    model: str | None = None
    agent: str | None = None


class SafetyConfigRequest(BaseModel):
    require_write_approval: bool | None = None
    require_terminal_approval: bool | None = None


class ApprovalRequest(BaseModel):
    action_id: str
    approved: bool


class AgentRunRequest(BaseModel):
    task: str
    apply_writes: bool = True
    run_tests: bool = True


class GitCommitRequest(BaseModel):
    message: str
    add_all: bool = True


class UndoRequest(BaseModel):
    snapshot_id: str


class OpenAIConfigRequest(BaseModel):
    base_url: str | None = None
    api_key: str | None = None


def _require_workspace() -> Path:
    if not _workspace or not _workspace.exists():
        raise HTTPException(400, "No workspace open. Call POST /api/workspace/open first.")
    return _workspace


async def broadcast(event: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    data = json.dumps(event, default=str)
    for ws in list(_ws_clients):
        try:
            await ws.send_text(data)
        except Exception:  # noqa: BLE001
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    models = await model_router.health()
    return {
        "ok": True,
        "version": __version__,
        "app": settings.app_name,
        "workspace": str(_workspace) if _workspace else None,
        "models": models,
        "platform": platform.system(),
        "pending_approvals": len(approval_gate.list_pending()),
    }


@app.get("/api/setup/recommend")
async def recommend_models() -> dict[str, Any]:
    # Rough RAM estimate from platform; detailed detection is OS-specific.
    ram_gb = 16.0
    try:
        if platform.system() == "Windows":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            ram_gb = stat.ullTotalPhys / (1024**3)
        else:
            # Linux
            meminfo = Path("/proc/meminfo")
            if meminfo.exists():
                for line in meminfo.read_text().splitlines():
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        ram_gb = kb / (1024**2)
                        break
    except Exception:  # noqa: BLE001
        pass
    rec = model_router.recommend_for_ram(ram_gb)
    return {"ram_gb": round(ram_gb, 1), "recommendation": rec, "first_run": True}


@app.post("/api/workspace/open")
async def open_workspace(body: OpenWorkspaceRequest) -> dict[str, Any]:
    global _workspace
    path = Path(body.path).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise HTTPException(400, f"Directory not found: {path}")
    _workspace = path
    settings.workspace_root = path
    await broadcast({"type": "workspace_opened", "path": str(path)})
    return {"ok": True, "path": str(path)}


@app.get("/api/workspace")
async def get_workspace() -> dict[str, Any]:
    return {"path": str(_workspace) if _workspace else None}


@app.get("/api/files/tree")
async def file_tree() -> dict[str, Any]:
    ws = _require_workspace()
    fs = FileSystemTools(ws)
    return {"entries": fs.list_tree()}


@app.get("/api/files/read")
async def read_file(path: str) -> dict[str, Any]:
    ws = _require_workspace()
    fs = FileSystemTools(ws)
    try:
        return fs.read_file(path)
    except FileNotFoundError:
        raise HTTPException(404, f"File not found: {path}") from None


@app.post("/api/files/write")
async def write_file(body: WriteFileRequest) -> dict[str, Any]:
    ws = _require_workspace()
    # Manual UI writes skip agent approval but still snapshot
    prev = approval_gate.require_write
    approval_gate.require_write = False
    try:
        fs = FileSystemTools(ws, on_event=broadcast)
        return await fs.write_file(body.path, body.content, agent="user")
    finally:
        approval_gate.require_write = prev


@app.get("/api/files/search")
async def search_files(q: str) -> dict[str, Any]:
    ws = _require_workspace()
    fs = FileSystemTools(ws)
    return {"hits": fs.search(q)}


@app.get("/api/models")
async def list_models() -> dict[str, Any]:
    models = await model_router.list_models()
    return {
        "models": [
            {"id": m.id, "provider": m.provider, "name": m.name, "available": m.available}
            for m in models
        ]
    }


@app.post("/api/models/select")
async def select_model(body: ModelSelectRequest) -> dict[str, Any]:
    if body.agent:
        model_router.set_agent_model(body.agent, body.model)
    else:
        model_router.set_global(provider=body.provider, model=body.model)
    health = await model_router.health()
    await broadcast({"type": "model_changed", "active": health["active"]})
    return {"ok": True, "active": health["active"]}


@app.post("/api/models/openai")
async def configure_openai(body: OpenAIConfigRequest) -> dict[str, Any]:
    if body.base_url is not None:
        settings.openai_base_url = body.base_url or None
    if body.api_key is not None:
        settings.openai_api_key = body.api_key or None
    return {"ok": True, "base_url": settings.openai_base_url, "has_key": bool(settings.openai_api_key)}


@app.get("/api/git/status")
async def git_status() -> dict[str, Any]:
    ws = _require_workspace()
    return GitTools(ws).status()


@app.get("/api/git/diff")
async def git_diff(staged: bool = False) -> dict[str, Any]:
    ws = _require_workspace()
    return GitTools(ws).diff(staged=staged)


@app.post("/api/git/commit")
async def git_commit(body: GitCommitRequest) -> dict[str, Any]:
    ws = _require_workspace()
    return GitTools(ws).commit(body.message, add_all=body.add_all)


@app.get("/api/safety/pending")
async def pending_approvals() -> dict[str, Any]:
    return {
        "pending": [
            {
                "id": p.id,
                "action_type": p.action_type,
                "agent": p.agent,
                "summary": p.summary,
                "payload": p.payload,
                "created_at": p.created_at,
            }
            for p in approval_gate.list_pending()
        ]
    }


@app.post("/api/safety/approve")
async def approve_action(body: ApprovalRequest) -> dict[str, Any]:
    ok = approval_gate.resolve(body.action_id, body.approved)
    if not ok:
        raise HTTPException(404, "Pending action not found or already resolved")
    await broadcast(
        {
            "type": "approval_resolved",
            "action_id": body.action_id,
            "approved": body.approved,
        }
    )
    return {"ok": True}


@app.post("/api/safety/config")
async def safety_config(body: SafetyConfigRequest) -> dict[str, Any]:
    approval_gate.configure(
        require_write=body.require_write_approval,
        require_terminal=body.require_terminal_approval,
    )
    return {
        "require_write_approval": approval_gate.require_write,
        "require_terminal_approval": approval_gate.require_terminal,
    }


@app.get("/api/undo")
async def list_undos() -> dict[str, Any]:
    return {
        "snapshots": [
            {
                "id": s.id,
                "path": s.path,
                "existed": s.existed,
                "created_at": s.created_at,
                "agent": s.agent,
                "reason": s.reason,
            }
            for s in undo_manager.list_recent()
        ]
    }


@app.post("/api/undo")
async def undo_snapshot(body: UndoRequest) -> dict[str, Any]:
    try:
        result = undo_manager.undo(body.snapshot_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    await broadcast({"type": "undo_applied", **result})
    return result


@app.post("/api/agents/run")
async def run_agents(body: AgentRunRequest) -> dict[str, Any]:
    global _active_orchestrator
    ws = _require_workspace()
    if not body.task.strip():
        raise HTTPException(400, "Task is required")

    orch = AgentOrchestrator(
        ws,
        on_event=broadcast,
        apply_writes=body.apply_writes,
        run_tests=body.run_tests,
    )
    _active_orchestrator = orch

    async def _run() -> None:
        await orch.run(body.task)

    asyncio.create_task(_run())
    return {"ok": True, "session_id": orch.session_id, "status": "started"}


@app.post("/api/terminal/start")
async def terminal_start() -> dict[str, Any]:
    ws = _require_workspace()

    async def on_out(event: dict[str, Any]) -> None:
        await broadcast(event)

    session = terminal_manager.create(ws, on_output=on_out)
    return session.start()


@app.post("/api/terminal/{session_id}/input")
async def terminal_input(session_id: str, body: dict[str, str]) -> dict[str, Any]:
    session = terminal_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session.write(body.get("data", ""))


@app.post("/api/terminal/{session_id}/resize")
async def terminal_resize(session_id: str, cols: int = 80, rows: int = 24) -> dict[str, Any]:
    session = terminal_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session.resize(cols, rows)


@app.delete("/api/terminal/{session_id}")
async def terminal_stop(session_id: str) -> dict[str, Any]:
    terminal_manager.remove(session_id)
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws_clients.add(websocket)
    await websocket.send_text(
        json.dumps(
            {
                "type": "connected",
                "workspace": str(_workspace) if _workspace else None,
                "version": __version__,
            }
        )
    )
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            # Client can ping or send approvals over WS
            if msg.get("type") == "approve":
                approval_gate.resolve(msg.get("action_id", ""), bool(msg.get("approved")))
            elif msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)


# Serve frontend build if present
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="assets")

    @app.get("/")
    async def spa_index() -> FileResponse:
        return FileResponse(_frontend_dist / "index.html")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        candidate = _frontend_dist / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_frontend_dist / "index.html")


def run() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
