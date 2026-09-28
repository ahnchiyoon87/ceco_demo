"""Backend-agnostic workspace operations (uploads / outputs).

In Docker mode, files live in `/workspace/{uploads,output}` inside the sandbox
container, with a duplicated host-side cache at `<repo>/.cache/uploads` for
OCR/indexing reads. In local mode, the canonical location is
`<LOCAL_SANDBOX_ROOT>/{uploads,output}` on the host filesystem and the duplicate
cache is unnecessary.

This module hides the backend choice behind a small set of helpers so the
files-module API and the agent-session continuation prompt do not need to
branch on `settings.sandbox_backend` themselves.
"""

from __future__ import annotations

import subprocess
import unicodedata
import uuid
from pathlib import Path

from ...shared.kernel.settings import get_local_sandbox_root, get_settings


_REPO_ROOT = Path(__file__).resolve().parents[4]
_DOCKER_LOCAL_UPLOAD_ROOT = _REPO_ROOT / ".cache" / "uploads"


def _is_local() -> bool:
    return (get_settings().sandbox_backend or "docker").lower() == "local"


def _local_root() -> Path:
    settings = get_settings()
    return Path(settings.local_sandbox_root) if settings.local_sandbox_root else get_local_sandbox_root()


def get_repo_root() -> Path:
    return _REPO_ROOT


def get_cache_root() -> Path:
    return _REPO_ROOT / ".cache"


def get_local_upload_root() -> Path:
    """The host directory consumed by OCR/indexing for upload reads."""

    if _is_local():
        return _local_root() / "uploads"
    return _DOCKER_LOCAL_UPLOAD_ROOT


def _local_output_root() -> Path:
    return _local_root() / "output"


def ensure_workspace_dirs() -> None:
    """Create upload/output workspace directories for the active backend."""

    if _is_local():
        root = _local_root()
        (root / "uploads").mkdir(parents=True, exist_ok=True)
        (root / "output").mkdir(parents=True, exist_ok=True)
        return

    _DOCKER_LOCAL_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    subprocess.run(
        [
            "docker",
            "exec",
            settings.container_name,
            "mkdir",
            "-p",
            "/workspace/uploads",
            "/workspace/output",
        ],
        capture_output=True,
    )


def _format_file_size(size_bytes: int) -> str:
    size = float(max(size_bytes, 0))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            rounded = round(size, 1)
            if rounded.is_integer():
                return f"{int(rounded)} {unit}"
            return f"{rounded:.1f} {unit}"
        size /= 1024
    return "0 B"


def write_upload(filename: str, content: bytes) -> dict:
    """Persist an uploaded file to the active backend's uploads location.

    Returns the per-file response shape used by `/api/upload`.
    """

    name = unicodedata.normalize("NFC", filename or "unknown")
    container_path = f"/workspace/uploads/{name}"

    if _is_local():
        target = _local_root() / "uploads" / name
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            return {
                "name": name,
                "path": container_path,
                "local_path": str(target),
                "size": len(content),
            }
        except OSError as exc:
            return {"name": name, "error": str(exc)}

    # Docker mode: keep the duplicated host cache for OCR + atomic container move.
    settings = get_settings()
    _DOCKER_LOCAL_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    local_path = _DOCKER_LOCAL_UPLOAD_ROOT / name
    local_path.write_bytes(content)

    tmp_name = f"/tmp/_upload_{uuid.uuid4().hex}"
    Path(tmp_name).write_bytes(content)
    tmp_container = f"/workspace/uploads/_tmp_{uuid.uuid4().hex}"
    cp = subprocess.run(
        ["docker", "cp", tmp_name, f"{settings.container_name}:{tmp_container}"],
        capture_output=True,
    )
    Path(tmp_name).unlink(missing_ok=True)
    if cp.returncode == 0:
        subprocess.run(
            [
                "docker",
                "exec",
                settings.container_name,
                "mv",
                tmp_container,
                container_path,
            ],
            capture_output=True,
        )
        return {
            "name": name,
            "path": container_path,
            "local_path": str(local_path),
            "size": len(content),
        }

    return {
        "name": name,
        "local_path": str(local_path),
        "error": cp.stderr.decode() if cp.stderr else "upload failed",
    }


def list_local_upload_files() -> list[Path]:
    root = get_local_upload_root()
    if not root.exists():
        return []
    return sorted(
        [p for p in root.iterdir() if p.is_file()],
        key=lambda p: p.name.lower(),
    )


def list_uploads() -> list[dict]:
    return [
        {"name": p.name, "size": _format_file_size(p.stat().st_size)}
        for p in list_local_upload_files()
    ]


def list_outputs() -> list[dict]:
    if _is_local():
        root = _local_output_root()
        if not root.exists():
            return []
        return [
            {"name": p.name, "size": _format_file_size(p.stat().st_size)}
            for p in sorted(
                (p for p in root.iterdir() if p.is_file()),
                key=lambda p: p.name.lower(),
            )
        ]

    settings = get_settings()
    result = subprocess.run(
        [
            "docker",
            "exec",
            settings.container_name,
            "bash",
            "-c",
            "ls -lh /workspace/output/ 2>/dev/null",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    out: list[dict] = []
    for line in result.stdout.strip().splitlines():
        if not line or line.startswith("total"):
            continue
        parts = line.split()
        if len(parts) >= 9:
            out.append({"name": " ".join(parts[8:]), "size": parts[4]})
    return out


def list_output_filenames() -> list[str]:
    if _is_local():
        root = _local_output_root()
        if not root.exists():
            return []
        return sorted(p.name for p in root.iterdir() if p.is_file())

    settings = get_settings()
    scan = subprocess.run(
        ["docker", "exec", settings.container_name, "ls", "/workspace/output/"],
        capture_output=True,
        text=True,
    )
    if scan.returncode != 0:
        return []
    return [name for name in scan.stdout.strip().split("\n") if name]


def resolve_output_for_download(filename: str) -> str | None:
    """Return a host-readable path FastAPI's FileResponse can serve, or None."""

    if _is_local():
        candidate = _local_output_root() / filename
        return str(candidate) if candidate.is_file() else None

    settings = get_settings()
    local_path = f"/tmp/_dl_{uuid.uuid4().hex}_{Path(filename).name}"
    container_path = f"/workspace/output/{filename}"
    cp = subprocess.run(
        ["docker", "cp", f"{settings.container_name}:{container_path}", local_path],
        capture_output=True,
    )
    return local_path if cp.returncode == 0 else None


def delete_upload(filename: str) -> bool:
    name = unicodedata.normalize("NFC", filename)

    if _is_local():
        target = _local_root() / "uploads" / name
        if target.exists():
            target.unlink(missing_ok=True)
            return True
        return False

    settings = get_settings()
    local = _DOCKER_LOCAL_UPLOAD_ROOT / name
    deleted = False
    if local.exists():
        local.unlink(missing_ok=True)
        deleted = True
    subprocess.run(
        [
            "docker",
            "exec",
            settings.container_name,
            "rm",
            "-f",
            f"/workspace/uploads/{name}",
        ],
        capture_output=True,
    )
    return deleted


def clear_workspace() -> None:
    if _is_local():
        for sub in ("uploads", "output"):
            target = _local_root() / sub
            if target.exists():
                for p in target.iterdir():
                    if p.is_file():
                        p.unlink(missing_ok=True)
        return

    settings = get_settings()
    subprocess.run(
        [
            "docker",
            "exec",
            settings.container_name,
            "bash",
            "-c",
            "rm -rf /workspace/output/* /workspace/uploads/*",
        ],
        capture_output=True,
    )
    if _DOCKER_LOCAL_UPLOAD_ROOT.exists():
        for p in _DOCKER_LOCAL_UPLOAD_ROOT.iterdir():
            if p.is_file():
                p.unlink(missing_ok=True)
