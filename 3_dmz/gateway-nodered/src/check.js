// 작업 요청 1차 검사. 출력 1 = 거부 응답, 출력 2 = DMZ 요청 토픽으로 발행.
// 검사: 토큰 · 스키마 · 허용 작업 ID·설비·파라미터 범위 · 요청자·승인자 허용 목록 · 요청 나이(10 s) · 중복(만료 시간 안의 ID) · 브로커 연결
const EXPIRY_S = 30, MAX_AGE_S = 10, PUBACK_TIMEOUT_MS = 2000;
const crypto = global.get('crypto');
const allow = global.get('allow');
const validate = global.get('validateJob');
const now = Date.now() / 1000;
const counters = flow.get('counters') || {};
const seen = flow.get('seen') || {};
const pending = flow.get('pending') || {};

function reject(reason, jid, code) {
    counters['rejected_' + reason] = (counters['rejected_' + reason] || 0) + 1;
    flow.set('counters', counters);
    node.log(`거부 ${jid} ${reason}`);
    msg.statusCode = code || 422;
    msg.payload = { status: 'REJECTED', reason, job_order_id: jid };
    return [msg, null];
}

const want = Buffer.from('Bearer ' + env.get('GATEWAY_CLIENT_TOKEN'));
const got = Buffer.from(msg.req.headers['authorization'] || '');
if (got.length !== want.length || !crypto.timingSafeEqual(got, want)) {
    msg.statusCode = 401;
    counters.rejected_UNAUTHORIZED = (counters.rejected_UNAUTHORIZED || 0) + 1;
    flow.set('counters', counters);
    msg.payload = { status: 'REJECTED', reason: 'UNAUTHORIZED' };
    return [msg, null];
}
let req;
try {
    req = JSON.parse(Buffer.isBuffer(msg.payload) ? msg.payload.toString('utf8') : String(msg.payload));
} catch (e) {
    return reject('SCHEMA_INVALID', null, 400);
}
const jid = (req && typeof req === 'object') ? req.job_order_id : null;
if (!req || typeof req !== 'object' || Array.isArray(req) || !validate(req)) return reject('SCHEMA_INVALID', jid);
const wm = allow.work_masters.find(w => w.work_master_id === req.work_master_id);
if (!wm) return reject('NOT_ALLOWED', jid);
if (wm.equipment_id !== req.equipment_id) return reject('EQUIPMENT_MISMATCH', jid);
for (const p of wm.parameters) {
    const v = req.job_order_parameters.find(x => x.id === p.id);
    if (!v) return reject('PARAMETER_MISSING', jid);
    if (!(p.min <= v.value && v.value <= p.max)) return reject('PARAMETER_RANGE', jid);
}
if (!allow.requesters.includes(req.requester)) return reject('REQUESTER_NOT_ALLOWED', jid);
if (!allow.approvers.includes(req.approver)) return reject('APPROVER_NOT_ALLOWED', jid);
const age = now - Number(req.created_at);
if (age > MAX_AGE_S || age < -2) return reject('TOO_OLD', jid);
for (const k of Object.keys(seen)) if (seen[k] < now) delete seen[k];
if (jid in seen) return reject('DUPLICATE', jid, 409);
// 브로커가 끊겨 있으면 기다리지 않고 바로 거부한다(동기 HTTP 응답 = 첫 겹)
if (!flow.get('connected')) return reject('BROKER_UNAVAILABLE', jid, 503);
seen[jid] = now + EXPIRY_S + 5;
flow.set('seen', seen);

req.expires_at = Math.floor(now) + EXPIRY_S;
// 발행 확인(PUBACK)이 2 s 안에 오지 않으면 거부로 답한다. 확인은 '발행 확인' 노드가 pending 에서 지운다.
pending[msg._msgid] = true;
flow.set('pending', pending);
const res = msg.res;
setTimeout(() => {
    const p = flow.get('pending') || {};
    if (!p[msg._msgid]) return;
    delete p[msg._msgid];
    flow.set('pending', p);
    const s = flow.get('seen') || {};
    delete s[jid];
    flow.set('seen', s);
    const c = flow.get('counters') || {};
    c.rejected_BROKER_UNAVAILABLE = (c.rejected_BROKER_UNAVAILABLE || 0) + 1;
    flow.set('counters', c);
    node.warn(`거부 ${jid} BROKER_UNAVAILABLE(발행 확인 없음)`);
    node.send([{ _msgid: msg._msgid, res, statusCode: 503,
                 payload: { status: 'REJECTED', reason: 'BROKER_UNAVAILABLE', job_order_id: jid } }, null]);
}, PUBACK_TIMEOUT_MS);
msg.topic = global.get('registry').request.in_topic;
msg.messageExpiryInterval = EXPIRY_S;
msg.payload = req;
return [null, msg];
