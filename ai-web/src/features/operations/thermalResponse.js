// Observation only: reaching a training target is not fault clearance or repair.
export const THERMAL_BAND=1
export const THERMAL_HOLD_MS=30000
export const THERMAL_MAX_GAP_MS=6000
export function startThermal(state,now){
  const temperature=state?.readings?.['TT-101'],target=state?.commands?.temp_sp_c
  if(!Number.isFinite(temperature)||!Number.isFinite(target)||!Number.isFinite(state?.seq))return null
  return {site:state.site,device:state.device,target,started:now,initial:temperature,lastSeq:state.seq,lastAt:now,withinSince:Math.abs(temperature-target)<=THERMAL_BAND?now:null,samples:[{at:now,value:temperature}],interrupted:null}
}
export function observeThermal(track,state,now){
  if(!track||track.interrupted)return track
  if(state?.site!==track.site||state?.device!==track.device||state?.seq<track.lastSeq)return {...track,interrupted:'설비 식별 또는 스캔 번호 변경 · 관측 종료'}
  if(state?.commands?.temp_sp_c!==track.target)return {...track,interrupted:'목표 온도 변경 · 이전 목표 관측 종료'}
  if(state?.seq===track.lastSeq)return track
  const value=state?.readings?.['TT-101']
  if(!Number.isFinite(value))return {...track,withinSince:null}
  const inBand=Math.abs(value-track.target)<=THERMAL_BAND
  return {...track,lastSeq:state.seq,lastAt:now,withinSince:inBand?(now-track.lastAt>THERMAL_MAX_GAP_MS?now:track.withinSince??now):null,samples:[...track.samples,{at:now,value}].slice(-180)}
}
export function thermalStatus(track,now,stale=false){
  if(!track)return {kind:'idle',label:'온도 관측을 시작하세요'}
  if(track.interrupted)return {kind:'interrupted',label:track.interrupted}
  if(stale||now-track.lastAt>THERMAL_MAX_GAP_MS)return {kind:'unknown',label:'새 관측 없음 · 유지 여부 확인 불가'}
  const held=track.withinSince===null?0:track.lastAt-track.withinSince
  if(held>=THERMAL_HOLD_MS)return {kind:'held',label:'목표 ±1°C 범위 30초 관측 확인',held}
  if(now-track.started>=300000)return {kind:'timeout',label:'5분 내 유지 확인 못함 · 추가 확인 필요',held}
  if(track.withinSince!==null)return {kind:'holding',label:'목표 범위 진입 · 유지 관측 중',held}
  const latest=track.samples.at(-1).value
  const improved=Math.abs(track.initial-track.target)-Math.abs(latest-track.target)
  return {kind:'observing',label:improved>.2?'목표에 가까워지는 중 · 아직 도달 아님':improved<-.2?'목표에서 멀어짐 · 운전 조건 확인':'온도 변화 관측 중 · 아직 도달 아님',held}
}
