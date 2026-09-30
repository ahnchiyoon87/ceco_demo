// Prometheus 텍스트(DMZ Prometheus 가 dmz-gateway:8088/metrics 를 긁는다)
const counters = flow.get('counters') || {};
const lines = ['# TYPE gateway_requests_total counter'];
for (const k of Object.keys(counters).sort()) lines.push(`gateway_requests_total{result="${k}"} ${counters[k]}`);
lines.push('# TYPE gateway_broker_connected gauge', `gateway_broker_connected ${flow.get('connected') ? 1 : 0}`, '');
msg.headers = { 'Content-Type': 'text/plain; version=0.0.4' };
msg.payload = lines.join('\n');
return msg;
