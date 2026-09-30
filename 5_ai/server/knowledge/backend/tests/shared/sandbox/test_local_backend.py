"""Unit tests for LocalSandboxBackend."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.src.shared.sandbox.local_backend import LocalSandboxBackend


@pytest.fixture
def backend(tmp_path: Path) -> LocalSandboxBackend:
    return LocalSandboxBackend(root=tmp_path / "sb")


def test_init_creates_root_uploads_output(tmp_path: Path) -> None:
    root = tmp_path / "sb"
    LocalSandboxBackend(root=root)
    assert (root / "uploads").is_dir()
    assert (root / "output").is_dir()


def test_path_translation_workspace(backend: LocalSandboxBackend) -> None:
    assert backend._translate("/workspace") == str(backend.root)
    assert backend._translate("/workspace/uploads/foo.pdf") == str(backend.root / "uploads/foo.pdf")
    assert backend._translate("/etc/passwd") == "/etc/passwd"
    assert backend._translate("") == ""


def test_execute_happy_path(backend: LocalSandboxBackend) -> None:
    result = backend.execute("echo hello")
    assert result.exit_code == 0
    assert "hello" in result.output
    assert result.truncated is False


def test_execute_non_zero_exit(backend: LocalSandboxBackend) -> None:
    result = backend.execute("exit 7")
    assert result.exit_code == 7
    assert result.truncated is False


def test_execute_timeout(backend: LocalSandboxBackend) -> None:
    result = backend.execute("sleep 5", timeout=1)
    assert result.exit_code == 124
    assert result.truncated is True
    assert "timed out" in result.output


def test_execute_rewrites_workspace_paths(tmp_path: Path) -> None:
    backend = LocalSandboxBackend(root=tmp_path / "sb")
    (backend.root / "output").mkdir(exist_ok=True)
    (backend.root / "output" / "hi.txt").write_text("howdy")
    if backend._symlink_ok:
        result = backend.execute("cat /workspace/output/hi.txt")
    else:
        # Force the regex-rewrite path by removing the symlink first.
        (backend.root / "workspace").unlink(missing_ok=True)
        backend._symlink_ok = False
        result = backend.execute("cat /workspace/output/hi.txt")
    assert result.exit_code == 0
    assert "howdy" in result.output


def test_upload_and_download_files(backend: LocalSandboxBackend) -> None:
    upload = backend.upload_files([("/workspace/uploads/x.txt", b"hello bytes")])
    assert upload[0].error is None
    assert (backend.root / "uploads/x.txt").read_bytes() == b"hello bytes"

    download = backend.download_files(["/workspace/uploads/x.txt"])
    assert download[0].error is None
    assert download[0].content == b"hello bytes"


def test_download_missing_returns_error(backend: LocalSandboxBackend) -> None:
    result = backend.download_files(["/workspace/uploads/missing.txt"])
    assert result[0].content == b""
    assert result[0].error == "file_not_found"


def test_ls_returns_workspace_paths(backend: LocalSandboxBackend) -> None:
    (backend.root / "uploads/a.txt").write_text("a")
    (backend.root / "uploads/sub").mkdir()
    result = backend.ls("/workspace/uploads")
    paths = sorted(entry["path"] for entry in result.entries)
    assert "/workspace/uploads/a.txt" in paths
    assert "/workspace/uploads/sub" in paths


def test_read_translates_workspace_path(backend: LocalSandboxBackend) -> None:
    (backend.root / "output").mkdir(exist_ok=True)
    (backend.root / "output/r.txt").write_text("readable\n")
    result = backend.read("/workspace/output/r.txt")
    assert result.error is None
    assert "readable" in result.file_data["content"]


def test_write_translates_workspace_path(backend: LocalSandboxBackend) -> None:
    result = backend.write("/workspace/output/w.txt", "wrote")
    assert result.error is None
    assert result.path == "/workspace/output/w.txt"
    assert (backend.root / "output/w.txt").read_text() == "wrote"


def test_assert_ready_passes(backend: LocalSandboxBackend) -> None:
    backend.assert_ready()  # should not raise


def test_assert_ready_missing_root(tmp_path: Path) -> None:
    backend = LocalSandboxBackend(root=tmp_path / "sb")
    # Tear down the directory to simulate failure.
    import shutil
    shutil.rmtree(backend.root)
    with pytest.raises(RuntimeError, match="존재하지 않습니다"):
        backend.assert_ready()


def test_assert_ready_unwritable_root(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("running as root makes the dir always writable")
    backend = LocalSandboxBackend(root=tmp_path / "sb")
    uploads = backend.root / "uploads"
    uploads.chmod(0o555)
    try:
        with pytest.raises(RuntimeError, match="쓰기 권한이 없습니다"):
            backend.assert_ready()
    finally:
        uploads.chmod(0o755)
