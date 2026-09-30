// 시각 동기: 1초마다 PLC %MW0..1 에 epoch 초를 쓴다(PLC 가 외부 요청 만료를 검사하는 기준).
const reg = global.get('registry');
const t = Math.floor(Date.now() / 1000);
msg.payload = { value: [Math.floor(t / 65536), t % 65536], fc: 16, unitid: reg.plc.unit_id, address: reg.plc.write.time_sync, quantity: 2 };
return msg;
