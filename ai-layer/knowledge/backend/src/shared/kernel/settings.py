"""Runtime settings shared across backend modules."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


_REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    sandbox_backend: str
    local_sandbox_root: str
    container_name: str
    sandbox_workdir: str
    major_model: str
    major_model_reasoning_effort: str
    minor_model: str
    minor_model_reasoning_effort: str
    ocr_model: str
    ocr_model_reasoning_effort: str
    ocr_embedding_model: str
    use_ocr_cache: bool
    openai_base_url: str
    openai_api_key: str
    backend_host: str
    backend_port: int
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    ollama_base_url: str
    ollama_embedding_model: str
    embedding_chunk_max_tokens: int
    mcp_transport: str
    mcp_host: str
    mcp_port: int
    mcp_max_results: int
    mcp_max_excerpt_chars: int


def _env_bool(name: str, default: bool) -> bool:
    """Parse a boolean-like environment variable."""

    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def get_local_sandbox_root() -> Path:
    """Return the absolute host directory used by the local sandbox backend."""

    raw = os.environ.get("LOCAL_SANDBOX_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _REPO_ROOT / ".cache" / "sandbox"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings(
        sandbox_backend=os.environ.get("SANDBOX_BACKEND", "docker").strip().lower() or "docker",
        local_sandbox_root=str(get_local_sandbox_root()),
        container_name=os.environ.get("CONTAINER_NAME", "deepagents-sandbox"),
        sandbox_workdir=os.environ.get("SANDBOX_WORKDIR", "/workspace"),
        major_model=os.environ.get("MAJOR_MODEL", "openai:gpt-5.4-2026-03-05"),
        major_model_reasoning_effort=os.environ.get(
            "MAJOR_MODEL_REASONING_EFFORT",
            "medium",
        ),
        minor_model=os.environ.get("MINOR_MODEL", "gpt-5.4-mini-2026-03-17"),
        minor_model_reasoning_effort=os.environ.get(
            "MINOR_MODEL_REASONING_EFFORT",
            "medium",
        ),
        ocr_model=os.environ.get("OCR_MODEL", "gpt-5.4-mini-2026-03-17"),
        ocr_model_reasoning_effort=os.environ.get(
            "OCR_MODEL_REASONING_EFFORT",
            "none",
        ),
        ocr_embedding_model=os.environ.get(
            "OCR_EMBEDDING_MODEL",
            "openai:text-embedding-3-small",
        ),
        use_ocr_cache=_env_bool("USE_OCR_CACHE", False),
        openai_base_url=os.environ.get("OPENAI_BASE_URL", ""),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        backend_host=os.environ.get("BACKEND_HOST", "0.0.0.0"),
        backend_port=int(os.environ.get("BACKEND_PORT", "8000")),
        neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD", ""),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_embedding_model=os.environ.get("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding"),
        embedding_chunk_max_tokens=int(os.environ.get("EMBEDDING_CHUNK_MAX_TOKENS", "1000")),
        mcp_transport=os.environ.get("MCP_TRANSPORT", "stdio").strip().lower() or "stdio",
        mcp_host=os.environ.get("MCP_HOST", "0.0.0.0"),
        mcp_port=int(os.environ.get("MCP_PORT", "8100")),
        mcp_max_results=int(os.environ.get("MCP_MAX_RESULTS", "20")),
        mcp_max_excerpt_chars=int(os.environ.get("MCP_MAX_EXCERPT_CHARS", "500")),
    )
