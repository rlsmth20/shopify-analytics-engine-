import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from app.growth.executable import resolve_codex
from app.growth.browser_executor import runtime_cycle


def test_removed_version_recovers_and_skips_incomplete_update():
    with TemporaryDirectory() as temp:
        root = Path(temp) / "OpenAI/Codex/bin"
        for name, stamp in (("old", 1), ("current", 2), ("incomplete", 3)):
            folder = root / name
            folder.mkdir(parents=True)
            if name != "incomplete":
                (folder / "codex.exe").write_text("fixture")
            os.utime(folder, (stamp, stamp))
        stale = root / "removed/codex.exe"
        assert resolve_codex(stale, local_app_data=temp) == str((root / "current/codex.exe").resolve())
        (root / "current/codex.exe").unlink()
        assert resolve_codex(stale, local_app_data=temp) == str((root / "old/codex.exe").resolve())


def test_existing_explicit_executable_is_respected():
    with TemporaryDirectory() as temp:
        preferred = Path(temp) / "explicit.exe"
        preferred.write_text("fixture")
        assert resolve_codex(preferred, local_app_data=temp) == str(preferred.resolve())


def test_missing_runtime_never_claims_work_or_invokes_adapter():
    with TemporaryDirectory() as temp, patch.dict(os.environ, {"LOCALAPPDATA": temp}):
        with patch("app.growth.browser_executor.cycle") as cycle:
            with pytest.raises(FileNotFoundError):
                runtime_cycle(None, "test", codex=None, repo=temp)
            cycle.assert_not_called()
