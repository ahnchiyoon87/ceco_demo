// 끊김 시 저장 후 전송(store-and-forward): OT 허브 연결이 끊긴 동안 보낼 메시지를 디스크 컨텍스트에 쌓고,
// 다시 붙으면 순서대로 먼저 보낸다. 한도를 넘으면 새 값을 버리고 버린 건수를 센다(17번 D10 과 같은 정책).
// 입력: {batch:[메시지…]} 또는 {_flush:true}(재연결 알림). 출력: MQTT 출력 노드로 보낼 메시지들.
const LIMIT = 72000;
const up = flow.get('mqttUp') === true;
const q = flow.get('safQueue', 'disk') || [];
const incoming = msg._flush ? [] : (Array.isArray(msg.batch) ? msg.batch : [msg]);
const pack = m => ({ topic: m.topic, payload: m.payload, qos: m.qos, retain: m.retain });
if (!up) {
    for (const m of incoming) {
        if (q.length >= LIMIT) { flow.set('safDropped', (flow.get('safDropped') || 0) + 1); continue; }
        q.push(pack(m));
    }
    flow.set('safQueue', q, 'disk');
    node.status({ fill: 'yellow', shape: 'ring', text: `끊김: 보관 ${q.length}` });
    return null;
}
const out = q.concat(incoming.map(pack));
if (q.length) {
    flow.set('safQueue', [], 'disk');
    node.status({ fill: 'green', shape: 'dot', text: `재전송 ${q.length}` });
}
flow.set('published', (flow.get('published') || 0) + out.length);
return [out];
