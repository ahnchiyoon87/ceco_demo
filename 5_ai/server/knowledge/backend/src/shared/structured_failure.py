"""Retain rejected model content without serializing clients, requests or headers."""
from langchain.agents.structured_output import (
    MultipleStructuredOutputsError,
    StructuredOutputValidationError,
)


def rejected_model_output(exc):
    if not isinstance(exc, (StructuredOutputValidationError, MultipleStructuredOutputsError)):
        return None
    message = exc.ai_message
    return {
        'error_type': type(exc).__name__,
        'tool_names': getattr(exc, 'tool_names', [getattr(exc, 'tool_name', '')]),
        'message': {
            'type': 'ai', 'content': message.content,
            'tool_calls': message.tool_calls,
            'invalid_tool_calls': message.invalid_tool_calls,
        },
        'accepted': False,
    }
