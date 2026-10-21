"""Integrated terminal sessions (Windows ConPTY / Unix PTY)."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Awaitable

from app.safety.approvals import approval_gate

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class TerminalSession:
    """Simple subprocess-backed terminal suitable for MVP."""

    def __init__(
        self,
        workspace: Path,
        on_output: EventCallback | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.on_output = on_output
        self.id = str(uuid.uuid4())
        self._proc: subprocess.Popen[bytes] | None = None
        self._reader: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> dict[str, Any]:
        if self._proc and self._proc.poll() is None:
            return {"ok": True, "id": self.id, "already_running": True}

        shell = self._default_shell()
        env = os.environ.copy()
        env["TERM"] = env.get("TERM", "xterm-256color")
        self._proc = subprocess.Popen(
            shell,
            cwd=str(self.workspace),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            bufsize=0,
            shell=False,
        )
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        return {"ok": True, "id": self.id, "shell": shell}

    def _default_shell(self) -> list[str]:
        if platform.system() == "Windows":
            pwsh = shutil.which("pwsh") or shutil.which("powershell")
            if pwsh:
                return [pwsh, "-NoLogo", "-NoExit"]
            return ["cmd.exe"]
        shell = os.environ.get("SHELL", "/bin/bash")
        return [shell]

    def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        while True:
            chunk = self._proc.stdout.read(1024)
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            self._emit_sync({"type": "terminal_output", "id": self.id, "data": text})

    def _emit_sync(self, event: dict[str, Any]) -> None:
        if not self.on_output:
            return
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._emit(event), self._loop)
        else:
            result = self.on_output(event)
            if hasattr(result, "__await__"):
                pass

    async def _emit(self, event: dict[str, Any]) -> None:
        if self.on_output:
            result = self.on_output(event)
            if hasattr(result, "__await__"):
                await result  # type: ignore[misc]

    def write(self, data: str) -> dict[str, Any]:
        if not self._proc or not self._proc.stdin or self._proc.poll() is not None:
            return {"ok": False, "error": "Terminal not running"}
        self._proc.stdin.write(data.encode("utf-8"))
        self._proc.stdin.flush()
        return {"ok": True}

    def resize(self, cols: int, rows: int) -> dict[str, Any]:
        # Subprocess MVP does not support PTY resize; accepted for API compatibility.
        return {"ok": True, "cols": cols, "rows": rows}

    def stop(self) -> dict[str, Any]:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        return {"ok": True, "id": self.id}

    async def run_command(self, command: str, agent: str = "tester") -> dict[str, Any]:
        """Run a one-shot command with approval (used by agents)."""
        approved = await approval_gate.request(
            "terminal",
            agent,
            f"Run command: {command}",
            {"command": command, "cwd": str(self.workspace)},
        )
        if not approved:
            return {"ok": False, "rejected": True, "command": command}

        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(self.workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace") if stdout else ""
        await self._emit(
            {
                "type": "command_result",
                "agent": agent,
                "command": command,
                "exit_code": proc.returncode,
                "output": output[-8000:],
            }
        )
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "output": output[-8000:],
            "command": command,
        }


class TerminalManager:
    def __init__(self) -> None:
        self._sessions: dict[str, TerminalSession] = {}

    def create(self, workspace: Path, on_output: EventCallback | None = None) -> TerminalSession:
        session = TerminalSession(workspace, on_output=on_output)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> TerminalSession | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            session.stop()


terminal_manager = TerminalManager()
