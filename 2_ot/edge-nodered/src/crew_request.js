// 수용된 현장 정비 작업 → 가상 정비팀(가상설비 정비팀 접점, OT 안). 정비팀 계정은 이 수신기만 갖는다.
// 정비팀은 현장 안전 확인 → 격리(LOTO) → 작업 → 소견을 돌려준다(작업 시간 = 설비 시간 ÷ 배속).
const c = msg._crew;
const auth = Buffer.from(`${env.get('FIELD_CREW_USER')}:${env.get('FIELD_CREW_PASSWORD')}`).toString('base64');
return { url: `http://${env.get('PLANT_HOST') || 'plant-sim'}:8082/tasks`, method: 'POST', requestTimeout: 60000,
    headers: { 'Content-Type': 'application/json', Authorization: `Basic ${auth}` },
    payload: JSON.stringify({ job_order_id: c.job_order_id, task: c.task, release_maintenance: !!c.release_maintenance }),
    _crew: c };
