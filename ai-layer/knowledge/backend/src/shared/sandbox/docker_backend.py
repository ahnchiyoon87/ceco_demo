"""Docker-backed sandbox implementation for DeepAgents."""

from __future__ import annotations

import subprocess
import uuid

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox


class DockerSandboxBackend(BaseSandbox):
    """Execute sandbox commands inside a named Docker container."""

    def __init__(
        self,
        container_name: str,
        workdir: str = "/workspace",
        timeout: int = 120,
    ) -> None:
        self._container_name = container_name
        self._workdir = workdir
        self._timeout = timeout
        self._id = str(uuid.uuid4())

    @property
    def id(self) -> str:
        return self._id

    def assert_ready(self, *, timeout: int = 10) -> None:
        """Raise when the sandbox container is not running or not exec-accessible."""

        try:
            inspect_result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "-f",
                    "{{.State.Running}}",
                    self._container_name,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Docker CLI를 찾을 수 없어 sandbox 컨테이너 상태를 확인할 수 없습니다."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Sandbox container '{self._container_name}' 상태 확인이 {timeout}초 내에 완료되지 않았습니다."
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Sandbox container '{self._container_name}' 상태 확인 중 예외가 발생했습니다: {exc}"
            ) from exc

        inspect_error = (inspect_result.stderr or inspect_result.stdout or "").strip()
        if inspect_result.returncode != 0:
            raise RuntimeError(
                f"Sandbox container '{self._container_name}' 정보를 조회할 수 없습니다: {inspect_error or 'unknown error'}"
            )

        if inspect_result.stdout.strip().lower() != "true":
            raise RuntimeError(
                f"Sandbox container '{self._container_name}'가 실행 중이 아닙니다."
            )

        try:
            exec_result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-w",
                    self._workdir,
                    self._container_name,
                    "bash",
                    "-lc",
                    "printf '__sandbox_ready__'",
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Sandbox container '{self._container_name}' 접근 확인이 {timeout}초 내에 완료되지 않았습니다."
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Sandbox container '{self._container_name}' 접근 확인 중 예외가 발생했습니다: {exc}"
            ) from exc

        exec_error = (exec_result.stderr or exec_result.stdout or "").strip()
        if exec_result.returncode != 0:
            raise RuntimeError(
                f"Sandbox container '{self._container_name}'에는 접근할 수 있지만 workdir '{self._workdir}'에서 실행할 수 없습니다: {exec_error or 'unknown error'}"
            )

        if exec_result.stdout != "__sandbox_ready__":
            raise RuntimeError(
                f"Sandbox container '{self._container_name}' 응답이 예상과 다릅니다."
            )

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        effective_timeout = timeout or self._timeout
        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-w",
                    self._workdir,
                    self._container_name,
                    "bash",
                    "-c",
                    command,
                ],
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )
            output = result.stdout + result.stderr
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

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        results = []
        for path, content in files:
            try:
                proc = subprocess.run(
                    ["docker", "cp", "-", f"{self._container_name}:{path}"],
                    input=content,
                    capture_output=True,
                    timeout=30,
                )
                if proc.returncode != 0:
                    import base64

                    b64 = base64.b64encode(content).decode()
                    self.execute(f"echo '{b64}' | base64 -d > {path}")
                results.append(FileUploadResponse(path=path, error=None))
            except Exception as exc:  # pragma: no cover - passthrough error handling
                results.append(FileUploadResponse(path=path, error=str(exc)))
        return results

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        results = []
        for path in paths:
            try:
                proc = subprocess.run(
                    ["docker", "cp", f"{self._container_name}:{path}", "/dev/stdout"],
                    capture_output=True,
                    timeout=30,
                )
                if proc.returncode == 0:
                    results.append(
                        FileDownloadResponse(path=path, content=proc.stdout, error=None)
                    )
                else:
                    import base64

                    resp = self.execute(f"base64 {path}")
                    content = base64.b64decode(resp.output.strip())
                    results.append(
                        FileDownloadResponse(path=path, content=content, error=None)
                    )
            except Exception as exc:  # pragma: no cover - passthrough error handling
                results.append(
                    FileDownloadResponse(path=path, content=b"", error=str(exc))
                )
        return results
