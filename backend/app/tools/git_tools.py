"""Basic Git integration: status, diff, commit."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import git
    from git import Repo
except ImportError:  # pragma: no cover
    git = None  # type: ignore
    Repo = None  # type: ignore


class GitTools:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def _repo(self) -> Any:
        if Repo is None:
            raise RuntimeError("GitPython not installed")
        try:
            return Repo(self.workspace, search_parent_directories=True)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Not a git repository: {exc}") from exc

    def status(self) -> dict[str, Any]:
        try:
            repo = self._repo()
        except RuntimeError as exc:
            return {"ok": False, "error": str(exc)}
        changed = [item.a_path for item in repo.index.diff(None)]
        staged = [item.a_path for item in repo.index.diff("HEAD")]
        untracked = list(repo.untracked_files)
        return {
            "ok": True,
            "branch": repo.active_branch.name if not repo.head.is_detached else "DETACHED",
            "dirty": repo.is_dirty(untracked_files=True),
            "changed": changed,
            "staged": staged,
            "untracked": untracked,
        }

    def diff(self, staged: bool = False) -> dict[str, Any]:
        try:
            repo = self._repo()
        except RuntimeError as exc:
            return {"ok": False, "error": str(exc)}
        if staged:
            text = repo.git.diff("--cached")
        else:
            text = repo.git.diff(None)
        return {"ok": True, "diff": text}

    def commit(self, message: str, add_all: bool = True) -> dict[str, Any]:
        try:
            repo = self._repo()
        except RuntimeError as exc:
            return {"ok": False, "error": str(exc)}
        if add_all:
            repo.git.add(A=True)
        if not repo.is_dirty() and not repo.untracked_files:
            # After add, check staged
            if not repo.index.diff("HEAD"):
                return {"ok": False, "error": "Nothing to commit"}
        commit = repo.index.commit(message)
        return {"ok": True, "sha": commit.hexsha, "message": message}
