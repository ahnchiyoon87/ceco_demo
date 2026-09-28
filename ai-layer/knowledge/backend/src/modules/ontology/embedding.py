"""Embedding client for ontology entity nodes. Supports OpenAI and Ollama."""

from __future__ import annotations

import json
import logging
import urllib.request
from functools import lru_cache
from typing import Any

import tiktoken

from ...shared.kernel.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_tokenizer() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def truncate_by_tokens(text: str, max_tokens: int | None = None) -> str:
    """Truncate *text* so that it fits within *max_tokens* (tiktoken cl100k_base).

    If *max_tokens* is ``None`` the value from ``EMBEDDING_CHUNK_MAX_TOKENS``
    (default 1000) is used.
    """
    if not text:
        return text
    if max_tokens is None:
        max_tokens = get_settings().embedding_chunk_max_tokens
    enc = _get_tokenizer()
    token_ids = enc.encode(text)
    if len(token_ids) <= max_tokens:
        return text
    return enc.decode(token_ids[:max_tokens])


def _is_openai_mode() -> bool:
    """True when using OpenAI API (not Ollama)."""
    settings = get_settings()
    return bool(settings.openai_api_key and settings.openai_api_key != "frentis"
                and not settings.openai_base_url)


def _openai_embed(texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
    """Call OpenAI embeddings API."""
    settings = get_settings()
    payload = json.dumps({
        "model": model,
        "input": texts,
    }).encode("utf-8")

    base = settings.openai_base_url or "https://api.openai.com/v1"
    req = urllib.request.Request(
        f"{base}/embeddings",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.openai_api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        # Sort by index to ensure order
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]


def _ollama_embed(texts: list[str]) -> list[list[float]]:
    """Call Ollama embedding API."""
    settings = get_settings()
    payload = json.dumps({
        "model": settings.ollama_embedding_model,
        "input": texts,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{settings.ollama_base_url}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("embeddings", [])


def _get_dimensions() -> int:
    return 1536 if _is_openai_mode() else 4096


def embed_text(text: str) -> list[float]:
    """Embed a single text string."""
    if not text or not text.strip():
        return [0.0] * _get_dimensions()
    try:
        truncated = truncate_by_tokens(text)
        results = embed_texts([truncated])
        return results[0] if results else [0.0] * _get_dimensions()
    except Exception:
        return [0.0] * _get_dimensions()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts using the configured provider.

    Each text is truncated to ``EMBEDDING_CHUNK_MAX_TOKENS`` tokens, and the
    batch is split into sub-batches of 5 to stay within the model's total
    input-token budget.
    """
    if not texts:
        return []
    max_tokens = get_settings().embedding_chunk_max_tokens
    cleaned = [truncate_by_tokens(t, max_tokens) if t and t.strip() else " " for t in texts]

    batch_size = 5  # small batches to avoid total-token overflow
    all_embeddings: list[list[float]] = []
    try:
        for offset in range(0, len(cleaned), batch_size):
            batch = cleaned[offset: offset + batch_size]
            if _is_openai_mode():
                all_embeddings.extend(_openai_embed(batch))
            else:
                all_embeddings.extend(_ollama_embed(batch))
        return all_embeddings
    except Exception as exc:
        logger.warning("Embedding failed: %s", exc)
        dims = _get_dimensions()
        return [[0.0] * dims] * len(texts)


def generate_hypothetical_answer(question: str) -> str:
    """Generate a hypothetical answer for HyDE using the configured LLM."""
    settings = get_settings()

    if _is_openai_mode():
        base_url = "https://api.openai.com/v1"
        model = settings.minor_model.replace("openai:", "")
    else:
        base_url = settings.openai_base_url or "http://localhost:11434/v1"
        model = settings.minor_model.replace("openai:", "")

    payload = json.dumps({
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "당신은 문서의 조항을 인용하여 답변하는 전문가입니다. "
                    "질문에 대해 관련 조항의 제목과 핵심 내용을 포함하는 짧은 답변(3-5문장)을 작성하세요. "
                    "실제 조항 번호나 내용을 모르면 합리적으로 추정하세요."
                ),
            },
            {"role": "user", "content": question},
        ],
        "max_tokens": 200,
        "temperature": 0.0,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.openai_api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return question


def hyde_embed(question: str) -> list[float]:
    """HyDE: Generate hypothetical answer, then embed it."""
    hypo_answer = generate_hypothetical_answer(question)
    combined = f"{question} {hypo_answer}"
    return embed_text(combined)


def node_text_for_embedding(node: dict[str, Any]) -> str:
    """Build the text representation of a node for embedding."""
    props = node.get("properties", {})
    parts = []
    for key in ("name", "title"):
        val = props.get(key, "")
        if val:
            parts.append(str(val))
    content = props.get("content", "")
    if content:
        parts.append(str(content)[:1500])
    text = " ".join(parts) if parts else ""
    return truncate_by_tokens(text)
