// 상태 블록(PLC 홀딩 레지스터 100..118 = 설정값 3 + 상태·ACK 16, 한 번의 FC3 읽기).
// 바뀐 상태만 보존(retain) 토픽으로 내고, 최대 간격마다 전부 다시 낸다. ACK 순번이 바뀌면 ACK 를 낸다.
const reg = global.get('registry');
const w = msg.payload;
if (!Array.isArray(w) || w.length < 19) return null;
const s = {};
reg.plc.read_status.fields.forEach((k, i) => { s[k] = w[i]; });
const prev = flow.get('plcStatus');
flow.set('plcStatus', s);
const now = Date.now();
const tsNs = now * 1e6;
// RUN/STOP: PLC 하트비트가 2초 넘게 멈추면 STOP(PLC 가 프로그램을 돌리지 않음)
let hb = context.get('hb') || { v: -1, at: now };
if (s.heartbeat !== hb.v) hb = { v: s.heartbeat, at: now };
context.set('hb', hb);
const P = `${reg.line_prefix}/${reg.plc.asset}`;
const values = {
    [`${P}/status/mode`]: reg.plc.modes[String(s.mode)] || 'UNKNOWN',
    [`${P}/status/maintenance`]: s.maintenance === 1,
    [`${P}/status/maint_operator`]: s.maint_operator,
    [`${P}/status/interlock`]: s.interlock === 1,
    [`${P}/status/estop`]: s.estop === 1,
    [`${P}/status/field_comm`]: s.field_comm === 1,
    [`${P}/status/run_state`]: (now - hb.at) > 2000 ? 'STOP' : 'RUN',
    [`${P}/status/fb_fault`]: s.fb_fault,
};
const sp = { 'P-101/speed_sp': s.sp_pump, 'CV-101/open_sp': s.sp_valve, 'R-101/temp_sp': s.sp_temp_x10 };
for (const c of reg.commands) {
    const key = `${c.asset}/${c.name}`;
    if (key in reg.plc.outputs_bits) values[c.status_topic] = ((s.outputs >> reg.plc.outputs_bits[key]) & 1) === 1;
    else if (key in sp) values[c.status_topic] = sp[key] / (c.scale || 1);
}
const last = context.get('last') || {};
const full = (now - (context.get('fullAt') || 0)) >= reg.plc.state_max_interval_wall_s * 1000;
if (full) context.set('fullAt', now);
const out = [];
for (const [topic, value] of Object.entries(values)) {
    if (full || last[topic] !== value) {
        out.push({ topic, qos: 1, retain: true, payload: JSON.stringify({ ts: tsNs, value, quality: 'GOOD' }) });
        last[topic] = value;
    }
}
context.set('last', last);
// ACK: 기동 뒤 첫 읽기에서는 내지 않는다(이전 ACK 를 새 것으로 오인하지 않게). 순번은 PLC 에서 이어받아 다음 명령 순번이 겹치지 않게 한다.
if (!prev) {
    flow.set('opSeq', s.op_ack_seq);
    flow.set('rqSeq', s.rq_ack_seq);
} else {
    const codes = reg.plc.ack_codes;
    if (s.op_ack_seq !== prev.op_ack_seq) {
        const cmd = (flow.get('opBySeq') || {})[s.op_ack_seq] || null;
        out.push({ topic: reg.plc.ack_operator_topic, qos: 1, retain: false, payload: JSON.stringify({
            ts: tsNs, source: 'plc', seq: s.op_ack_seq, code: s.op_ack_code, result: codes[String(s.op_ack_code)] || 'UNKNOWN', command: cmd }) });
    }
    if (s.rq_ack_seq !== prev.rq_ack_seq) {
        const hash = s.rq_ack_hash_hi * 65536 + s.rq_ack_hash_lo;
        const job = (flow.get('jobByHash') || {})[hash] || null;
        out.push({ topic: reg.plc.ack_request_topic, qos: 1, retain: false, payload: JSON.stringify({
            ts: tsNs, source: 'plc', seq: s.rq_ack_seq, job_hash: hash, job_order_id: job,
            code: s.rq_ack_code, result: codes[String(s.rq_ack_code)] || 'UNKNOWN' }) });
    }
}
if (!out.length) return null;
return { batch: out };
