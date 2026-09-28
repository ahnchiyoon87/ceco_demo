from backend.src.modules.operations import evidence


def test_missing_tag_relations_retain_exact_lookup_scope(monkeypatch):
    alarm = {'site': 'AR-100', 'device': 'reactor-line-01', 'tag': 'UNKNOWN', 'ts': 123}
    monkeypatch.setattr(evidence, 'get_incident', lambda _: {
        'incident': {'alarm': alarm, 'review_revision': 1, 'revision': 1},
        'events': [{'kind': 'alarm_received', 'payload': alarm}]})
    calls = []
    monkeypatch.setattr(evidence, '_run_readonly_query', lambda q, p: calls.append(p) or [])
    monkeypatch.setattr(evidence, 'history', lambda *args: {'status': 'missing', 'rows': []})
    graph = evidence.incident_evidence('test')['graph']
    assert graph['status'] == 'available' and not graph['assets']
    assert calls[0] == {'site': 'AR-100', 'device': 'reactor-line-01', 'tags': ['UNKNOWN']}
    assert graph['lookup_scope']['alarm_tags'] == ['UNKNOWN']
    assert 'Empty results do not establish' in graph['lookup_scope']['limitation']
