// 발행 확인(PUBACK) → 수용 응답. 제한 시간이 지나 이미 거부로 답했으면 아무것도 하지 않는다.
const pending = flow.get('pending') || {};
if (!pending[msg._msgid]) return null;
delete pending[msg._msgid];
flow.set('pending', pending);
const counters = flow.get('counters') || {};
counters.accepted = (counters.accepted || 0) + 1;
flow.set('counters', counters);
const req = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload;
node.log(`수용 ${req.job_order_id} ${req.work_master_id} → ${msg.topic} (만료 ${req.expires_at})`);
return { _msgid: msg._msgid, res: msg.res, statusCode: 202,
         payload: { status: 'ACCEPTED', job_order_id: req.job_order_id, expires_at: req.expires_at } };
