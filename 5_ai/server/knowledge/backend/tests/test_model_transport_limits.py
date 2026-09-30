"""Inspect actual SDK clients: Pydantic model fields alone do not prove limits."""
from types import SimpleNamespace

import pytest

from backend.src.modules.agent_session import service


@pytest.mark.parametrize('mode', ['answer', 'build'])
def test_limits_reach_both_sdk_clients(monkeypatch, mode):
    profile = SimpleNamespace(is_openai=True, model_name='coding', api_key='verification-only',
                              reasoning_effort='none', base_url='http://127.0.0.1:9/v1')
    monkeypatch.setattr(service, '_resolve_agent_model_profile', lambda _: profile)
    monkeypatch.setattr(service, 'should_use_openai_responses_api', lambda _: False)
    model = service._init_model(mode, request_timeout=90, max_retries=0)
    assert model.root_client.timeout == 90
    assert model.root_async_client.timeout == 90
    assert model.root_client.max_retries == 0
    assert model.root_async_client.max_retries == 0
