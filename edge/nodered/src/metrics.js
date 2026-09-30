// 엣지 지표(Prometheus 텍스트). OT 쪽 Prometheus agent 가 읽는다.
const q = flow.get('safQueue', 'disk') || [];
msg.payload = [
    '# HELP edge_published_total UNS 로 낸 메시지 수', '# TYPE edge_published_total counter', `edge_published_total ${flow.get('published') || 0}`,
    '# HELP edge_saf_queue 끊김 버퍼에 쌓인 메시지 수', '# TYPE edge_saf_queue gauge', `edge_saf_queue ${q.length}`,
    '# HELP edge_saf_dropped_total 끊김 버퍼 한도로 버린 메시지 수', '# TYPE edge_saf_dropped_total counter', `edge_saf_dropped_total ${flow.get('safDropped') || 0}`,
    '# HELP edge_plc_online PLC 통신 정상(1)', '# TYPE edge_plc_online gauge', `edge_plc_online ${flow.get('plcOnline') === false ? 0 : 1}`,
    '# HELP edge_mqtt_up OT 허브 연결(1)', '# TYPE edge_mqtt_up gauge', `edge_mqtt_up ${flow.get('mqttUp') === true ? 1 : 0}`,
    ''].join('\n');
msg.headers = { 'Content-Type': 'text/plain; version=0.0.4' };
return msg;
