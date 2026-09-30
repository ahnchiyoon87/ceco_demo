// OT 허브 연결 상태(MQTT 출력 노드의 상태) → 끊김 버퍼가 쓰는 연결 표시. 다시 붙으면 쌓인 것을 바로 보낸다.
const text = String((msg.status || {}).text || '').toLowerCase();
const up = text.includes('connected') && !text.includes('disconnected') && !text.includes('connecting');
const was = flow.get('mqttUp') === true;
flow.set('mqttUp', up);
if (up && !was) return { _flush: true };
return null;
