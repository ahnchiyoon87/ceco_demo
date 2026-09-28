export const trainingScenarios = [
  {id:'mixer',path:'/mixer-anomaly',title:'교반기 전류·진동 이상',duration:600,
    description:'교반기에 부하를 주는 가상 고장입니다. 전류·진동 알람을 조사하고, 승인 후 정지 여부를 확인합니다.'},
  {id:'thermal',path:'/thermal-anomaly',title:'반응기 온도 상승',duration:1200,
    description:'히터가 계속 열을 내는 가상 고장입니다. TT-101 온도 알람을 조사하고, 승인 후 냉각 명령과 실제 온도 변화를 따로 확인합니다.'},
]

export function injectionDisabledReason(state, scenario, pending=false) {
  if(pending)return '앞선 요청의 응답을 기다리고 있습니다.'
  if(!state)return '설비 상태를 확인한 뒤 시작할 수 있습니다.'
  if(state.interlock)return '고압 인터록이 남아 있습니다. 설비 상태를 확인하세요.'
  if(Object.keys(state.active_faults||{}).length)return '이미 적용 중인 이상이 있습니다. 해제 후 시작하세요.'
  if(scenario==='mixer'&&!state.agitator_run)return '위 설비 직접 조작에서 교반기를 기동한 뒤 시작하세요.'
  if(scenario==='thermal'&&state.cooler_enable!==false)return '냉각 기능이 지원되고 냉각 명령이 꺼져 있어야 합니다.'
  if(!trainingScenarios.some(item=>item.id===scenario))return '실습 종류를 다시 선택하세요.'
  return ''
}

// Time/site/tag association is not proof that an injected fault caused an alarm.
export function findTrainingIncident(incidents, track, now=Date.now()) {
  if(track.incidentId)return incidents.find(item=>item.id===track.incidentId)
  const scenario=trainingScenarios.find(item=>item.id===track.scenario)
  if(!scenario||!Number.isFinite(track.started)||track.started<=0||track.ended||now<track.started)return null
  const end=track.started+scenario.duration*1000+60000
  if(now>end)return null
  return incidents.find(item=>{
    const alarm=item.alarm||{},at=Number(item.last_ts)/1e6
    return alarm.site===track.site&&alarm.device===track.device&&at>=track.started&&at<=end&&
      (scenario.id==='mixer'?item.correlation_key?.includes('mixer'):alarm.tag==='TT-101')
  })||null
}
