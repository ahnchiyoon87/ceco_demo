"""File operations against the active sandbox workspace."""

from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from . import workspace as ws


def get_repo_root() -> Path:
    return ws.get_repo_root()


def get_cache_root() -> Path:
    return ws.get_cache_root()


def get_local_upload_root() -> Path:
    return ws.get_local_upload_root()


def ensure_workspace_dirs() -> None:
    ws.ensure_workspace_dirs()


async def save_uploads(files: list[UploadFile]) -> list[dict]:
    """Copy uploaded files into the active workspace."""

    ws.ensure_workspace_dirs()
    uploaded: list[dict] = []
    for uploaded_file in files:
        content = await uploaded_file.read()
        uploaded.append(ws.write_upload(uploaded_file.filename or "unknown", content))
    return uploaded


def list_workspace_files() -> dict:
    return {"uploads": ws.list_uploads(), "output": ws.list_outputs()}


def list_output_filenames() -> list[str]:
    return ws.list_output_filenames()


def list_local_upload_files() -> list[Path]:
    return ws.list_local_upload_files()


def copy_output_file(filename: str) -> str | None:
    return ws.resolve_output_for_download(filename)


def delete_upload_file(filename: str) -> bool:
    return ws.delete_upload(filename)


def clear_workspace_files() -> None:
    ws.clear_workspace()
