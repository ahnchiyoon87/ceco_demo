// 운전원 결정(FUXA "받은 요청" 화면 → …/request/decision): 수락이면 새 만료(발행 + 30 s)와 운전원 수락 표시를 붙여
// 제어기 명령 토픽으로 낸다(Store 후 운전원 Start). 거부면 거부 응답. 10초 넘은 결정·없는 요청은 무시한다.
const reg = global.get('registry');
let d;
try { d = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload; } catch (e) { return null; }
if (msg.retain) return null;
const age = (Date.now() - Date.parse(d.ts)) / 1000;
if (!Number.isFinite(age) || age > 10 || age < -10) { node.warn('오래된 운전원 결정 무시'); return null; }
const pending = flow.get('pending') || {};
const job = pending[d.job_order_id];
if (!job) { node.warn(`대기 목록에 없는 요청: ${d.job_order_id}`); return null; }
delete pending[d.job_order_id];
flow.set('pending', pending);
const now = Date.now() / 1000;
const iso = new Date().toISOString();
const resp = (status, reason) => ({ topic: `${reg.request.response_prefix}/${job.job_order_id}`, qos: 1, retain: false,
    payload: JSON.stringify({ job_order_id: job.job_order_id, stage: 'operator', status, reason, ts: iso }) });
const items = Object.values(pending).sort((a, b) => a.received_at - b.received_at);
const h = items[0];
const pendingMsg = { topic: reg.request.pending_topic, qos: 1, retain: true, payload: JSON.stringify({
    count: items.length, head_job: h ? h.job_order_id : '', head_wm: h ? h.work_master_id : '',
    head_desc: h ? h.desc : '대기 중인 요청 없음', head_context: h ? (h.context_summary || '') : '',
    head_wait_s: h ? Math.round(now - h.received_at) : 0,
    items: items.map(i => ({ job_order_id: i.job_order_id, work_master_id: i.work_master_id, desc: i.desc })) }) };
if (String(d.decision).toLowerCase() !== 'accept') return { batch: [resp('OPERATOR_REJECTED', 'OPERATOR'), pendingMsg] };
const plc = flow.get('plc') || {};
if (plc.mode !== 'REMOTE_MANUAL' || plc.maintenance === true) {
    return { batch: [resp('REJECTED', plc.maintenance === true ? 'MAINTENANCE' : `MODE_${plc.mode}`), pendingMsg] };
}
const cmd = { topic: job.command_topic, qos: 1, retain: false, payload: JSON.stringify({ job_order_id: job.job_order_id,
    code: job.code, value: job.value, expires_at: Math.floor(now) + 30, operator_accepted: 1, job_hash: job.job_hash }) };
return { batch: [resp('OPERATOR_ACCEPTED', 'OPERATOR'), cmd, pendingMsg] };
