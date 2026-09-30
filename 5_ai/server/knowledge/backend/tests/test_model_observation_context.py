from datetime import datetime, timedelta, timezone
from backend.src.modules.operations.agent import observation_summary, model_plant_context


def test_tool_fetches_new_window_after_model_delay_and_preserves_actual_timestamps(monkeypatch):
    from backend.src.modules.operations import agent
    calls = []
    old = {'status': 'available', 'rows': []}
    measured = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
    fresh = {'status': 'available', 'rows': [{'time': measured, 'tag': 'IT-102', 'value': 10.4, 'quality': 'GOOD'}]}
    monkeypatch.setattr(agent.time, 'time_ns', lambda: 90_000_000_000)
    monkeypatch.setattr(agent, 'history', lambda *args: calls.append(args) or fresh)
    monkeypatch.setattr(agent, 'live_state', lambda: {'status': 'available', 'commands': {'agitator_run': True}})
    evidence = {'graph': {'sensors': [{'tag': 'IT-102'}]}, 'history': old,
                'current_history': old, 'window_capped': False}
    result = agent.refresh_analysis_observations(evidence, {'site': 'AR-100', 'device': 'reactor-line-01'})
    assert calls == [('AR-100', 'reactor-line-01', ['IT-102'], 60_000_000_000, 90_000_000_000)]
    assert result['current_window']['statistics'][0]['last']['time'] == measured
    assert 2 <= result['current_window']['statistics'][0]['latest_age_seconds'] < 4
    assert evidence['history'] is old
    assert evidence['current_history'] is fresh


def test_tool_query_failure_does_not_reuse_startup_current_values(monkeypatch):
    from backend.src.modules.operations import agent
    unavailable = {'status': 'unavailable', 'rows': [], 'error': 'history unavailable'}
    monkeypatch.setattr(agent, 'history', lambda *args: unavailable)
    monkeypatch.setattr(agent, 'live_state', lambda: {'status': 'unavailable'})
    evidence = {'graph': {'sensors': []}, 'history': {'rows': []},
                'current_history': {'rows': ['previous high readings']}, 'window_capped': False}
    result = agent.refresh_analysis_observations(evidence, {'site': 'AR-100', 'device': 'reactor-line-01'})
    assert result['current_window']['status'] == 'unavailable'
    assert result['current_window']['statistics'] == []
    assert evidence['current_history'] is unavailable


def test_good_but_old_measurement_age_is_explicit():
    measured = (datetime.now(timezone.utc) - timedelta(seconds=21)).isoformat()
    summary = observation_summary({'status': 'available', 'rows': [
        {'time': measured, 'tag': 'IT-102', 'value': 10.4, 'quality': 'GOOD'}]})
    assert 21 <= summary['statistics'][0]['latest_age_seconds'] < 23
    assert summary['statistics'][0]['quality_counts'] == {'GOOD': 1}
    assert summary['statistics'][0]['last']['time'] == measured


def test_model_cannot_substitute_untimed_snapshot_values_for_measurements():
    context = model_plant_context({'status': 'available', 'commands': {'agitator_run': True},
                                  'interlock': False, 'readings': {'IT-102': 6.3},
                                  'active_faults': ['synthetic'], 'retrieved_at': 'now'})
    assert context['commands']['agitator_run'] is True
    assert context['interlock'] is False
    assert 'readings' not in context and 'active_faults' not in context
