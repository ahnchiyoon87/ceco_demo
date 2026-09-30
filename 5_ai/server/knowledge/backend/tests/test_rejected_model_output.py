from langchain_core.messages import AIMessage
from langchain.agents.structured_output import StructuredOutputValidationError
from backend.src.shared.structured_failure import rejected_model_output


def test_rejected_arguments_are_preserved_without_transport_metadata():
    message = AIMessage(content='Rejected response', tool_calls=[
        {'name': 'GroundedProposal', 'args': {'citations': ['wrong document ID']}, 'id': 'test'}],
        response_metadata={'internal_header': 'must-not-be-recorded'})
    error = StructuredOutputValidationError('GroundedProposal', ValueError('invalid citation'), message)
    result = rejected_model_output(error)
    assert result['accepted'] is False
    assert result['message']['tool_calls'][0]['args']['citations'] == ['wrong document ID']
    assert 'must-not-be-recorded' not in str(result)
    assert rejected_model_output(ConnectionError('private connection details')) is None
