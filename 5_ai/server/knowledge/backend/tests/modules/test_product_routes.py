"""HTTP product boundary; does not claim model inference or UI verification."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.src.host.app import create_app
from backend.src.modules.ontology import api


@pytest.fixture
def client():
    # No context manager: route tests intentionally do not start infrastructure.
    return TestClient(create_app())


@pytest.mark.parametrize('method,path', [
    ('POST', '/api/neo4j/clear-all'),
    ('POST', '/api/graph/entities'),
    ('PATCH', '/api/graph/entities/probe'),
    ('DELETE', '/api/graph/entities/probe'),
    ('POST', '/api/graph/relationships'),
    ('PUT', '/api/schema/classes'),
    ('DELETE', '/api/schema/classes/Asset'),
    ('PUT', '/api/schema/relationships'),
    ('DELETE', '/api/schemas/probe/entities'),
    ('POST', '/api/graph/nl-query'),
    ('GET', '/api/stream?prompt=build&mode=build'),
])
def test_upstream_mutation_routes_are_not_served(client, method, path):
    assert client.request(method, path).status_code == 404


def test_review_and_manufacturing_routes_remain_registered(client):
    paths = client.get('/openapi.json').json()['paths']
    for path in ('/api/knowledge/prepare', '/api/knowledge/build',
                 '/api/knowledge/preview', '/api/knowledge/publish',
                 '/api/operations/incidents/{incident_id}/analyze',
                 '/api/operations/analysis/{run_id}/decision', '/api/upload'):
        assert 'post' in paths[path]


def test_search_treats_class_as_data_and_returns_empty_success(client, monkeypatch):
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value
    session.run.return_value = []
    monkeypatch.setattr(api, 'get_driver', lambda: driver)
    malicious = 'Asset) DETACH DELETE n //'
    response = client.get('/api/graph/search', params={'q': 'mixer', 'class_name': malicious})
    assert response.status_code == 200
    assert response.json() == {'nodes': [], 'edges': []}
    query, params = session.run.call_args.args
    assert malicious not in query
    assert params['class'] == malicious


@pytest.mark.parametrize('path', ['/api/graph', '/api/graph/search?q=mixer', '/api/graph/neighbors?node_id=probe'])
def test_graph_failure_is_not_an_empty_success(client, monkeypatch, path):
    def fail():
        raise OSError('private connection detail')
    monkeypatch.setattr(api, 'get_driver', fail)
    response = client.get(path)
    assert response.status_code == 503
    assert 'private connection detail' not in response.text


@pytest.mark.parametrize('limit', [-1, 0, 501])
def test_graph_limits_are_bounded(client, limit):
    assert client.get('/api/graph', params={'limit': limit}).status_code == 422


@pytest.mark.parametrize('depth', [-1, 0, 4, '1 RETURN n'])
def test_neighbor_depth_is_bounded(client, depth):
    assert client.get('/api/graph/neighbors', params={'node_id': 'probe', 'depth': depth}).status_code == 422


def test_neighbor_failure_never_retries_with_a_smaller_scope(client, monkeypatch):
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value
    session.run.side_effect = OSError('connection lost')
    monkeypatch.setattr(api, 'get_driver', lambda: driver)
    response = client.get('/api/graph/neighbors', params={'node_id': 'probe', 'depth': 3})
    assert response.status_code == 503
    assert session.run.call_count == 1
