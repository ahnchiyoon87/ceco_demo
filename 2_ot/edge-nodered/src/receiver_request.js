// OT 작업 요청 수신기(현업 L3 MES 서버·SCADA MES 모듈 흉내, 17번 E20): 받을지 OT 안에서 정한다.
// 입력 = 스키마 검사를 통과한 작업 요청. 검사: 중복(QoS 1)·허용 작업·설비·파라미터 범위·만료·모드·정비 모드.
// REMOTE_AUTO → 자동 수용(StoreAndStart), REMOTE_MANUAL → 운전원 대기로 저장(Store), 그 밖 → 거부.
// 결정과 제어기 명령 토픽 발행까지만 한다(설비 쓰기는 엣지 → PLC 길).
const reg = global.get('registry');
const wm = global.get('workMastersOt');
const crypto = global.get('crypto');
const req = msg.payload;
const now = Date.now() / 1000;
const iso = new Date().toISOString();
const resp = (stage, status, reason) => ({ topic: `${reg.request.response_prefix}/${req.job_order_id}`, qos: 1, retain: false,
    payload: JSON.stringify({ job_order_id: req.job_order_id, stage, status, reason, ts: iso }) });
const pendingMsg = (pending) => {
    const items = Object.values(pending).sort((a, b) => a.received_at - b.received_at);
    const h = items[0];
    return { topic: reg.request.pending_topic, qos: 1, retain: true, payload: JSON.stringify({
        count: items.length, head_job: h ? h.job_order_id : '', head_wm: h ? h.work_master_id : '',
        head_desc: h ? h.desc : '대기 중인 요청 없음', head_context: h ? (h.context_summary || '') : '',
        head_wait_s: h ? Math.round(now - h.received_at) : 0,
        items: items.map(i => ({ job_order_id: i.job_order_id, work_master_id: i.work_master_id, desc: i.desc })) }) };
};
flow.set('requests', (flow.get('requests') || 0) + 1);
// 중복: MQTT QoS 1 은 같은 메시지를 다시 보낼 수 있다(규격). 만료 시간 안에 본 ID 는 다시 처리하지 않는다(17번 E19)
const seen = flow.get('seen') || {};
for (const k of Object.keys(seen)) if (seen[k] < now) delete seen[k];
if (seen[req.job_order_id]) { flow.set('seen', seen); return null; }
seen[req.job_order_id] = (Number(req.expires_at) || now) + 60;
flow.set('seen', seen);
const reject = (reason) => { flow.set('rejected', (flow.get('rejected') || 0) + 1); return { batch: [resp('receipt', 'REJECTED', reason)] }; };
const w = wm.find(x => x.work_master_id === req.work_master_id);
if (!w) return reject('NOT_ALLOWED');
if (w.equipment_id !== req.equipment_id) return reject('EQUIPMENT_MISMATCH');
let value = w.fixed_value;
for (const p of w.parameters) {
    const got = (req.job_order_parameters || []).find(x => x.id === p.id);
    if (!got) return reject('PARAMETER_MISSING');
    if (!(got.value >= p.min && got.value <= p.max)) return reject('PARAMETER_RANGE');
    value = Math.round(got.value * (w.scale || 1));
}
if (!(Number(req.expires_at) > now)) return reject('EXPIRED');
const plc = flow.get('plc') || {};
if (plc.run_state !== 'RUN' || plc.field_comm === false) return reject('PLC_UNAVAILABLE');
if (plc.mode === 'LOCAL') return reject('LOCAL_MODE');
if (plc.maintenance === true) return reject('MAINTENANCE');
const hash = parseInt(crypto.createHash('sha256').update(req.job_order_id).digest('hex').slice(0, 8), 16) || 1;
const job = { job_order_id: req.job_order_id, work_master_id: w.work_master_id, equipment_id: w.equipment_id, desc: w.desc,
    code: w.code, value, command_topic: w.command_topic, job_hash: hash, received_at: now, expires_at: Math.floor(Number(req.expires_at)),
    // 운전원 화면에 누가 보낸 요청인지 앞에 붙인다(요청자 종류·ID)
    context_summary: `[${String(req.requester_type).toUpperCase()} ${req.requester}] ` + (req.context ? String(req.context.summary || '').slice(0, 120) : '') };
if (plc.mode === 'REMOTE_AUTO') {
    const cmd = { topic: w.command_topic, qos: 1, retain: false, payload: JSON.stringify({ job_order_id: job.job_order_id,
        code: job.code, value: job.value, expires_at: job.expires_at, operator_accepted: 0, job_hash: hash }) };
    return { batch: [resp('receipt', 'AUTO_ACCEPTED', 'REMOTE_AUTO'), cmd] };
}
if (plc.mode === 'REMOTE_MANUAL') {
    const pending = flow.get('pending') || {};
    pending[job.job_order_id] = job;
    flow.set('pending', pending);
    return { batch: [resp('receipt', 'OPERATOR_WAIT', 'STORED'), pendingMsg(pending)] };
}
return reject('MODE_UNKNOWN');
