"""Host-filesystem sandbox backend for DeepAgents.

Mirrors `DockerSandboxBackend` but executes commands directly on the host via
`bash -lc` instead of `docker exec`. The agent still sees `/workspace/uploads`
and `/workspace/output` as logical paths; this backend rewrites them to
`<root>/uploads` and `<root>/output` at the boundary, and ensures a
`<root>/workspace -> <root>` symlink so absolute `/workspace/...` references
inside scripts resolve when the working directory is `<root>`.

DEV-ONLY: there is no isolation between the agent and the backend host user.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
    LsResult,
    ReadResult,
    WriteResult,
)
from deepagents.backends.sandbox import BaseSandbox

logger = logging.getLogger(__name__)


_WORKSPACE_PREFIX = "/workspace"
_WORKSPACE_PREFIX_RE = re.compile(r"(?<![\w/])/workspace(?=/|\b)")


class LocalSandboxBackend(BaseSandbox):
    """Execute sandbox commands directly on the host filesystem."""

    def __init__(
        self,
        root: Path | str,
        workdir: str = "/workspace",
        timeout: int = 120,
    ) -> None:
        self._root = Path(root).expanduser().resolve()
        self._workdir = workdir
        self._timeout = timeout
        self._id = str(uuid.uuid4())
        self._symlink_ok = False

        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / "uploads").mkdir(parents=True, exist_ok=True)
        (self._root / "output").mkdir(parents=True, exist_ok=True)
        self._symlink_ok = self._ensure_workspace_symlink()

    def _ensure_workspace_symlink(self) -> bool:
        """Create `<root>/workspace -> <root>` so absolute /workspace paths resolve."""

        link = self._root / "workspace"
        target = self._root
        try:
            if link.is_symlink():
                if Path(os.readlink(link)).resolve() == target:
                    return True
                link.unlink()
            elif link.exists():
                return False
            link.symlink_to(target, target_is_directory=True)
            return True
        except OSError as exc:
            logger.warning(
                "Local sandbox could not create workspace symlink at %s (%s). "
                "Falling back to /workspace path rewriting in execute().",
                link,
                exc,
            )
            return False

    @property
    def id(self) -> str:
        return self._id

    @property
    def root(self) -> Path:
        return self._root

    def _translate(self, path: str) -> str:
        """Rewrite a `/workspace/...` agent path to a host path under root."""

        if not path:
            return path
        if path == _WORKSPACE_PREFIX:
            return str(self._root)
        if path.startswith(_WORKSPACE_PREFIX + "/"):
            return str(self._root / path[len(_WORKSPACE_PREFIX) + 1 :])
        return path

    def _rewrite_command(self, command: str) -> str:
        """Rewrite `/workspace[/...]` in the command to the host root path.

        Absolute `/workspace/...` paths inside the command would otherwise
        resolve against the real filesystem root. The symlink at
        `<root>/workspace` only helps relative references; absolute ones must
        be rewritten before the shell sees them.
        """

        return _WORKSPACE_PREFIX_RE.sub(str(self._root), command)

    def assert_ready(self, *, timeout: int = 10) -> None:
        """Raise when the local sandbox root is missing, unwritable, or bash is absent."""

        if not self._root.exists():
            raise RuntimeError(
                f"Local sandbox 루트 '{self._root}'가 존재하지 않습니다."
            )
        if not self._root.is_dir():
            raise RuntimeError(
                f"Local sandbox 루트 '{self._root}'가 디렉토리가 아닙니다."
            )

        for sub in ("uploads", "output"):
            target = self._root / sub
            target.mkdir(parents=True, exist_ok=True)
            probe = target / f".sandbox_probe_{uuid.uuid4().hex}"
            try:
                probe.write_bytes(b"ok")
                probe.unlink()
            except OSError as exc:
                raise RuntimeError(
                    f"Local sandbox '{target}'에 쓰기 권한이 없습니다: {exc}"
                ) from exc

        if shutil.which("bash") is None:
            raise RuntimeError(
                "Local sandbox에 필요한 'bash' 실행 파일을 PATH에서 찾을 수 없습니다."
            )

        try:
            probe_result = subprocess.run(
                ["bash", "-lc", "printf '__sandbox_ready__'"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._root),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Local sandbox 준비 확인이 {timeout}초 내에 완료되지 않았습니다."
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Local sandbox 준비 확인 중 예외가 발생했습니다: {exc}"
            ) from exc

        if probe_result.returncode != 0 or probe_result.stdout != "__sandbox_ready__":
            err = (probe_result.stderr or probe_result.stdout or "").strip()
            raise RuntimeError(
                f"Local sandbox bash 실행 확인이 실패했습니다: {err or 'unknown error'}"
            )

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        effective_timeout = timeout or self._timeout
        rewritten = self._rewrite_command(command)
        try:
            result = subprocess.run(
                ["bash", "-lc", rewritten],
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=str(self._root),
            )
            output = (result.stdout or "") + (result.stderr or "")
            return ExecuteResponse(
                output=output,
                exit_code=result.returncode,
                truncated=False,
            )
        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                output=f"Command timed out after {effective_timeout}s",
                exit_code=124,
                truncated=True,
            )
        except Exception as exc:  # pragma: no cover - passthrough error handling
            return ExecuteResponse(
                output=str(exc),
                exit_code=1,
                truncated=False,
            )

    def ls(self, path: str) -> LsResult:
        result = super().ls(self._translate(path))
        prefix = str(self._root)
        rewritten: list = []
        for entry in result.entries:
            host_path = entry.get("path", "")
            if host_path.startswith(prefix):
                tail = host_path[len(prefix):].lstrip("/")
                agent_path = _WORKSPACE_PREFIX if not tail else f"{_WORKSPACE_PREFIX}/{tail}"
                entry = {**entry, "path": agent_path}
            rewritten.append(entry)
        return LsResult(entries=rewritten)

    def read(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> ReadResult:
        return super().read(self._translate(file_path), offset=offset, limit=limit)

    def write(self, file_path: str, content: str) -> WriteResult:
        result = super().write(self._translate(file_path), content)
        if result.path:
            return WriteResult(path=file_path)
        return result

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        results: list[FileUploadResponse] = []
        for path, content in files:
            host_path = Path(self._translate(path))
            try:
                host_path.parent.mkdir(parents=True, exist_ok=True)
                host_path.write_bytes(content)
                results.append(FileUploadResponse(path=path, error=None))
            except Exception as exc:  # pragma: no cover - passthrough error handling
                results.append(FileUploadResponse(path=path, error=str(exc)))
        return results

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        results: list[FileDownloadResponse] = []
        for path in paths:
            host_path = Path(self._translate(path))
            try:
                if not host_path.exists():
                    results.append(
                        FileDownloadResponse(path=path, content=b"", error="file_not_found")
                    )
                    continue
                if host_path.is_dir():
                    results.append(
                        FileDownloadResponse(path=path, content=b"", error="is_directory")
                    )
                    continue
                results.append(
                    FileDownloadResponse(path=path, content=host_path.read_bytes(), error=None)
                )
            except Exception as exc:  # pragma: no cover - passthrough error handling
                results.append(
                    FileDownloadResponse(path=path, content=b"", error=str(exc))
                )
        return results
