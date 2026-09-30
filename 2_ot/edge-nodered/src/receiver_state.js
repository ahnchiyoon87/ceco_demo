// PLC 상태 토픽(모드·정비 모드·실행 상태·현장 통신)을 수신기가 따로 구독해 둔다(엣지 수집 흐름과 떨어진 전용 계정).
const field = msg.topic.split('/').pop();
let v;
try { v = JSON.parse(msg.payload).value; } catch (e) { return null; }
const plc = flow.get('plc') || {};
plc[field] = v;
flow.set('plc', plc);
return null;
