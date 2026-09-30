import pytest
from pydantic import TypeAdapter, ValidationError

from backend.src.modules.operations.agent import NeedsEvidence, grounded_response_schema
from backend.src.modules.operations.actions import Proposal


def schema(*ids):
    return TypeAdapter(grounded_response_schema({'graph': {'documents': [
        {'document_id': value} for value in ids]}}))


def proposal(citations):
    return dict(expected_revision=1, summary='Inspect the evidence before deciding.',
                action='inspect_only', citations=citations, uncertainties=['Cause unknown'])


def test_only_exact_retrieved_ids_are_valid_and_exposed():
    adapter = schema('AR100-MIXER-RESPONSE', 'AR100-EVIDENCE-POLICY')
    parsed = adapter.validate_python(proposal(['AR100-MIXER-RESPONSE']))
    assert isinstance(parsed, Proposal)
    item = adapter.json_schema()['$defs']['GroundedProposal']['properties']['citations']['items']
    assert item['enum'] == ['AR100-EVIDENCE-POLICY', 'AR100-MIXER-RESPONSE']
    for invalid in ['AR100-MIXER-RESPONSE v1, section 1', 'current_window 12:00', 'FAKE-APPROVAL-999']:
        with pytest.raises(ValidationError):
            adapter.validate_python(proposal([invalid]))


def test_missing_documents_only_allows_evidence_request_with_no_citations():
    adapter = schema()
    outcome = dict(summary='Applicable documents are missing.', missing=['Procedure'],
                   next_steps=['Register an applicable procedure.'], citations=[])
    assert isinstance(adapter.validate_python(outcome), NeedsEvidence)
    with pytest.raises(ValidationError):
        adapter.validate_python({**outcome, 'citations': ['invented']})
    with pytest.raises(ValidationError):
        adapter.validate_python(proposal(['AR100-MIXER-RESPONSE']))


def test_action_remains_required_even_when_named_in_summary():
    adapter = schema('AR100-MIXER-RESPONSE')
    body = proposal(['AR100-MIXER-RESPONSE'])
    body['summary'] = 'The proposed action is inspect_only; review this request.'
    del body['action']
    with pytest.raises(ValidationError):
        adapter.validate_python(body)
    assert 'action' in adapter.json_schema()['$defs']['GroundedProposal']['required']
