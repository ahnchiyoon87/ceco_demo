"""Unit tests for the sandbox backend factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.src.shared.kernel import settings as settings_mod
from backend.src.shared.sandbox import (
    get_sandbox_backend,
    reset_sandbox_backend_cache,
)
from backend.src.shared.sandbox.docker_backend import DockerSandboxBackend
from backend.src.shared.sandbox.local_backend import LocalSandboxBackend


@pytest.fixture
def fresh_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Force `get_settings()` and the backend factory to re-read env vars."""

    settings_mod.get_settings.cache_clear()
    reset_sandbox_backend_cache()
    monkeypatch.setenv("LOCAL_SANDBOX_ROOT", str(tmp_path / "sb"))
    yield monkeypatch
    settings_mod.get_settings.cache_clear()
    reset_sandbox_backend_cache()


def test_default_returns_docker_backend(fresh_settings: pytest.MonkeyPatch) -> None:
    fresh_settings.delenv("SANDBOX_BACKEND", raising=False)
    backend = get_sandbox_backend()
    assert isinstance(backend, DockerSandboxBackend)


def test_local_backend_selected(fresh_settings: pytest.MonkeyPatch) -> None:
    fresh_settings.setenv("SANDBOX_BACKEND", "local")
    backend = get_sandbox_backend()
    assert isinstance(backend, LocalSandboxBackend)


def test_invalid_backend_raises(fresh_settings: pytest.MonkeyPatch) -> None:
    fresh_settings.setenv("SANDBOX_BACKEND", "kubernetes")
    with pytest.raises(RuntimeError, match="Unknown SANDBOX_BACKEND"):
        get_sandbox_backend()


def test_local_backend_is_cached(fresh_settings: pytest.MonkeyPatch) -> None:
    fresh_settings.setenv("SANDBOX_BACKEND", "local")
    a = get_sandbox_backend()
    b = get_sandbox_backend()
    assert a is b
