import pytest
from fastapi import HTTPException
from backend.src.modules.operations.agent import refresh_proposal_observations


def test_refresh_retains_model_snapshot_without_replacing_its_history():
    original={'incident_id':'a','revision':1,'graph':{'status':'available'},
              'history':{'rows':['historical']},'current_history':{'rows':['before']}}
    fresh={**original,'current_history':{'rows':['after']}}
    result=refresh_proposal_observations(original,fresh)
    assert result['analysis_current_history']=={'rows':['before']}
    assert result['current_history']=={'rows':['after']}
    assert original['current_history']=={'rows':['before']}
    assert result['history']==original['history']


@pytest.mark.parametrize('change',[{'revision':2},{'graph':{'status':'available','documents':[{'content':'changed'}]}}])
def test_refresh_rejects_changed_reasoning_basis(change):
    original={'incident_id':'a','revision':1,'graph':{'status':'available'}}
    with pytest.raises(HTTPException) as caught:refresh_proposal_observations(original,{**original,**change})
    assert caught.value.status_code==409
