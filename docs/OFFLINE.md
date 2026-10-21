# Offline / air-gapped install

1. On a machine with internet, clone the repo and run the installer so dependencies and models download.
2. Copy the entire project folder plus:
   - `backend/.venv` (or recreate with a wheels mirror)
   - Ollama model blobs (typically under `~/.ollama` or `%USERPROFILE%\.ollama`)
3. On the offline machine, install Python 3.11+ and Node only if you need to rebuild the UI.
4. Start with `./start.sh` or `.\start.ps1` and point the wizard at your project folder.

Manual model transfer with Ollama:

```bash
# export (online)
ollama show llama3.2:3b --modelfile > Modelfile
# copy blobs from ~/.ollama/models

# import (offline) — restore the models directory, then:
ollama list
```

For fully offline Python deps, build a wheelhouse:

```bash
pip download -r backend/requirements.txt -d wheels
pip install --no-index --find-links=wheels -r backend/requirements.txt
```
