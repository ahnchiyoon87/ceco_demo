// DMZ 브로커 연결 상태 기억(초록 = 연결됨)
flow.set('connected', msg.status.fill === 'green');
return null;
