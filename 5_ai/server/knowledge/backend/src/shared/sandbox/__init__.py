"""Sandbox backends for agent execution."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from deepagents.backends.sandbox import BaseSandbox

from ..kernel.settings import get_local_sandbox_root, get_settings


@lru_cache(maxsize=None)
def _make_backend(name: str) -> BaseSandbox:
    if name == "docker":
        from .docker_backend import DockerSandboxBackend

        settings = get_settings()
        return DockerSandboxBackend(
            container_name=settings.container_name,
            workdir=settings.sandbox_workdir,
        )
    if name == "local":
        from .local_backend import LocalSandboxBackend

        settings = get_settings()
        root = Path(settings.local_sandbox_root) if settings.local_sandbox_root else get_local_sandbox_root()
        return LocalSandboxBackend(
            root=root,
            workdir=settings.sandbox_workdir,
        )
    raise RuntimeError(
        f'Unknown SANDBOX_BACKEND: {name} (expected "docker" or "local")'
    )


def get_sandbox_backend() -> BaseSandbox:
    """Return the sandbox backend chosen by `settings.sandbox_backend`."""

    name = (get_settings().sandbox_backend or "docker").strip().lower()
    return _make_backend(name)


def reset_sandbox_backend_cache() -> None:
    """Clear the cached backend (used by tests that change settings at runtime)."""

    _make_backend.cache_clear()
