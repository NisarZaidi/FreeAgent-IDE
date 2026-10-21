# Troubleshooting

## Installer fails finding Python

- Install Python 3.11+ from https://www.python.org/downloads/ (enable **Add to PATH**)
- Restart the terminal and re-run `install.ps1` / `install.sh`
- On Windows, disable the Store app aliases under *Settings → Apps → Advanced app settings → App execution aliases*

## UI is blank / only API JSON

Build the frontend:

```bash
cd frontend && npm install && npm run build
```

Restart `start.ps1` / `start.sh`.

## Ollama not running

```bash
ollama serve
ollama pull llama3.2:3b
```

Check health: `http://127.0.0.1:8765/api/health`

## Agents error or hang

- Confirm a model is pulled and selected in the top bar
- Mid-range hardware may need smaller models (`3b`)
- For cloud/free APIs, set `OPENAI_BASE_URL` and `OPENAI_API_KEY` in `.env`

## Approvals stuck

Open the Agents panel and click **Approve** / **Reject**. Pending actions also appear under `GET /api/safety/pending`.

## Terminal does nothing

Open a workspace first, then check WebSocket status (green dot in the top bar). Restart the app if the session died.

## Low VRAM / out of memory

Switch to a smaller model or close other GPU apps. See hardware table in the README.

## Port 8765 in use

```bash
# Windows
netstat -ano | findstr 8765
# Linux
ss -ltnp | grep 8765
```

Stop the other process or change `PORT` in `.env`.
