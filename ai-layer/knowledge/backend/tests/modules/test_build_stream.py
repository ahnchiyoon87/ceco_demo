"""Read-only stream lifecycle; no model, database or equipment calls."""
import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from backend.src.modules.ontology import build


class Request:
    async def is_disconnected(self):
        return False


def test_committed_updates_terminal_close_and_no_generation(monkeypatch):
    run_id = uuid4()
    rows = iter([
        {"id": run_id, "status": "running", "trace": []},
        {"id": run_id, "status": "running", "trace": [{"tool": "read_registered_source"}]},
        {"id": run_id, "status": "candidate", "trace": [{"tool": "read_registered_source"}]},
    ])
    monkeypatch.setattr(build, "get_build", lambda _: next(rows))
    async def sleep(_):
        pass
    monkeypatch.setattr(build.asyncio, "sleep", sleep)
    async def check():
        response = await build.stream_build(run_id, Request())
        frames = [frame async for frame in response.body_iterator]
        assert len(frames) == 3
        assert 'read_registered_source' not in frames[0]
        assert 'read_registered_source' in frames[1]
        assert '"status": "candidate"' in frames[2]
        assert response.headers['x-accel-buffering'] == 'no'
    asyncio.run(check())


def test_missing_run_is_http404_before_stream(monkeypatch):
    def missing(_):
        raise HTTPException(404, 'missing')
    monkeypatch.setattr(build, 'get_build', missing)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(build.stream_build(uuid4(), Request()))
    assert exc.value.status_code == 404


def test_storage_failure_reports_disconnect_not_success(monkeypatch):
    count = 0
    def read(_):
        nonlocal count
        count += 1
        if count > 1:
            raise RuntimeError('storage unavailable')
        return {'status': 'running', 'trace': []}
    monkeypatch.setattr(build, 'get_build', read)
    async def sleep(_):
        pass
    monkeypatch.setattr(build.asyncio, 'sleep', sleep)
    async def check():
        response = await build.stream_build(uuid4(), Request())
        frames = [frame async for frame in response.body_iterator]
        assert len(frames) == 2
        assert 'event: unavailable' in frames[1]
    asyncio.run(check())
