"""Unit tests for the backend-agnostic workspace helpers (local mode)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.src.shared.kernel import settings as settings_mod


@pytest.fixture
def local_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    settings_mod.get_settings.cache_clear()
    monkeypatch.setenv("SANDBOX_BACKEND", "local")
    monkeypatch.setenv("LOCAL_SANDBOX_ROOT", str(tmp_path / "sb"))
    # Re-import workspace under the new env so its module-level state is fresh.
    from backend.src.modules.files import workspace as ws

    ws.ensure_workspace_dirs()
    yield ws
    settings_mod.get_settings.cache_clear()


def test_local_write_upload_persists_file(local_workspace) -> None:
    record = local_workspace.write_upload("hello.txt", b"hi")
    assert record["name"] == "hello.txt"
    assert record["path"] == "/workspace/uploads/hello.txt"
    assert Path(record["local_path"]).read_bytes() == b"hi"
    assert record["size"] == 2


def test_local_list_uploads_and_outputs(local_workspace) -> None:
    local_workspace.write_upload("a.txt", b"aa")
    out_dir = Path(local_workspace._local_root()) / "output"
    (out_dir / "report.json").write_text("{}")

    listing = {
        "uploads": local_workspace.list_uploads(),
        "outputs": local_workspace.list_outputs(),
    }
    upload_names = [u["name"] for u in listing["uploads"]]
    output_names = [o["name"] for o in listing["outputs"]]
    assert "a.txt" in upload_names
    assert "report.json" in output_names
    assert local_workspace.list_output_filenames() == ["report.json"]


def test_local_resolve_output_for_download(local_workspace) -> None:
    out_dir = Path(local_workspace._local_root()) / "output"
    (out_dir / "x.bin").write_bytes(b"\x00\x01")
    path = local_workspace.resolve_output_for_download("x.bin")
    assert path is not None
    assert Path(path).read_bytes() == b"\x00\x01"
    assert local_workspace.resolve_output_for_download("missing.bin") is None


def test_local_delete_upload(local_workspace) -> None:
    local_workspace.write_upload("byebye.txt", b"x")
    assert local_workspace.delete_upload("byebye.txt") is True
    assert local_workspace.delete_upload("byebye.txt") is False


def test_local_clear_workspace(local_workspace) -> None:
    local_workspace.write_upload("a.txt", b"a")
    out_dir = Path(local_workspace._local_root()) / "output"
    (out_dir / "b.json").write_text("{}")

    local_workspace.clear_workspace()
    assert local_workspace.list_uploads() == []
    assert local_workspace.list_outputs() == []


def test_local_get_local_upload_root_points_into_sandbox(local_workspace, tmp_path: Path) -> None:
    root = local_workspace.get_local_upload_root()
    assert root == tmp_path / "sb" / "uploads"


def test_docker_branch_uses_subprocess(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings_mod.get_settings.cache_clear()
    monkeypatch.setenv("SANDBOX_BACKEND", "docker")
    monkeypatch.delenv("LOCAL_SANDBOX_ROOT", raising=False)
    from backend.src.modules.files import workspace as ws

    calls: list[list[str]] = []

    class FakeCompleted:
        def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, *a, **kw):
        calls.append(list(cmd))
        return FakeCompleted(returncode=0, stdout=b"")

    monkeypatch.setattr(ws.subprocess, "run", fake_run)
    ws.ensure_workspace_dirs()
    assert any(c[:2] == ["docker", "exec"] for c in calls)
    settings_mod.get_settings.cache_clear()
