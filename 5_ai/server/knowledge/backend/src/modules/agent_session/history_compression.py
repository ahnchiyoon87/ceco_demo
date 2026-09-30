"""Middleware to compress conversation history before each model call.

Prevents token overflow (e.g. 57K > 32K context limit) by:
1. Truncating large tool results in older messages
2. Dropping oldest message pairs when total exceeds budget
"""

from __future__ import annotations

import logging

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

logger = logging.getLogger(__name__)

# Korean text: ~2.5 chars per token (conservative)
_CHARS_PER_TOKEN = 2.5
# Max tokens for conversation history (leave room for system prompt + tools + response)
_MAX_HISTORY_TOKENS = 12_000
# Max chars kept per tool result in older messages
_TOOL_RESULT_MAX_CHARS = 2000
_TOOL_RESULT_SUFFIX = "\n... [결과가 잘렸습니다]"
# Keep recent messages untouched (don't truncate last N messages)
_KEEP_RECENT = 4


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def _msg_content(msg) -> str:
    c = msg.content
    if isinstance(c, str):
        return c
    return str(c)


def _total_tokens(msgs: list) -> int:
    return sum(_estimate_tokens(_msg_content(m)) for m in msgs)


def compress_messages(
    messages: list,
    max_tokens: int = _MAX_HISTORY_TOKENS,
    tool_max_chars: int = _TOOL_RESULT_MAX_CHARS,
    keep_recent: int = _KEEP_RECENT,
) -> list:
    """Compress a message list to fit within token budget.

    Strategy:
    1. Truncate large tool results in older messages (keep recent ones intact).
    2. Drop oldest messages from front if still over budget.
    3. Never drop the very last HumanMessage.
    """
    if not messages or _total_tokens(messages) <= max_tokens:
        return messages

    # Step 1: Truncate tool results in older messages
    boundary = max(0, len(messages) - keep_recent)
    compressed = []
    for i, msg in enumerate(messages):
        if i < boundary and isinstance(msg, ToolMessage):
            content = _msg_content(msg)
            if len(content) > tool_max_chars:
                truncated = content[:tool_max_chars] + _TOOL_RESULT_SUFFIX
                compressed.append(ToolMessage(
                    content=truncated,
                    tool_call_id=msg.tool_call_id,
                    name=getattr(msg, "name", None) or "",
                ))
                continue
        compressed.append(msg)

    # Step 2: Drop oldest messages if still over budget
    while len(compressed) > 1 and _total_tokens(compressed) > max_tokens:
        # Remove the oldest message, but keep at least the last message
        removed = compressed.pop(0)
        # If we removed an AIMessage with tool_calls, also remove orphaned ToolMessages
        if isinstance(removed, AIMessage) and removed.tool_calls:
            tc_ids = {tc["id"] for tc in removed.tool_calls if "id" in tc}
            compressed = [
                m for m in compressed
                if not (isinstance(m, ToolMessage) and m.tool_call_id in tc_ids)
            ]

    original_count = len(messages)
    final_count = len(compressed)
    if final_count < original_count:
        logger.info(
            "History compressed: %d → %d messages, ~%d tokens",
            original_count, final_count, _total_tokens(compressed),
        )

    return compressed


class HistoryCompressionMiddleware(AgentMiddleware):
    """Compress conversation history before each LLM call to prevent context overflow."""

    def __init__(self, max_tokens: int = _MAX_HISTORY_TOKENS):
        self.max_tokens = max_tokens

    def wrap_model_call(self, request, handler):
        """Compress messages in the request, then forward to the model."""
        messages = request.messages
        if messages and _total_tokens(messages) > self.max_tokens:
            compressed = compress_messages(messages, max_tokens=self.max_tokens)
            request = request.override(messages=compressed)
        return handler(request)
