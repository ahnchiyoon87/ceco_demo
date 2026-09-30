"""Source grounding and draft persistence. No real model quality claim."""
import asyncio
import hashlib
from uuid import uuid4

import pytest

from backend.src.modules.ontology import build
from backend.src.modules.operations.api import connection
from psycopg.types.json import Jsonb


def inputs():
    text="M-101 agitator measures vibration using VT-101 sensor."
    base={"nodes":[{"id":"sensor1","class":"Sensor","properties":{"name":"VT-101"}}],"relationships":[]}
    sources={"asset.txt":{"text":text,"sha256":hashlib.sha256(text.encode()).hexdigest()}}
    evidence={"filename":"asset.txt","excerpt":text}
    plan=build.MeaningPlan(summary="A source-grounded mixer and sensor relation candidate.",
        additional_nodes=[{"node":{"id":"mixer1","class":"Asset","properties":{"name":"M-101"}},"evidence":evidence,"reason":"The source explicitly names the mixer."}],
        additional_relationships=[{"relationship":{"from_id":"mixer1","to_id":"sensor1","type":"HAS_SENSOR"},"evidence":evidence,"reason":"The source explicitly links its vibration sensor."}],
        unresolved=["Test source; not an approved industrial procedure."])
    return base,sources,plan


@pytest.mark.parametrize('mode', ['valid', 'repaired', 'still_invalid'])
def test_exact_quote_repair_is_bounded_and_never_accepts_paraphrases(mode):
    _, sources, valid = inputs()
    invalid = valid.model_copy(deep=True)
    invalid.additional_nodes[0].evidence.excerpt = 'M-101 has a vibration sensor, according to this source.'
    calls, records = [], []
    class Agent:
        async def ainvoke(self, payload, config):
            calls.append(payload)
            plan = valid if mode == 'valid' or (mode == 'repaired' and len(calls) == 2) else invalid
            return {'structured_response': plan, 'messages': [{'role':'assistant','content':'candidate'}]}
    task = build.invoke_grounded(Agent(), [{'role':'user','content':'build'}], sources, records.append)
    if mode == 'still_invalid':
        with pytest.raises(ValueError, match='원본과 일치'):
            asyncio.run(task)
    else:
        result = asyncio.run(task)
        assert result['structured_response'] == valid
    assert len(calls) == (1 if mode == 'valid' else 2)
    if mode != 'valid':
        invalid = [r for r in records if r['stage'] == 'source_quote_validation']
        assert invalid[0]['invalid_paths'] == ['additional_nodes[0].evidence']
        assert 'unresolved' in calls[1]['messages'][-1]['content']
    if mode == 'still_invalid':
        assert records[-1]['repair_requested'] is False
    else:
        assert records[-1]['stage'] == 'source_quotes_verified'
    assert records[0] == {'stage':'model_requested','attempt':1,'status':'started'}


def test_candidate_preserves_source_evidence_on_nodes_and_relationships():
    base,sources,plan=inputs()
    result=build.merge_meaning(base,sources,plan)
    assert result["batch"]["status"]=="candidate"
    node=result["batch"]["nodes"][-1]
    rel=result["batch"]["relationships"][-1]
    for item in (node,rel):
        assert item["properties"]["source_sha256"]==sources["asset.txt"]["sha256"]
        assert item["properties"]["source_excerpt"]==sources["asset.txt"]["text"]
        assert item["properties"]["mapping_method"]=="model-proposed-awaiting-review"


@pytest.mark.parametrize("section,key", [("additional_nodes", "node"), ("additional_relationships", "relationship")])
def test_model_schema_exposes_the_same_scalar_property_contract_as_import(section, key):
    import jsonschema
    _, _, plan = inputs()
    payload = plan.model_dump(by_alias=True)
    properties = payload[section][0][key].setdefault("properties", {})
    properties.update({"name": "example", "version": 3, "value": 1.5, "enabled": True, "optional": None})
    schema = build.MeaningPlan.model_json_schema()
    jsonschema.validate(payload, schema)
    build.MeaningPlan.model_validate(payload)
    for unsupported in (["IT-102", "VT-101"], {"tag": "IT-102"}):
        properties["targets"] = unsupported
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, schema)
        with pytest.raises(ValueError):
            build.MeaningPlan.model_validate(payload)


@pytest.mark.parametrize("defect", ["invented_excerpt","unselected_source","duplicate_node","missing_endpoint"])
def test_invalid_meaning_candidate_is_not_accepted(defect):
    base,sources,plan=inputs()
    if defect=="invented_excerpt":plan.additional_nodes[0].evidence.excerpt="A claim that is absent from the source."
    elif defect=="unselected_source":plan.additional_nodes[0].evidence.filename="unselected.txt"
    elif defect=="duplicate_node":plan.additional_nodes[0].node.id="sensor1"
    else:plan.additional_relationships[0].relationship.to_id="missing"
    with pytest.raises(ValueError):build.merge_meaning(base,sources,plan)


@pytest.mark.parametrize('failure', ['timeout', 'missing_endpoint', 'invented_excerpt', 'unknown_value_error'])
def test_failed_build_keeps_trace_and_never_claims_a_candidate(monkeypatch, failure):
    build.initialize()
    base,sources,_=inputs()
    with connection() as conn:
        run=conn.execute("INSERT INTO manufacturing_knowledge_builds(id,status,model,question,sources,base_batch) VALUES (%s,'running','test-substitute','integration probe',%s,%s) RETURNING *",(uuid4(),Jsonb(sources),Jsonb(base))).fetchone()
    async def fail(run,trace):
        trace.append({"tool":"read_registered_source","filename":"asset.txt"})
        if failure == 'invented_excerpt':
            invalid_base, invalid_sources, plan = inputs()
            plan.additional_nodes[0].evidence.excerpt = 'secret-rejected-input'
            return build.merge_meaning(invalid_base, invalid_sources, plan), trace
        if failure == 'unknown_value_error':
            raise ValueError('secret-provider-detail')
        if failure == 'missing_endpoint':
            invalid_base, invalid_sources, plan = inputs()
            plan.additional_relationships[0].relationship.to_id = 'secret-rejected-input'
            return build.merge_meaning(invalid_base, invalid_sources, plan), trace
        raise TimeoutError("Simulated provider failure")
    monkeypatch.setattr(build,"generate",fail)
    try:
        asyncio.run(build.drive(run))
        result=build.get_build(run["id"])
        assert result["status"]=="failed" and result["result"] is None
        assert result["trace"][0]["filename"]=="asset.txt"
        if failure == 'missing_endpoint':
            assert '관계가 참조한 노드' in result['error']
            assert result['trace'][-1]['validation_issues'] == [{'loc': [], 'type': 'value_error'}]
            assert 'secret-rejected-input' not in str(result['trace']) + result['error']
        if failure == 'invented_excerpt':
            assert '관계 근거 인용이 선택한 원본과 일치하지 않습니다' in result['error']
            assert 'validation_failure' in result['trace'][-1]
            assert 'secret-rejected-input' not in str(result['trace']) + result['error']
        if failure == 'unknown_value_error':
            assert 'ValueError' in result['error']
            assert 'secret-provider-detail' not in str(result['trace']) + result['error']
    finally:
        with connection() as conn:conn.execute("DELETE FROM manufacturing_knowledge_builds WHERE id=%s",(run["id"],))


def test_tool_receipts_are_visible_before_model_finishes(monkeypatch):
    build.initialize()
    base, sources, plan = inputs()
    with connection() as conn:
        run = conn.execute("INSERT INTO manufacturing_knowledge_builds(id,status,model,question,sources,base_batch) VALUES (%s,'running','test-substitute','live trace probe',%s,%s) RETURNING *",
                           (uuid4(), Jsonb(sources), Jsonb(base))).fetchone()

    class Agent:
        def __init__(self, tools):
            self.tools = {tool.name:tool for tool in tools}

        async def ainvoke(self, *args):
            await asyncio.gather(
                asyncio.to_thread(self.tools['read_registered_source'].invoke, {'filename':'asset.txt'}),
                asyncio.to_thread(self.tools['read_extracted_structure'].invoke, {}))
            snapshot = build.get_build(run['id'])
            assert snapshot['status'] == 'running'
            tools = [item for item in snapshot['trace'] if item.get('tool')]
            assert {item['tool'] for item in tools} == {'read_registered_source','read_extracted_structure'}
            assert all(item['at'] and item['status'] == 'returned' for item in tools)
            assert snapshot['trace'][0]['stage'] == 'model_requested'
            assert not any(item.get('stage') == 'model_returned' for item in snapshot['trace'])
            return {'messages':[], 'structured_response':plan}

    monkeypatch.setattr(build, '_init_model', lambda *a, **kw: object())
    monkeypatch.setattr(build, 'create_agent', lambda **kw: Agent(kw['tools']))
    asyncio.run(build.drive(run))
    assert build.get_build(run['id'])['status'] == 'candidate'
    stages = [item['stage'] for item in build.get_build(run['id'])['trace'] if item.get('stage')]
    assert stages == ['model_requested','model_returned','source_quotes_verified','candidate_validation','candidate_validated']


@pytest.mark.parametrize('mode', ['fixed', 'still_invalid', 'duplicate'])
def test_structure_repair_has_exact_ids_and_one_shared_retry(mode):
    base, sources, valid = inputs()
    invalid = valid.model_copy(deep=True)
    if mode == 'duplicate':
        invalid.additional_relationships.append(invalid.additional_relationships[0].model_copy(deep=True))
    else:
        invalid.additional_relationships[0].relationship.to_id = 'invented-sensor-id'
    calls, records = [], []
    class Agent:
        async def ainvoke(self, payload, config):
            calls.append(payload)
            plan = invalid if len(calls) == 1 or mode == 'still_invalid' else valid
            return {'structured_response': plan, 'messages': []}
    task = build.invoke_grounded(Agent(), [], sources, records.append, base)
    if mode == 'still_invalid':
        with pytest.raises(ValueError, match='연결이 유효하지'):
            asyncio.run(task)
    else:
        result = asyncio.run(task)
        assert result['structured_response'] == valid
    assert len(calls) == 2
    assert 'sensor1' in calls[1]['messages'][-1]['content']
    repairs = [r for r in records if r['stage'] == 'candidate_structure_validation']
    assert repairs[0]['repair_requested'] is True
    if mode == 'still_invalid':
        assert repairs[-1]['repair_requested'] is False
    assert base['nodes'][0]['id'] == 'sensor1'
    assert len(base['nodes']) == 1  # No invented replacement node was added.


def test_quote_repair_does_not_grant_another_structure_retry():
    base, sources, valid = inputs()
    quote_bad = valid.model_copy(deep=True)
    quote_bad.additional_nodes[0].evidence.excerpt = 'This quotation does not occur in the selected source.'
    ids_bad = valid.model_copy(deep=True)
    ids_bad.additional_relationships[0].relationship.to_id = 'not-present'
    calls = []
    class Agent:
        async def ainvoke(self, payload, config):
            calls.append(payload)
            return {'structured_response': quote_bad if len(calls) == 1 else ids_bad, 'messages': []}
    with pytest.raises(ValueError, match='연결이 유효하지'):
        asyncio.run(build.invoke_grounded(Agent(), [], sources, lambda _: None, base))
    assert len(calls) == 2
