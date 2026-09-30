// 운전원 대기 60초(벽시계, 17번 E18): 넘으면 OPERATOR_TIMEOUT 으로 거부하고 대기 목록에서 뺀다.
const reg = global.get('registry');
const pending = flow.get('pending') || {};
const now = Date.now() / 1000;
const iso = new Date().toISOString();
const out = [];
for (const [id, job] of Object.entries(pending)) {
    if (now - job.received_at >= 60) {
        delete pending[id];
        out.push({ topic: `${reg.request.response_prefix}/${id}`, qos: 1, retain: false,
            payload: JSON.stringify({ job_order_id: id, stage: 'operator', status: 'REJECTED', reason: 'OPERATOR_TIMEOUT', ts: iso }) });
    }
}
const items = Object.values(pending).sort((a, b) => a.received_at - b.received_at);
const h = items[0];
const snapshot = JSON.stringify({ count: items.length, head_job: h ? h.job_order_id : '', head_wm: h ? h.work_master_id : '',
    head_desc: h ? h.desc : '대기 중인 요청 없음', head_context: h ? (h.context_summary || '') : '',
    items: items.map(i => ({ job_order_id: i.job_order_id, work_master_id: i.work_master_id, desc: i.desc })) });
// 목록이 바뀌었거나 대기 중이면(대기 시간 표시) 다시 낸다
if (out.length || items.length || context.get('last') !== snapshot) {
    const payload = JSON.parse(snapshot);
    payload.head_wait_s = h ? Math.round(now - h.received_at) : 0;
    out.push({ topic: reg.request.pending_topic, qos: 1, retain: true, payload: JSON.stringify(payload) });
    context.set('last', snapshot);
}
flow.set('pending', pending);
return out.length ? { batch: out } : null;
