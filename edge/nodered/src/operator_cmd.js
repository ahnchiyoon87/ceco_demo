// 운전원 명령(FUXA → …/cmd/operator) → PLC 운전원 채널(%MW10..12). 받을지는 PLC 가 정하고 ACK 로 답한다.
// 엣지는 모양만 거른다: 보존(retain) 메시지·5초 넘은 명령·모르는 명령은 쓰지 않고 거부 ACK 를 낸다.
// 출력 1 = PLC 쓰기(명령 코드·값 → 끝나면 순번), 출력 2 = 엣지 거부 ACK
const reg = global.get('registry');
const asset = msg.topic.split('/')[3];
const tsNs = Date.now() * 1e6;
const reject = (result, extra) => [null, { batch: [{ topic: reg.plc.ack_operator_topic, qos: 1, retain: false,
    payload: JSON.stringify({ ts: tsNs, source: 'edge', result, command: { topic: msg.topic, ...extra } }) }] }];
let body;
try { body = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload; } catch (e) { return reject('BAD_PAYLOAD', {}); }
const cmd = reg.commands.find(c => c.asset === asset && c.name === body.command);
if (!cmd) return reject('UNKNOWN_COMMAND', { command: body.command });
if (msg.retain) return reject('RETAINED_COMMAND', { command: body.command });
const age = (Date.now() - Date.parse(body.ts)) / 1000;
if (!Number.isFinite(age) || age > 5 || age < -5) return reject('STALE_COMMAND', { command: body.command, ts: body.ts });
let v;
if (cmd.kind === 'switch') v = [true, 1, '1', 'true', 'on', 'ON'].includes(body.value) ? 1 : 0;
else if (cmd.kind === 'setpoint') v = Math.round(Number(body.value) * (cmd.scale || 1));
else if (cmd.kind === 'mode') v = ({ REMOTE_MANUAL: 1, REMOTE_AUTO: 2 })[body.value] || Number(body.value);
else if (cmd.kind === 'reset') v = 1;
else v = Number(body.value);
if (!Number.isInteger(v)) return reject('BAD_VALUE', { command: body.command, value: body.value });
const seq = (((flow.get('opSeq') || 0) + 1) & 0xFFFF) || 1;
flow.set('opSeq', seq);
const bySeq = flow.get('opBySeq') || {};
bySeq[seq] = { topic: msg.topic, command: body.command, value: body.value, ts: body.ts };
for (const k of Object.keys(bySeq).slice(0, -64)) delete bySeq[k];
flow.set('opBySeq', bySeq);
const base = reg.plc.write.operator;
// 명령 코드·값을 먼저 쓰고, 그 쓰기가 끝나면 순번을 쓴다(PLC 는 순번이 바뀐 것을 새 명령으로 본다)
return [{ payload: { value: [cmd.code, v & 0xFFFF], fc: 16, unitid: reg.plc.unit_id, address: base + 1, quantity: 2 },
          seqWrite: { value: [seq], fc: 16, unitid: reg.plc.unit_id, address: base, quantity: 1 } }, null];
