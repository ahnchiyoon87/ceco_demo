// 스키마 검사를 통과하지 못한 요청: 요청 ID 를 알 수 있으면 거부 응답을 낸다(알 수 없으면 기록만).
const reg = global.get('registry');
let id = null;
try { id = JSON.parse(msg.payload).job_order_id; } catch (e) { /* 해석 불가 */ }
if (typeof msg.payload === 'object' && msg.payload) id = msg.payload.job_order_id;
flow.set('rejected', (flow.get('rejected') || 0) + 1);
if (typeof id !== 'string' || !/^[A-Za-z0-9._:-]{8,80}$/.test(id)) { node.warn('스키마 오류 요청(ID 없음) 버림'); return null; }
return { batch: [{ topic: `${reg.request.response_prefix}/${id}`, qos: 1, retain: false,
    payload: JSON.stringify({ job_order_id: id, stage: 'receipt', status: 'REJECTED', reason: 'SCHEMA_INVALID',
        detail: JSON.stringify(msg.schemaError || (msg.error && msg.error.message) || '').slice(0, 300), ts: new Date().toISOString() }) }] };
