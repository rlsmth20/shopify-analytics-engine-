"""Resolve the existing desktop runtime without pinning an update directory."""
import os
from pathlib import Path


def resolve_codex(preferred=None, *, local_app_data=None):
    if preferred and Path(preferred).is_file():
        return str(Path(preferred).resolve())
    local = local_app_data if local_app_data is not None else os.environ.get("LOCALAPPDATA")
    if local:
        root = Path(local) / "OpenAI" / "Codex" / "bin"
        if root.is_dir():
            for folder in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                candidate = folder / "codex.exe"
                if folder.is_dir() and candidate.is_file():
                    return str(candidate.resolve())
    raise FileNotFoundError("Installed desktop Codex executable unavailable; no acquisition task claimed")
