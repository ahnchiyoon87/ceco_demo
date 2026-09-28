const actions = {
  stop_mixer: {title:'교반기 정지 후 점검',description:'승인 후 조건을 다시 확인하고 Modbus로 교반기 정지를 요청합니다.'},
  enable_cooling: {title:'냉각기 기동 후 온도 관측',description:'승인 후 현재 목표값을 유지한 채 Modbus로 냉각기를 켭니다. 명령 반영과 실제 온도 회복은 별도로 확인합니다.'},
  inspect_only: {title:'현장 점검 요청',description:'승인하면 점검 요청을 기록합니다. 설비 명령은 보내지 않습니다.'},
}
export const actionPresentation = action => actions[action] || {title:'알 수 없는 조치',description:'저장된 조치 코드를 확인해야 합니다.'}
