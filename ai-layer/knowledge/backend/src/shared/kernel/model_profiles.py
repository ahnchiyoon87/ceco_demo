"""Helpers for provider-prefixed LLM and embedding model settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ModelPurpose = Literal["major", "minor", "ocr", "ocr_embedding"]


@dataclass(frozen=True)
class ModelProfile:
    """Normalized model configuration used across backend modules."""

    purpose: ModelPurpose
    raw_name: str
    provider: str
    model_name: str
    reasoning_effort: str
    base_url: str
    api_key: str

    @property
    def is_openai(self) -> bool:
        return self.provider == "openai"

    @property
    def uses_custom_base_url(self) -> bool:
        return self.is_openai and bool(self.base_url)


def _split_provider(raw_name: str, default_provider: str = "openai") -> tuple[str, str]:
    """Split a provider-prefixed model string into provider and model name."""

    normalized = (raw_name or "").strip()
    if not normalized:
        raise ValueError("model name is required")
    if ":" in normalized:
        provider, model_name = normalized.split(":", maxsplit=1)
        return provider.strip().lower(), model_name.strip()
    return default_provider, normalized


def resolve_model_profile(
    *,
    purpose: ModelPurpose,
    model_name: str,
    reasoning_effort: str = "",
    openai_base_url: str = "",
    openai_api_key: str = "",
    default_provider: str = "openai",
) -> ModelProfile:
    """Resolve a model setting into a provider-aware profile."""

    provider, normalized_model = _split_provider(model_name, default_provider=default_provider)
    base_url = openai_base_url.strip() if provider == "openai" else ""
    api_key = openai_api_key.strip() if provider == "openai" else ""
    return ModelProfile(
        purpose=purpose,
        raw_name=(model_name or "").strip(),
        provider=provider,
        model_name=normalized_model,
        reasoning_effort=(reasoning_effort or "").strip(),
        base_url=base_url,
        api_key=api_key,
    )


def should_use_openai_responses_api(profile: ModelProfile) -> bool:
    """Use the OpenAI Responses API for official GPT-5 chat models."""

    return profile.is_openai and not profile.base_url and profile.model_name.startswith("gpt-5")
