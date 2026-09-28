"""Sandbox tools wrapping the active backend for use with create_agent."""

from __future__ import annotations

import json

from ...shared.sandbox import get_sandbox_backend


def _get_backend():
    return get_sandbox_backend()


def ensure_sandbox_ready() -> None:
    """Fail fast when the active sandbox backend is unavailable during startup."""

    _get_backend().assert_ready()


def execute(command: str) -> str:
    """Execute a shell command (Python or bash) in the sandbox container. Use this for file exploration, running parser scripts, and any code execution."""

    try:
        result = _get_backend().execute(command, timeout=120)
        output = result.output or ""
        if result.exit_code != 0:
            return json.dumps({
                "exit_code": result.exit_code,
                "output": output[:3000],
            }, ensure_ascii=False)
        # Truncate long outputs to save context
        if len(output) > 3000:
            output = output[:3000] + "\n... [truncated]"
        return output
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def sandbox_ls(path: str = "/workspace/uploads") -> str:
    """List files in the sandbox directory."""

    try:
        result = _get_backend().ls(path)
        files = []
        for entry in result.entries:
            files.append({
                "path": entry.get("path", ""),
                "is_dir": entry.get("is_dir", False),
            })
        return json.dumps(files, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def sandbox_read(file_path: str, offset: int = 0, limit: int = 200) -> str:
    """Read file contents from the sandbox."""

    try:
        result = _get_backend().read(file_path, offset=offset, limit=limit)
        content = result.file_data or ""
        if len(content) > 3000:
            content = content[:3000] + "\n... [truncated]"
        return content
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def sandbox_write(file_path: str, content: str) -> str:
    """Write file contents to the sandbox."""

    try:
        _get_backend().write(file_path, content)
        return json.dumps({"status": "ok", "path": file_path}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
