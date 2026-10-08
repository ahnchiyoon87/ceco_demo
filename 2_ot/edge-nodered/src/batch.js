// 수신기 출력 묶음을 한 건씩 보낸다. 출력 1 = MQTT(OT 허브 안에서만 발행하므로 끊김 버퍼를 두지 않는다),
// 출력 2 = 가상 정비팀 작업 지시(_crew). 같은 묶음 함수를 엣지·수신기가 함께 쓴다(엣지는 _crew 를 만들지 않는다).
const items = msg.batch || [];
return [items.filter(m => !m._crew), items.filter(m => m._crew)];
