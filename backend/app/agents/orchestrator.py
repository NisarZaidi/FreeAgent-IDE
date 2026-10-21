"""LangGraph multi-agent orchestrator: Planner → Coder → Reviewer → Tester."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.prompts import CODER_SYSTEM, PLANNER_SYSTEM, REVIEWER_SYSTEM, TESTER_SYSTEM
from app.models.router import ChatMessage, model_router
from app.tools.filesystem import FileSystemTools
from app.tools.git_tools import GitTools
from app.tools.terminal import TerminalSession

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]

FILE_BLOCK_RE = re.compile(
    r"<<<FILE\s+(.+?)>>>\n(.*?)<<<END>>>",
    re.DOTALL,
)
RUN_RE = re.compile(r"^RUN:\s*(.+)$", re.MULTILINE)


class AgentState(TypedDict, total=False):
    task: str
    plan: str
    code_output: str
    review: str
    test_output: str
    applied_files: list[str]
    messages: list[dict[str, str]]
    error: str
    paused: bool


class AgentOrchestrator:
    def __init__(
        self,
        workspace: Path,
        on_event: EventCallback | None = None,
        apply_writes: bool = True,
        run_tests: bool = True,
    ) -> None:
        self.workspace = workspace.resolve()
        self.on_event = on_event
        self.apply_writes = apply_writes
        self.run_tests = run_tests
        self.fs = FileSystemTools(self.workspace, on_event=self._bridge_event)
        self.git = GitTools(self.workspace)
        self.terminal = TerminalSession(self.workspace, on_output=self._bridge_event)
        self.session_id = str(uuid.uuid4())
        self._graph = self._build_graph()

    async def _bridge_event(self, event: dict[str, Any]) -> None:
        await self._emit(event)

    async def _emit(self, event: dict[str, Any]) -> None:
        payload = {**event, "session_id": self.session_id}
        if self.on_event:
            await self.on_event(payload)

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("planner", self._planner_node)
        graph.add_node("coder", self._coder_node)
        graph.add_node("reviewer", self._reviewer_node)
        graph.add_node("tester", self._tester_node)
        graph.set_entry_point("planner")
        graph.add_edge("planner", "coder")
        graph.add_edge("coder", "reviewer")
        graph.add_edge("reviewer", "tester")
        graph.add_edge("tester", END)
        return graph.compile()

    async def _planner_node(self, state: AgentState) -> AgentState:
        await self._emit({"type": "agent_started", "agent": "planner"})
        tree_preview = self._tree_preview()
        messages = [
            ChatMessage(role="system", content=PLANNER_SYSTEM),
            ChatMessage(
                role="user",
                content=(
                    f"Workspace: {self.workspace}\n"
                    f"Project tree (partial):\n{tree_preview}\n\n"
                    f"Task:\n{state['task']}"
                ),
            ),
        ]
        plan = await model_router.chat(messages, agent="planner", temperature=0.3)
        await self._emit({"type": "agent_message", "agent": "planner", "content": plan})
        await self._emit({"type": "agent_finished", "agent": "planner"})
        msgs = list(state.get("messages") or [])
        msgs.append({"agent": "planner", "content": plan})
        return {**state, "plan": plan, "messages": msgs}

    async def _coder_node(self, state: AgentState) -> AgentState:
        await self._emit({"type": "agent_started", "agent": "coder"})
        messages = [
            ChatMessage(role="system", content=CODER_SYSTEM),
            ChatMessage(
                role="user",
                content=(
                    f"Task:\n{state['task']}\n\n"
                    f"Plan:\n{state.get('plan', '')}\n\n"
                    f"Tree:\n{self._tree_preview()}"
                ),
            ),
        ]
        output = await model_router.chat(messages, agent="coder", temperature=0.2)
        await self._emit({"type": "agent_message", "agent": "coder", "content": output})

        applied: list[str] = []
        if self.apply_writes:
            for path, content in FILE_BLOCK_RE.findall(output):
                path = path.strip().replace("\\", "/")
                result = await self.fs.write_file(path, content.rstrip() + "\n", agent="coder")
                if result.get("ok"):
                    applied.append(path)
                    await self._emit(
                        {
                            "type": "diff_ready",
                            "agent": "coder",
                            "path": path,
                            "content": content,
                        }
                    )

        await self._emit({"type": "agent_finished", "agent": "coder", "files": applied})
        msgs = list(state.get("messages") or [])
        msgs.append({"agent": "coder", "content": output})
        return {**state, "code_output": output, "applied_files": applied, "messages": msgs}

    async def _reviewer_node(self, state: AgentState) -> AgentState:
        await self._emit({"type": "agent_started", "agent": "reviewer"})
        file_context = []
        for path in state.get("applied_files") or []:
            try:
                file_context.append(f"### {path}\n{self.fs.read_file(path)['content'][:4000]}")
            except Exception:  # noqa: BLE001
                pass
        messages = [
            ChatMessage(role="system", content=REVIEWER_SYSTEM),
            ChatMessage(
                role="user",
                content=(
                    f"Task:\n{state['task']}\n\n"
                    f"Coder output:\n{state.get('code_output', '')}\n\n"
                    f"Files:\n" + "\n\n".join(file_context)
                ),
            ),
        ]
        review = await model_router.chat(messages, agent="reviewer", temperature=0.2)
        await self._emit({"type": "agent_message", "agent": "reviewer", "content": review})
        await self._emit({"type": "agent_finished", "agent": "reviewer"})
        msgs = list(state.get("messages") or [])
        msgs.append({"agent": "reviewer", "content": review})
        return {**state, "review": review, "messages": msgs}

    async def _tester_node(self, state: AgentState) -> AgentState:
        await self._emit({"type": "agent_started", "agent": "tester"})
        messages = [
            ChatMessage(role="system", content=TESTER_SYSTEM),
            ChatMessage(
                role="user",
                content=(
                    f"Task:\n{state['task']}\n\n"
                    f"Plan:\n{state.get('plan', '')}\n\n"
                    f"Coder output:\n{state.get('code_output', '')}\n\n"
                    f"Review:\n{state.get('review', '')}"
                ),
            ),
        ]
        output = await model_router.chat(messages, agent="tester", temperature=0.2)
        await self._emit({"type": "agent_message", "agent": "tester", "content": output})

        if self.apply_writes:
            for path, content in FILE_BLOCK_RE.findall(output):
                path = path.strip().replace("\\", "/")
                await self.fs.write_file(path, content.rstrip() + "\n", agent="tester")

        command_results = []
        if self.run_tests:
            for match in RUN_RE.findall(output):
                result = await self.terminal.run_command(match.strip(), agent="tester")
                command_results.append(result)

        await self._emit(
            {
                "type": "agent_finished",
                "agent": "tester",
                "commands": command_results,
            }
        )
        msgs = list(state.get("messages") or [])
        msgs.append({"agent": "tester", "content": output})
        return {**state, "test_output": output, "messages": msgs}

    def _tree_preview(self, limit: int = 80) -> str:
        entries = self.fs.list_tree(max_depth=3, max_entries=limit)
        lines = []
        for e in entries[:limit]:
            prefix = "📁 " if e["type"] == "dir" else "📄 "
            lines.append(prefix + e["path"])
        return "\n".join(lines) if lines else "(empty workspace)"

    async def run(self, task: str) -> AgentState:
        await self._emit({"type": "session_started", "task": task})
        initial: AgentState = {
            "task": task,
            "messages": [],
            "applied_files": [],
        }
        try:
            final = await self._graph.ainvoke(initial)
            await self._emit(
                {
                    "type": "session_finished",
                    "summary": {
                        "plan": final.get("plan", "")[:500],
                        "files": final.get("applied_files", []),
                        "review": (final.get("review") or "")[:500],
                    },
                }
            )
            return final  # type: ignore[return-value]
        except Exception as exc:  # noqa: BLE001
            await self._emit({"type": "session_error", "error": str(exc)})
            return {**initial, "error": str(exc)}


async def run_session(
    workspace: Path,
    task: str,
    on_event: EventCallback | None = None,
) -> AgentState:
    orch = AgentOrchestrator(workspace, on_event=on_event)
    return await orch.run(task)
