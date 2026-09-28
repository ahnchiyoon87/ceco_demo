"""Middleware to parse raw tool calls from gpt-oss models that output them as text."""

from __future__ import annotations

import json
import re
import uuid

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage


# Pattern: <|start|>..to=functions.TOOLNAME ..<|message|>{JSON}<|call|>
# The JSON may contain nested braces, so we match greedily up to }<|call|>
_RAW_TOOL_CALL_PATTERN = re.compile(
    r"<\|start\|>.*?to=functions\.(\w+).*?<\|message\|>\s*(\{.*\})\s*<\|call\|>",
    re.DOTALL,
)


def _fix_json(raw: str) -> str:
    """Attempt to fix common JSON errors from gpt-oss models.

    e.g. {"command":"...PY"]} -> {"command":"...PY"}
    """
    fixed = re.sub(r'"\]\s*\}$', '"}', raw.strip())
    fixed = re.sub(r'^\{\s*\[', '{', fixed)
    return fixed


def _extract_tool_calls_from_text(content: str) -> tuple[str, list[dict]]:
    """Extract raw tool calls from gpt-oss formatted text.

    Returns (cleaned_content, tool_calls_list).
    """
    tool_calls = []
    for match in _RAW_TOOL_CALL_PATTERN.finditer(content):
        tool_name = match.group(1)
        raw_json = match.group(2)
        args = None
        for attempt_json in [raw_json, _fix_json(raw_json)]:
            try:
                args = json.loads(attempt_json, strict=False)
                break
            except json.JSONDecodeError:
                continue
        if args is None:
            continue
        tool_calls.append({
            "name": tool_name,
            "args": args,
            "id": f"call_{uuid.uuid4().hex[:24]}",
            "type": "tool_call",
        })

    if tool_calls:
        cleaned = _RAW_TOOL_CALL_PATTERN.sub("", content).strip()
        return cleaned, tool_calls
    return content, []


class ToolCallParserMiddleware(AgentMiddleware):
    """Parse raw gpt-oss tool calls into proper tool_call objects."""

    def wrap_model_call(self, request, handler):
        """Intercept model response and fix raw tool calls."""

        response = handler(request)

        # Identify the AIMessage from the ModelResponse
        msg = None
        msg_index = -1
        if isinstance(response, AIMessage):
            msg = response
        elif hasattr(response, "result") and isinstance(response.result, list):
            for i, m in enumerate(response.result):
                if isinstance(m, AIMessage):
                    msg = m
                    msg_index = i
                    break

        if msg is None:
            return response

        # Already has proper tool calls
        if msg.tool_calls:
            return response

        content = msg.content
        if isinstance(content, list):
            content = " ".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        if not isinstance(content, str) or "<|start|>" not in content:
            return response

        cleaned, tool_calls = _extract_tool_calls_from_text(content)
        if not tool_calls:
            return response

        # Return a new AIMessage with proper tool_calls
        new_msg = AIMessage(
            content=cleaned,
            tool_calls=tool_calls,
        )

        # Replace the AIMessage in the ModelResponse
        if hasattr(response, "result") and msg_index >= 0:
            response.result[msg_index] = new_msg
            return response
        return new_msg
