"""HTTP API for sandbox file operations."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from .service import clear_workspace_files, copy_output_file, delete_upload_file, list_workspace_files, save_uploads

router = APIRouter(tags=["files"])


@router.post("/api/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    session_id: str = Form(""),
):
    """Upload user files into the sandbox workspace."""

    del session_id
    uploaded = await save_uploads(files)
    return {"uploaded": uploaded}


@router.get("/api/files")
async def list_files():
    """List uploaded and generated files."""

    return list_workspace_files()


@router.delete("/api/files/{filename:path}")
async def delete_file(filename: str):
    """Delete an uploaded file."""
    deleted = delete_upload_file(filename)
    if deleted:
        return {"status": "ok", "filename": filename}
    return {"status": "not_found", "filename": filename}


@router.get("/api/download/{filename:path}")
async def download_file(filename: str):
    """Download a generated output file from the sandbox."""

    local_path = copy_output_file(filename)
    if local_path:
        return FileResponse(
            local_path,
            media_type="application/octet-stream",
            filename=filename.split("/")[-1],
        )
    return {"error": f"파일을 찾을 수 없습니다: {filename}"}


@router.post("/api/sandbox/clear")
async def clear_sandbox():
    """Delete all files in the sandbox /workspace directory."""
    try:
        clear_workspace_files()
        return {"status": "ok", "message": "샌드박스 파일이 모두 삭제되었습니다."}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
