// PLC 의 외부 요청 ACK(엣지가 PLC 레지스터에서 읽어 …/ack/request 로 낸 것)를 요청 응답(셋째 단계 plc)으로 올린다.
const reg = global.get('registry');
let a;
try { a = JSON.parse(msg.payload); } catch (e) { return null; }
if (!a.job_order_id) return null;
return { batch: [{ topic: `${reg.request.response_prefix}/${a.job_order_id}`, qos: 1, retain: false,
    payload: JSON.stringify({ job_order_id: a.job_order_id, stage: 'plc', status: a.code === 0 ? 'ACCEPTED' : 'REJECTED',
        reason: a.result, plc_ack_code: a.code, ts: new Date().toISOString() }) }] };
