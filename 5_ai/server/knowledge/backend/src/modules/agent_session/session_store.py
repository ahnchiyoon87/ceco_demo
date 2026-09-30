"""SQLite-backed session store for persisting conversation history."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "sessions.db"
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection (created lazily)."""

    conn = getattr(_local, "conn", None)
    if conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""

    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL DEFAULT '',
            mode        TEXT NOT NULL DEFAULT '',
            schema_name TEXT NOT NULL DEFAULT '',
            created_at  REAL NOT NULL,
            updated_at  REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            mode        TEXT NOT NULL,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            metadata    TEXT NOT NULL DEFAULT '{}',
            created_at  REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session_mode
            ON messages(session_id, mode, id);

        CREATE TABLE IF NOT EXISTS build_context (
            session_id  TEXT PRIMARY KEY,
            context_json TEXT NOT NULL DEFAULT '{}',
            updated_at  REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS frontend_state (
            session_id  TEXT NOT NULL,
            mode        TEXT NOT NULL,
            state_json  TEXT NOT NULL DEFAULT '[]',
            updated_at  REAL NOT NULL,
            PRIMARY KEY (session_id, mode),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
    """)
    # Migrate: add mode column if missing (existing DBs)
    try:
        conn.execute("SELECT mode FROM sessions LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE sessions ADD COLUMN mode TEXT NOT NULL DEFAULT ''")
    # Migrate: add schema_name column if missing
    try:
        conn.execute("SELECT schema_name FROM sessions LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE sessions ADD COLUMN schema_name TEXT NOT NULL DEFAULT ''")
    conn.commit()
    # Ensure ontology schema tables exist
    _ensure_schema_tables()


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

def list_sessions(mode_filter: str = "") -> list[dict[str, Any]]:
    """Return all sessions ordered by most recent first, optionally filtered by mode."""

    conn = _get_conn()
    if mode_filter:
        rows = conn.execute(
            "SELECT id, title, mode, schema_name, created_at, updated_at FROM sessions "
            "WHERE mode = ? ORDER BY updated_at DESC",
            (mode_filter,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, mode, schema_name, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
    return [
        {"id": r[0], "title": r[1], "mode": r[2], "schema_name": r[3], "created_at": r[4], "updated_at": r[5]}
        for r in rows
    ]


def get_session(session_id: str) -> dict[str, Any] | None:
    """Return a single session metadata or None."""

    conn = _get_conn()
    row = conn.execute(
        "SELECT id, title, mode, schema_name, created_at, updated_at FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return {"id": row[0], "title": row[1], "mode": row[2], "schema_name": row[3], "created_at": row[4], "updated_at": row[5]}


def ensure_session(session_id: str, title: str = "", mode: str = "", schema_name: str = "") -> dict[str, Any]:
    """Create session if it doesn't exist; return session metadata."""

    existing = get_session(session_id)
    if existing:
        return existing
    now = time.time()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO sessions (id, title, mode, schema_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, title, mode, schema_name, now, now),
    )
    conn.commit()
    return {"id": session_id, "title": title, "mode": mode, "schema_name": schema_name, "created_at": now, "updated_at": now}


def update_session_title(session_id: str, title: str) -> None:
    """Update the title of an existing session."""

    conn = _get_conn()
    conn.execute(
        "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
        (title, time.time(), session_id),
    )
    conn.commit()


def update_session_schema_name(session_id: str, schema_name: str) -> None:
    """Update the schema_name of an existing session."""

    conn = _get_conn()
    conn.execute(
        "UPDATE sessions SET schema_name = ?, updated_at = ? WHERE id = ?",
        (schema_name, time.time(), session_id),
    )
    conn.commit()


def touch_session(session_id: str) -> None:
    """Bump updated_at timestamp."""

    conn = _get_conn()
    conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (time.time(), session_id),
    )
    conn.commit()


def delete_session(session_id: str) -> None:
    """Delete a session and all its messages (CASCADE)."""

    conn = _get_conn()
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Message persistence
# ---------------------------------------------------------------------------

def _serialize_message(msg: Any) -> dict[str, Any]:
    """Convert a LangChain message to a serializable dict."""

    if isinstance(msg, HumanMessage):
        return {"role": "human", "content": msg.content, "metadata": {}}
    elif isinstance(msg, AIMessage):
        meta: dict[str, Any] = {}
        if msg.tool_calls:
            meta["tool_calls"] = msg.tool_calls
        return {"role": "ai", "content": msg.content, "metadata": meta}
    elif isinstance(msg, ToolMessage):
        return {
            "role": "tool",
            "content": msg.content if isinstance(msg.content, str) else str(msg.content),
            "metadata": {
                "tool_call_id": msg.tool_call_id,
                "name": msg.name or "",
            },
        }
    # Fallback
    return {
        "role": "unknown",
        "content": str(getattr(msg, "content", "")),
        "metadata": {},
    }


def _deserialize_message(row: dict[str, Any]) -> Any:
    """Reconstruct a LangChain message from stored data."""

    role = row["role"]
    content = row["content"]
    meta = row.get("metadata", {})

    if role == "human":
        return HumanMessage(content=content)
    elif role == "ai":
        tool_calls = meta.get("tool_calls", [])
        return AIMessage(content=content, tool_calls=tool_calls)
    elif role == "tool":
        return ToolMessage(
            content=content,
            tool_call_id=meta.get("tool_call_id", ""),
            name=meta.get("name", ""),
        )
    # Fallback: treat as human
    return HumanMessage(content=content)


def save_messages(session_id: str, mode: str, messages: list) -> None:
    """Replace all messages for a session+mode with the given list."""

    conn = _get_conn()
    conn.execute(
        "DELETE FROM messages WHERE session_id = ? AND mode = ?",
        (session_id, mode),
    )
    now = time.time()
    rows = []
    for msg in messages:
        serialized = _serialize_message(msg)
        rows.append((
            session_id,
            mode,
            serialized["role"],
            serialized["content"],
            json.dumps(serialized["metadata"], ensure_ascii=False),
            now,
        ))
    if rows:
        conn.executemany(
            "INSERT INTO messages (session_id, mode, role, content, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
    conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    conn.commit()


def load_messages(session_id: str, mode: str) -> list:
    """Load all messages for a session+mode, ordered by insertion order."""

    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content, metadata FROM messages "
        "WHERE session_id = ? AND mode = ? ORDER BY id",
        (session_id, mode),
    ).fetchall()
    result = []
    for role, content, metadata_str in rows:
        meta = json.loads(metadata_str) if metadata_str else {}
        result.append(_deserialize_message({"role": role, "content": content, "metadata": meta}))
    return result


def append_message(session_id: str, mode: str, msg: Any) -> None:
    """Append a single message (used during streaming for incremental saves)."""

    conn = _get_conn()
    serialized = _serialize_message(msg)
    now = time.time()
    conn.execute(
        "INSERT INTO messages (session_id, mode, role, content, metadata, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            session_id,
            mode,
            serialized["role"],
            serialized["content"],
            json.dumps(serialized["metadata"], ensure_ascii=False),
            now,
        ),
    )
    conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    conn.commit()


def delete_session_messages(session_id: str) -> None:
    """Delete all messages for a session (both modes)."""

    conn = _get_conn()
    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM frontend_state WHERE session_id = ?", (session_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Frontend state persistence
# ---------------------------------------------------------------------------

def save_frontend_state(session_id: str, mode: str, state_json: str) -> None:
    """Save (upsert) serialised frontend messages for a session+mode."""

    conn = _get_conn()
    now = time.time()
    conn.execute(
        "INSERT INTO frontend_state (session_id, mode, state_json, updated_at) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(session_id, mode) DO UPDATE SET state_json = excluded.state_json, "
        "updated_at = excluded.updated_at",
        (session_id, mode, state_json, now),
    )
    conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    conn.commit()


def load_frontend_state(session_id: str, mode: str) -> str | None:
    """Load serialised frontend messages for a session+mode, or None."""

    conn = _get_conn()
    row = conn.execute(
        "SELECT state_json FROM frontend_state WHERE session_id = ? AND mode = ?",
        (session_id, mode),
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Build context persistence (for resuming interrupted builds)
# ---------------------------------------------------------------------------

def save_build_context(session_id: str, context_json: str) -> None:
    """Save (upsert) build context for a session."""

    conn = _get_conn()
    now = time.time()
    conn.execute(
        "INSERT INTO build_context (session_id, context_json, updated_at) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET context_json = excluded.context_json, "
        "updated_at = excluded.updated_at",
        (session_id, context_json, now),
    )
    conn.commit()


def load_build_context(session_id: str) -> str | None:
    """Load saved build context for a session, or None."""

    conn = _get_conn()
    row = conn.execute(
        "SELECT context_json FROM build_context WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Ontology Schema persistence (survives Neo4j resets)
# ---------------------------------------------------------------------------

def _ensure_schema_tables() -> None:
    """Create ontology schema tables if they don't exist."""

    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ontology_schemas (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            intent      TEXT NOT NULL DEFAULT '',
            golden_questions TEXT NOT NULL DEFAULT '[]',
            created_at  REAL NOT NULL,
            updated_at  REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS schema_classes (
            schema_id   TEXT NOT NULL,
            class_name  TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            properties  TEXT NOT NULL DEFAULT '[]',
            created_at  REAL NOT NULL,
            PRIMARY KEY (schema_id, class_name),
            FOREIGN KEY (schema_id) REFERENCES ontology_schemas(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS schema_relationships (
            schema_id   TEXT NOT NULL,
            name        TEXT NOT NULL,
            from_class  TEXT NOT NULL,
            to_class    TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            properties  TEXT NOT NULL DEFAULT '[]',
            created_at  REAL NOT NULL,
            PRIMARY KEY (schema_id, name, from_class, to_class),
            FOREIGN KEY (schema_id) REFERENCES ontology_schemas(id) ON DELETE CASCADE
        );
    """)
    # Migrate: add intent/golden_questions columns if missing
    try:
        conn.execute("SELECT intent FROM ontology_schemas LIMIT 1")
    except Exception:
        conn.execute("ALTER TABLE ontology_schemas ADD COLUMN intent TEXT NOT NULL DEFAULT ''")
        conn.execute("ALTER TABLE ontology_schemas ADD COLUMN golden_questions TEXT NOT NULL DEFAULT '[]'")
    conn.commit()


import uuid as _uuid


def create_schema(name: str, description: str = "", intent: str = "", golden_questions: str = "[]") -> dict[str, Any]:
    """Create or return an ontology schema group."""

    _ensure_schema_tables()
    conn = _get_conn()
    # Check if already exists
    row = conn.execute(
        "SELECT id, name, description, intent, golden_questions, created_at, updated_at "
        "FROM ontology_schemas WHERE name = ?",
        (name,),
    ).fetchone()
    if row:
        return {"id": row[0], "name": row[1], "description": row[2],
                "intent": row[3], "golden_questions": json.loads(row[4]) if row[4] else [],
                "created_at": row[5], "updated_at": row[6]}
    schema_id = _uuid.uuid4().hex[:12]
    now = time.time()
    conn.execute(
        "INSERT INTO ontology_schemas (id, name, description, intent, golden_questions, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (schema_id, name, description, intent, golden_questions, now, now),
    )
    conn.commit()
    return {"id": schema_id, "name": name, "description": description,
            "intent": intent, "golden_questions": json.loads(golden_questions) if golden_questions else [],
            "created_at": now, "updated_at": now}


def update_schema_brief(schema_id: str, intent: str, golden_questions: str) -> None:
    """Update the intent and golden questions for a schema."""

    _ensure_schema_tables()
    conn = _get_conn()
    now = time.time()
    conn.execute(
        "UPDATE ontology_schemas SET intent = ?, golden_questions = ?, updated_at = ? WHERE id = ?",
        (intent, golden_questions, now, schema_id),
    )
    conn.commit()


def list_schemas() -> list[dict[str, Any]]:
    """Return all ontology schemas with their class lists."""

    _ensure_schema_tables()
    conn = _get_conn()
    schemas = conn.execute(
        "SELECT id, name, description, intent, golden_questions, created_at, updated_at "
        "FROM ontology_schemas ORDER BY updated_at DESC"
    ).fetchall()
    result = []
    for s in schemas:
        classes = conn.execute(
            "SELECT class_name, description, properties FROM schema_classes WHERE schema_id = ?",
            (s[0],),
        ).fetchall()
        rels = conn.execute(
            "SELECT name, from_class, to_class, description, properties "
            "FROM schema_relationships WHERE schema_id = ?",
            (s[0],),
        ).fetchall()
        result.append({
            "id": s[0], "name": s[1], "description": s[2],
            "intent": s[3] or "", "golden_questions": json.loads(s[4]) if s[4] else [],
            "created_at": s[5], "updated_at": s[6],
            "classes": [
                {"class_name": c[0], "description": c[1],
                 "properties": json.loads(c[2]) if c[2] else []}
                for c in classes
            ],
            "relationships": [
                {"name": r[0], "from_class": r[1], "to_class": r[2],
                 "description": r[3], "properties": json.loads(r[4]) if r[4] else []}
                for r in rels
            ],
        })
    return result


def get_schema(schema_id: str) -> dict[str, Any] | None:
    """Return a single ontology schema with classes and relationships."""

    _ensure_schema_tables()
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, name, description, intent, golden_questions, created_at, updated_at "
        "FROM ontology_schemas WHERE id = ?",
        (schema_id,),
    ).fetchone()
    if not row:
        return None
    classes = conn.execute(
        "SELECT class_name, description, properties FROM schema_classes WHERE schema_id = ?",
        (schema_id,),
    ).fetchall()
    rels = conn.execute(
        "SELECT name, from_class, to_class, description, properties "
        "FROM schema_relationships WHERE schema_id = ?",
        (schema_id,),
    ).fetchall()
    return {
        "id": row[0], "name": row[1], "description": row[2],
        "intent": row[3] or "", "golden_questions": json.loads(row[4]) if row[4] else [],
        "created_at": row[5], "updated_at": row[6],
        "classes": [
            {"class_name": c[0], "description": c[1],
             "properties": json.loads(c[2]) if c[2] else []}
            for c in classes
        ],
        "relationships": [
            {"name": r[0], "from_class": r[1], "to_class": r[2],
             "description": r[3], "properties": json.loads(r[4]) if r[4] else []}
            for r in rels
        ],
    }


def get_schema_by_name(name: str) -> dict[str, Any] | None:
    """Return a schema by name (exact match first, then partial/LIKE fallback)."""

    _ensure_schema_tables()
    conn = _get_conn()
    # Exact match
    row = conn.execute(
        "SELECT id FROM ontology_schemas WHERE name = ?", (name,),
    ).fetchone()
    if not row:
        # Partial match: schema name contains the query or query contains schema name
        row = conn.execute(
            "SELECT id FROM ontology_schemas WHERE name LIKE ? ORDER BY updated_at DESC LIMIT 1",
            (f"%{name}%",),
        ).fetchone()
    if not row:
        return None
    return get_schema(row[0])


def delete_schema(schema_id: str) -> None:
    """Delete an ontology schema and its class/relationship metadata (CASCADE)."""

    conn = _get_conn()
    conn.execute("DELETE FROM ontology_schemas WHERE id = ?", (schema_id,))
    conn.commit()


def add_class_to_schema(
    schema_id: str, class_name: str,
    description: str = "", properties_json: str = "[]",
) -> None:
    """Add or update a class in a schema."""

    _ensure_schema_tables()
    conn = _get_conn()
    now = time.time()
    conn.execute(
        "INSERT INTO schema_classes (schema_id, class_name, description, properties, created_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(schema_id, class_name) DO UPDATE SET "
        "description = excluded.description, properties = excluded.properties",
        (schema_id, class_name, description, properties_json, now),
    )
    conn.execute(
        "UPDATE ontology_schemas SET updated_at = ? WHERE id = ?",
        (now, schema_id),
    )
    conn.commit()


def remove_class_from_schema(schema_id: str, class_name: str) -> None:
    """Remove a class from a schema."""

    conn = _get_conn()
    conn.execute(
        "DELETE FROM schema_classes WHERE schema_id = ? AND class_name = ?",
        (schema_id, class_name),
    )
    conn.commit()


def list_classes_for_schema(schema_id: str) -> list[dict[str, Any]]:
    """Return all classes belonging to a schema."""

    _ensure_schema_tables()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT class_name, description, properties FROM schema_classes WHERE schema_id = ?",
        (schema_id,),
    ).fetchall()
    return [
        {"class_name": r[0], "description": r[1],
         "properties": json.loads(r[2]) if r[2] else []}
        for r in rows
    ]


def find_schemas_for_class(class_name: str) -> list[dict[str, Any]]:
    """Find all schemas that contain a given class name (for merge detection)."""

    _ensure_schema_tables()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT s.id, s.name, s.description "
        "FROM ontology_schemas s "
        "JOIN schema_classes sc ON s.id = sc.schema_id "
        "WHERE sc.class_name = ?",
        (class_name,),
    ).fetchall()
    return [{"id": r[0], "name": r[1], "description": r[2]} for r in rows]


def add_relationship_to_schema(
    schema_id: str, name: str, from_class: str, to_class: str,
    description: str = "", properties_json: str = "[]",
) -> None:
    """Add or update a relationship type in a schema."""

    _ensure_schema_tables()
    conn = _get_conn()
    now = time.time()
    conn.execute(
        "INSERT INTO schema_relationships "
        "(schema_id, name, from_class, to_class, description, properties, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(schema_id, name, from_class, to_class) DO UPDATE SET "
        "description = excluded.description, properties = excluded.properties",
        (schema_id, name, from_class, to_class, description, properties_json, now),
    )
    conn.execute(
        "UPDATE ontology_schemas SET updated_at = ? WHERE id = ?",
        (now, schema_id),
    )
    conn.commit()


def remove_class_from_all_schemas(class_name: str) -> None:
    """Remove a class from every schema that contains it."""

    _ensure_schema_tables()
    conn = _get_conn()
    conn.execute("DELETE FROM schema_classes WHERE class_name = ?", (class_name,))
    conn.commit()


def rename_class_in_all_schemas(old_name: str, new_name: str) -> None:
    """Rename a class across all schemas and update relationship references."""

    _ensure_schema_tables()
    conn = _get_conn()
    now = time.time()
    conn.execute(
        "UPDATE schema_classes SET class_name = ? WHERE class_name = ?",
        (new_name, old_name),
    )
    conn.execute(
        "UPDATE schema_relationships SET from_class = ? WHERE from_class = ?",
        (new_name, old_name),
    )
    conn.execute(
        "UPDATE schema_relationships SET to_class = ? WHERE to_class = ?",
        (new_name, old_name),
    )
    # Update timestamps of affected schemas
    schema_ids = conn.execute(
        "SELECT DISTINCT schema_id FROM schema_classes WHERE class_name = ?",
        (new_name,),
    ).fetchall()
    for (sid,) in schema_ids:
        conn.execute(
            "UPDATE ontology_schemas SET updated_at = ? WHERE id = ?",
            (now, sid),
        )
    conn.commit()


def remove_relationship_from_all_schemas(
    name: str, from_class: str, to_class: str,
) -> None:
    """Remove a relationship type from every schema that contains it."""

    _ensure_schema_tables()
    conn = _get_conn()
    conn.execute(
        "DELETE FROM schema_relationships WHERE name = ? AND from_class = ? AND to_class = ?",
        (name, from_class, to_class),
    )
    conn.commit()


def list_relationships_for_schema(schema_id: str) -> list[dict[str, Any]]:
    """Return all relationship types belonging to a schema."""

    _ensure_schema_tables()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT name, from_class, to_class, description, properties "
        "FROM schema_relationships WHERE schema_id = ?",
        (schema_id,),
    ).fetchall()
    return [
        {"name": r[0], "from_class": r[1], "to_class": r[2],
         "description": r[3], "properties": json.loads(r[4]) if r[4] else []}
        for r in rows
    ]
