// 정비팀 결과 → 요청 응답(field 단계). 통신 실패는 결과 미확인으로 올린다(다시 보내지 않는다).
const reg = global.get('registry');
const c = msg._crew || {};
let r = {};
try { r = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : (msg.payload || {}); } catch (e) { r = {}; }
const ok = msg.statusCode === 200 && r.status;
const payload = ok
    ? { job_order_id: c.job_order_id, stage: 'field', status: r.status, reason: r.reason || r.finding || '', finding: r.finding,
        effective: r.effective, task: r.task || c.task, plant_duration_s: r.plant_duration_s, wall_s: r.wall_s,
        maintenance_released: !!r.maintenance_released, ts: new Date().toISOString() }
    : { job_order_id: c.job_order_id, stage: 'field', status: 'UNKNOWN', reason: `정비팀 응답 없음(${msg.statusCode || msg.error || '연결 실패'})`,
        task: c.task, ts: new Date().toISOString() };
return { topic: `${reg.request.response_prefix}/${c.job_order_id}`, qos: 1, retain: false, payload: JSON.stringify(payload) };
