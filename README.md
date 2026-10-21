# FreeAgent IDE

**Cursor-level AI coding — completely free and local.**

Multiple specialized AI agents (Planner, Coder, Reviewer, Tester) collaborate on your machine. Your code never leaves your computer when you use Ollama.

![FreeAgent IDE](docs/assets/hero-placeholder.svg)

## Features

- **One-command install** on Windows and Linux
- **Multi-agent workflow** with live progress and approve/reject for writes & shell
- **Monaco editor**, file tree, integrated terminal, chat/agent panel
- **Ollama** first-class + OpenAI-compatible APIs (Groq, OpenRouter, LM Studio, …)
- **Undo** for AI file changes · basic **Git** status / diff / commit
- **No telemetry** by default

## Quick install

### Windows (PowerShell)

```powershell
git clone https://github.com/NisarZaidi/FreeAgent-IDE.git
cd FreeAgent-IDE
.\install.ps1
```

### Linux

```bash
git clone https://github.com/NisarZaidi/FreeAgent-IDE.git
cd FreeAgent-IDE
bash install.sh
```

Then open **http://127.0.0.1:8765**

## Hardware recommendations

| RAM | Suggested Ollama model | Notes |
|-----|------------------------|-------|
| 8–12 GB | `llama3.2:3b` | Light coding help |
| 16–24 GB | `qwen2.5-coder:7b` | Better code quality |
| 32 GB+ | `qwen2.5-coder:14b` | Stronger multi-agent runs |

GPU (NVIDIA / AMD / Apple via Ollama) improves speed but is optional.

## Development

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
pip install -e .

# Frontend (dev server with API proxy)
cd ..\frontend
npm install
npm run dev
```

Run API: `uvicorn app.main:app --reload --port 8765` from `backend/`.

## Usage

1. Open a project folder in the first-run wizard
2. Pick a model (Ollama must be running for local models)
3. Describe a task in the Agents panel
4. Approve file writes / commands when prompted
5. Review diffs in the editor · Undo AI from the top bar if needed

## Configuration

Copy [`.env.example`](.env.example) to `backend/.env` or project root `.env`.

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Contributing](docs/CONTRIBUTING.md)

## Privacy

- No telemetry in the core app
- Local models via Ollama keep prompts and code on-device
- Optional API providers send only what you choose to those endpoints; keys stay in local settings

## License

MIT — free forever for the open-source core.

## Roadmap (short)

1. **MVP** — this repo (web IDE + LangGraph agents + installers)
2. **Usability** — richer diffs, themes, shortcuts
3. **Desktop** — Tauri/Electron packaging, custom agents, RAG
