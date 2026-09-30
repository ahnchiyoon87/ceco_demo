// 장치 통신 상태(Sparkplug DDEATH 흉내): PLC 폴링 성공·실패로 PLC 통신 상태를 내고,
// 끊기면 마지막 값을 품질 STALE 로 한 번 낸다. 입력 = Modbus 읽기 노드들의 상태(status 노드).
const reg = global.get('registry');
const st = msg.status || {};
const text = String(st.text || '').toLowerCase();
let online = null;
if (/error|disconnect|closed|fail|timeout|broken|reconnect|stopped/.test(text) || st.fill === 'red') online = false;
else if (/active|polling|reading done|connected/.test(text) || st.fill === 'green') online = true;
if (online === null || online === flow.get('plcOnline')) return null;
flow.set('plcOnline', online);
node.status({ fill: online ? 'green' : 'red', shape: 'dot', text: online ? 'PLC 통신 정상' : 'PLC 통신 끊김' });
const tsNs = Date.now() * 1e6;
const out = [{ topic: reg.plc.comm_topic, qos: 1, retain: true, payload: JSON.stringify({ ts: tsNs, value: online, quality: 'GOOD' }) }];
if (!online) {
    const lastPub = flow.get('lastPub') || {};
    const lv = flow.get('lastValues') || {};
    for (const t of reg.tags) {
        const lp = lastPub[t.tag];
        if (!lp) continue;
        out.push({ topic: t.topic, qos: 1, retain: false, payload: JSON.stringify({ ts: tsNs, value: lp.value, quality: 'STALE', seq: lv.seq, pts: lv.pts }) });
        lastPub[t.tag] = { ...lp, quality: 'STALE' };
    }
    flow.set('lastPub', lastPub);
}
return { batch: out };
