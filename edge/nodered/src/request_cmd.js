// 외부 요청 명령(OT 수신기 → …/cmd/request) → PLC 외부 요청 채널(%MW20..27). PLC 가 만료·중복·모드·범위를 다시 검사한다.
const reg = global.get('registry');
let b;
try { b = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload; } catch (e) { node.warn('요청 명령 해석 실패'); return null; }
if (msg.retain) return null;
const ok = typeof b.job_order_id === 'string' && Number.isInteger(b.code) && Number.isInteger(b.value)
    && Number.isInteger(b.expires_at) && Number.isInteger(b.job_hash) && b.job_hash > 0;
if (!ok) { node.warn('요청 명령 형식 오류'); return null; }
const seq = (((flow.get('rqSeq') || 0) + 1) & 0xFFFF) || 1;
flow.set('rqSeq', seq);
const byHash = flow.get('jobByHash') || {};
byHash[b.job_hash] = b.job_order_id;
for (const k of Object.keys(byHash).slice(0, -64)) delete byHash[k];
flow.set('jobByHash', byHash);
const base = reg.plc.write.request;
const e = b.expires_at >>> 0;
return { payload: { value: [b.code, b.value & 0xFFFF, e >>> 16, e & 0xFFFF, b.operator_accepted ? 1 : 0,
                            b.job_hash >>> 16, b.job_hash & 0xFFFF], fc: 16, unitid: reg.plc.unit_id, address: base + 1, quantity: 7 },
         seqWrite: { value: [seq], fc: 16, unitid: reg.plc.unit_id, address: base, quantity: 1 } };
