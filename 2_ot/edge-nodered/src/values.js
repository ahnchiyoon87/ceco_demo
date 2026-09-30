// 계측값 블록(PLC 입력 레지스터 0..27 = 값 12점 + 스캔 순번 + 설비 시각, 한 번의 FC4 읽기).
// 새 스캔일 때만 UNS 와 수업용 edgex/telemetry 로 낸다. 결측 표시값은 버리고 품질 BAD 로 낸다.
const reg = global.get('registry');
const w = msg.payload;
if (!Array.isArray(w) || w.length < 28) return null;
const seq = w[24] * 65536 + w[25];
const pts = w[26] * 65536 + w[27];
if (seq === context.get('lastSeq')) return null;
context.set('lastSeq', seq);
const st = flow.get('plcStatus') || {};
const fieldOk = st.field_comm === 1;
const tsNs = Date.now() * 1e6;
const buf = Buffer.alloc(4);
const f32 = (hi, lo) => { buf.writeUInt16BE(hi, 0); buf.writeUInt16BE(lo, 2); return buf.readFloatBE(0); };
const lastPub = flow.get('lastPub') || {};
const uns = [];
const readings = [];
for (const t of reg.tags) {
    const raw = f32(w[t.plc_ir], w[t.plc_ir + 1]);
    const value = Number.isFinite(raw) && raw > -1000 ? Math.round(raw * 10000) / 10000 : null;
    const quality = value === null ? 'BAD' : (fieldOk ? 'GOOD' : 'STALE');
    const lp = lastPub[t.tag];
    // 보고 조건(17번 D2): 품질 변화, deadband 를 넘는 변화, 최대 간격(공정 시간 — 설비 시각 pts 로 잰다)
    const due = !lp || lp.quality !== quality || value === null || lp.value === null
        || Math.abs(value - lp.value) >= t.deadband || pts < lp.pts || (pts - lp.pts) >= t.max_interval_s;
    if (due) {
        uns.push({ topic: t.topic, qos: 1, retain: false, payload: JSON.stringify({ ts: tsNs, value, quality, seq, pts }) });
        lastPub[t.tag] = { value, quality, pts };
    }
    if (value !== null) {
        readings.push({ id: `${seq}-${t.tag}`, origin: tsNs, deviceName: reg.hierarchy.line, resourceName: t.tag,
            profileName: 'AR100-Reactor-Line', valueType: 'Float32', value: String(value) });
    }
}
flow.set('lastPub', lastPub);
flow.set('lastValues', { seq, pts, tsNs });
// 수업 자료가 쓰는 edgex/telemetry: 같은 데이터를 EdgeX Event 모양으로 낸다(같은 데이터의 이름 둘, 정본은 등록부)
uns.push({ topic: reg.edgex_telemetry_topic, qos: 1, retain: false, payload: JSON.stringify({
    apiVersion: 'v3', id: String(seq), deviceName: reg.hierarchy.line, profileName: 'AR100-Reactor-Line',
    sourceName: 'AllSensors', origin: tsNs, readings }) });
return { batch: uns };
