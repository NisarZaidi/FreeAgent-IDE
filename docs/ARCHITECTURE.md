# Architecture

FreeAgent IDE is a local-first stack: a Python FastAPI backend orchestrates agents and tools; a React UI provides a Cursor-like shell in the browser.

```
┌─────────────────────────────────────────────────────┐
│                   User Interface                     │
│  (File Tree + Monaco + Chat + Terminal + Agents)     │
└─────────────────────┬───────────────────────────────┘
                      │ REST + WebSocket
┌─────────────────────▼───────────────────────────────┐
│              Agent Orchestrator (LangGraph)          │
│  Planner → Coder → Reviewer → Tester                 │
└─────────┬───────────────────────────┬───────────────┘
          │                           │
┌─────────▼─────────┐       ┌─────────▼─────────┐
│   Model Router     │       │  Tools Layer      │
│ (Ollama / OpenAI-  │       │ (FS, Terminal,    │
│  compatible APIs)  │       │  Git, Undo)       │
└────────────────────┘       └───────────────────┘
```

## Backend packages

| Path | Role |
|------|------|
| `backend/app/main.py` | FastAPI routes, WebSocket broadcast |
| `backend/app/agents/` | LangGraph graph + role prompts |
| `backend/app/models/` | Provider routing & health checks |
| `backend/app/tools/` | Filesystem, Git, terminal |
| `backend/app/safety/` | Approval gate + undo snapshots |

## Agent flow

1. User submits a natural-language task
2. **Planner** returns a numbered plan
3. **Coder** emits `<<<FILE path>>>…<<<END>>>` blocks; writes go through the approval gate
4. **Reviewer** critiques applied files
5. **Tester** may write tests and emit `RUN:` shell commands (also approval-gated)
6. Events stream to the UI over `/ws`

## Safety

- Configurable confirmation for file writes and terminal commands
- Pre-change snapshots under `~/.freeagent-ide/snapshots`
- Workspace path sandboxing (no escape outside the opened folder)

## Frontend

Vite + React + Monaco + xterm.js. In development, Vite proxies `/api` and `/ws` to port `8765`. Production builds are served by FastAPI from `frontend/dist`.
