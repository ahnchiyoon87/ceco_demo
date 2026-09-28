import pytest
from fastapi import HTTPException
from backend.src.modules.operations import simulation


@pytest.mark.parametrize('patch', [
    {'interlock': True}, {'active_faults': {'heater_stuck': {}}},
    {'cooler_enable': None}, {'cooler_enable': True}, {'cooler_enable': 0},
])
def test_invalid_thermal_start_never_injects(monkeypatch, patch):
    monkeypatch.setenv('SIMULATOR_ACTIONS_ENABLED', 'true')
    state = dict(interlock=False, active_faults={}, cooler_enable=False)
    monkeypatch.setattr(simulation, 'status', lambda: state | patch)
    monkeypatch.setattr(simulation, 'simulator', lambda *args: pytest.fail('must not inject'))
    with pytest.raises(HTTPException) as error:
        simulation.inject_thermal()
    assert error.value.status_code == 409


def test_thermal_disabled_never_contacts_plant(monkeypatch):
    monkeypatch.delenv('SIMULATOR_ACTIONS_ENABLED', raising=False)
    monkeypatch.setattr(simulation, 'status', lambda: pytest.fail('must not query'))
    with pytest.raises(HTTPException) as error:
        simulation.inject_thermal()
    assert error.value.status_code == 403


def test_thermal_injects_one_fixed_fault_and_never_changes_commands(monkeypatch):
    monkeypatch.setenv('SIMULATOR_ACTIONS_ENABLED', 'true')
    monkeypatch.setattr(simulation, 'status', lambda: dict(interlock=False, active_faults={}, cooler_enable=False))
    writes = []
    monkeypatch.setattr(simulation, 'simulator', lambda *args: writes.append(args))
    simulation.inject_thermal()
    assert writes == [('/fault', {'scenario': 'heater_stuck', 'duration_s': 1200})]


def test_status_returns_runtime_capability_and_identity(monkeypatch):
    monkeypatch.setenv('SIMULATOR_ACTIONS_ENABLED', 'true')
    monkeypatch.setattr(simulation, 'simulator', lambda path: dict(
        site='AR-100', device='reactor-line-01', seq=42, interlock=False,
        commands={'agitator_run': False, 'cooler_enable': False}))
    data = simulation.status()
    assert data['cooler_enable'] is False and data['site'] == 'AR-100' and data['seq'] == 42
