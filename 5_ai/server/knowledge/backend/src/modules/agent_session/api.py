"""HTTP API for agent session streaming, reset, and session management."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

from ..files.service import clear_workspace_files
from .service import clear_session, generate_sse
from .session_store import (
    delete_session,
    ensure_session,
    list_sessions,
    load_frontend_state,
    save_frontend_state,
    update_session_title,
    update_session_schema_name,
)

router = APIRouter(tags=["agent-session"])


@router.get("/api/stream")
async def stream_endpoint(
    prompt: str = "",
    session_id: str = "default",
    mode: Literal["build", "answer"] = "build",
    build_context: str = "",
):
    """Stream agent events to the frontend via SSE."""

    if not prompt:
        return {"error": "prompt is required"}
    return StreamingResponse(
        generate_sse(prompt, session_id, mode, build_context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/session/reset")
async def reset_session(session_id: str = "default"):
    """Reset in-memory session state and sandbox workspace files."""

    clear_session(session_id)
    clear_workspace_files()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

@router.get("/api/sessions")
async def get_sessions():
    """Return all saved sessions, most recent first."""

    return {"sessions": list_sessions()}


@router.post("/api/sessions")
async def create_session(title: str = "", mode: str = "", schema_name: str = ""):
    """Create a new session and return its metadata."""

    session_id = uuid.uuid4().hex[:12]
    session = ensure_session(session_id, title=title or "새 대화", mode=mode, schema_name=schema_name)
    return session


@router.delete("/api/sessions/{session_id}")
async def remove_session(session_id: str):
    """Delete a session and all its messages."""

    clear_session(session_id)
    delete_session(session_id)
    return {"status": "ok"}


@router.patch("/api/sessions/{session_id}")
async def patch_session(session_id: str, title: str = "", schema_name: str = ""):
    """Update session title and/or schema_name."""

    if title:
        update_session_title(session_id, title)
    if schema_name:
        update_session_schema_name(session_id, schema_name)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Frontend message state persistence
# ---------------------------------------------------------------------------

@router.get("/api/sessions/{session_id}/messages")
async def get_frontend_messages(session_id: str, mode: Literal["build", "answer"] = "build"):
    """Load saved frontend messages for a session+mode."""

    state = load_frontend_state(session_id, mode)
    if state is None:
        return {"messages": []}
    import json
    return {"messages": json.loads(state)}


@router.put("/api/sessions/{session_id}/messages")
async def put_frontend_messages(
    session_id: str,
    mode: Literal["build", "answer"] = "build",
    messages: list = Body(...),
):
    """Save frontend messages for a session+mode."""

    import json
    save_frontend_state(session_id, mode, json.dumps(messages, ensure_ascii=False))
    return {"status": "ok"}
