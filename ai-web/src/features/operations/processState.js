// UI projection of persisted states, never a timer-driven simulation.
export function processState(run, proposal) {
  const nodes={received:'done',investigate:'waiting',review:'waiting',execute:'waiting',result:'waiting'}
  let outcome='분석 시작을 기다립니다.', branch='none'
  if(run?.status==='running'){nodes.investigate='active';outcome='AI가 실제 자료를 조회하고 있습니다.'}
  if(run && !['running','needs_evidence','failed','interrupted','awaiting_review','resuming','finished'].includes(run.status)){
    nodes.investigate='warning';outcome='알 수 없는 실행 상태입니다. 저장된 기록을 확인하세요.'
  }
  if(run && ['awaiting_review','resuming','finished'].includes(run.status) && !proposal){
    nodes.investigate='done';nodes.review='warning';outcome='실행 상태에 대응하는 제안·결과를 아직 확인하지 못했습니다.'
  }
  if(run?.status==='needs_evidence'){nodes.investigate='warning';branch='evidence';outcome='근거 보완 필요 · 승인할 제안이 없습니다.'}
  if(['failed','interrupted'].includes(run?.status)){nodes.investigate='warning';outcome='처리 실패·중단 · 저장된 기록을 확인하세요.'}
  if(proposal){nodes.investigate='done';nodes.review='active';outcome='사람의 검토를 기다립니다.'}
  if(proposal && run?.status==='resuming'){outcome='검토 결과를 반영하고 있습니다. 설비 실행 여부는 아직 확인 전입니다.'}
  if(proposal?.decision?.decision==='reject'||proposal?.status==='rejected'){
    nodes.review='done';nodes.result='done';branch='rejected';outcome='반려 · 이 제안의 설비 명령은 없습니다.'
  }else if(proposal?.status==='executing'){
    nodes.review='done';nodes.execute='active';outcome='승인 후 조건·조치 결과를 확인하고 있습니다.'
  }
  if(proposal?.result){
    nodes.review='done';nodes.execute='done';branch='approved'
    const status=proposal.result.status
    nodes.result=['stop_verified','inspection_requested'].includes(status)?'done':'warning'
    outcome=({stop_verified:'교반기 정지 확인 · 후속 점검 대기',inspection_requested:'점검 요청 기록 · 설비 명령 없음',not_executed:'조건 불충족 · 명령 미실행',uncertain:'조치 결과 불명확 · 상태 확인 필요'})[status]||'결과 기록을 확인하세요.'
    if(!['stop_verified','inspection_requested'].includes(status))nodes.execute='warning'
    if(status==='cooling_command_verified'){
      nodes.execute='done';nodes.result=proposal.status==='observing'?'active':'warning'
      outcome=proposal.status==='observing'?'냉각 명령 반영 · 서버에서 온도 유지 관측 중':'냉각 명령 반영 확인 · 온도 회복은 아직 미확인'
    }
    if(status==='temperature_stable'){
      nodes.execute='done';nodes.result='done'
      outcome='목표 온도 범위 30초 확인 · 원인 제거·정비 완료는 아님'
    }
    if(proposal.result.thermal_observation?.status==='unknown'){
      nodes.execute='done';nodes.result='warning';outcome='냉각 명령 반영 · 새 온도 관측 확인 필요'
    }
    if(proposal.result.thermal_observation && ['interrupted','timeout'].includes(status)){
      nodes.execute='done';nodes.result='warning';outcome=proposal.result.reason
    }
  }
  if(proposal && !proposal.result && ['failed','interrupted'].includes(run?.status)){
    nodes.review='warning'
    if(proposal.status==='executing')nodes.execute='warning'
    outcome='검토·실행 처리가 중단되었습니다. 저장된 상태를 확인하세요. 성공으로 확인되지 않았습니다.'
  }
  return {nodes,outcome,branch}
}
