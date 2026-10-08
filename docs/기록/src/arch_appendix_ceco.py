# -*- coding: utf-8 -*-
"""ceco_demo 부록: 저장소 파일에서 빌드 때마다 직접 뽑는 전체 목록. 반환 (html, 대조용 이름 dict)."""
import json, pathlib, re

import yaml

import arch_inventory as I
from arch_inventory import code, esc, table

ROOT = pathlib.Path(__file__).resolve().parents[3]


def kafka_topics():
    s = (ROOT / "4_it/stream-kafka/create-topics.sh").read_text(encoding="utf-8")
    rows, names = [], []
    for m in re.finditer(r"^create\s+(\S+)\s+(\d+)\s+(\S+)\s*(#.*)?$", s, re.M):
        names.append(m.group(1))
        rows.append([code(m.group(1)), esc(m.group(2)), esc(m.group(3).replace("$D7", "7일").replace("$D30", "30일")), "1", esc((m.group(4) or "").lstrip("# "))])
    assert len(names) == len(re.findall(r"^create\s", s, re.M)), "create-topics.sh 의 create 줄을 다 읽지 못함"
    return table(["토픽", "파티션", "보존", "복제", "주석(원문)"], rows), names


def acl(path):
    s = (ROOT / path).read_text(encoding="utf-8")
    rows, user = [], "(모든 계정)"
    for ln in s.splitlines():
        ln = ln.strip()
        if ln.startswith("user "):
            user = ln[5:]
        elif ln.startswith(("topic ", "pattern ")):
            parts = ln.split(None, 2)
            rows.append([code(user), esc(parts[1] if len(parts) == 3 else "readwrite"), code(parts[-1]), parts[-1]])
    n = sum(1 for ln in s.splitlines() if ln.strip().startswith(("topic ", "pattern ")))
    assert len(rows) == n, f"{path} 의 topic 줄을 다 읽지 못함"
    return rows


def bridge():
    s = (ROOT / "2_ot/factory-broker-mosquitto/mosquitto.conf").read_text(encoding="utf-8")
    rows = [[code(m.group(1)), esc(m.group(2)), esc(m.group(3))] for m in re.finditer(r"^topic\s+(\S+)\s+(in|out|both)\s+(\d)", s, re.M)]
    assert len(rows) == len(re.findall(r"^topic\s", s, re.M))
    return table(["토픽(브리지)", "방향(OT 허브 기준)", "QoS"], rows)


def router():
    s = (ROOT / "shared/network-router/rules.sh").read_text(encoding="utf-8")
    rows = [[esc(m.group(1)), esc(m.group(2)), esc(m.group(3)), esc(m.group(4)), esc(m.group(5)), esc(m.group(6))]
            for m in re.finditer(r'^allow\s+(\S+)\s+(\S+)\s+(\d+)\s+(\S+)\s+(\d+)\s+"([^"]+)"', s, re.M)]
    assert len(rows) == len(re.findall(r"^allow\s", s, re.M)), "rules.sh 의 allow 줄을 다 읽지 못함"
    return table(["출발 대역", "라우터 주소", "라우터 포트", "목적지", "목적지 포트", "이름(원문)"], rows), len(rows)


def bento():
    rows = []
    files = sorted((ROOT / "4_it/collector-bento/streams").glob("*.yaml")) + [ROOT / "3_dmz/loader-bento/loader.yaml"] + sorted((ROOT / "4_it").glob("history-bento/*.yaml"))
    for p in files:
        assert p.exists(), p
        y = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        ins = ", ".join(_kinds(y.get("input")))
        outs = ", ".join(_kinds(y.get("output")))
        procs = ", ".join(_kinds((y.get("pipeline") or {}).get("processors")))
        rows.append([f'<span class="ref">{esc(p.relative_to(ROOT).as_posix())}</span>', esc(ins), esc(procs) or "—", esc(outs)])
    return table(["스트림 파일", "입력", "처리기", "출력"], rows)


def _kinds(x):
    if x is None:
        return []
    if isinstance(x, list):
        out = []
        for e in x:
            out += _kinds(e)
        return out
    if isinstance(x, dict):
        out = []
        for k, v in x.items():
            if k in ("label", "processors", "batching"):
                continue
            if k in ("broker", "fan_out", "switch", "sequence", "try", "catch", "branch", "workflow", "fallback"):
                inner = v.get("outputs") or v.get("inputs") or v.get("cases") or v.get("processors") if isinstance(v, dict) else v
                out.append(k + "(" + ", ".join(_kinds(inner if not isinstance(inner, list) else [c.get("output", c.get("processors", c)) if isinstance(c, dict) else c for c in inner])) + ")")
            else:
                out.append(k)
        return out
    return []


def registry():
    t = json.loads((ROOT / "shared/registry/generated/tags.json").read_text(encoding="utf-8"))
    tr = [[code(x["tag"]), esc(x["asset"]), esc(x.get("class", "")), esc(x.get("unit", "")), esc(f'{x.get("lsl")} ~ {x.get("usl")}'), esc(x.get("plc_ir", "")),
           esc(x.get("deadband", "")), esc(x.get("max_interval_s", "")), code(x.get("topic", ""))] for x in t["tags"]]
    cr = [[esc(c["asset"]), code(c["name"]), esc(c.get("code", "")), esc(c.get("kind", "")), esc(f'{c.get("min", "")} ~ {c.get("max", "")}' if "min" in c else "—"), esc(c.get("desc", ""))] for c in t["commands"]]
    w = json.loads((ROOT / "shared/registry/generated/work_masters.ot.json").read_text(encoding="utf-8"))
    wr = [[code(x["work_master_id"]), esc(x.get("equipment_id", "")), esc(x.get("kind", "")), esc(x.get("command", "")), esc(", ".join(p.get("name", "") if isinstance(p, dict) else str(p) for p in x.get("parameters", []))), esc(x.get("desc", ""))] for x in w]
    return (table(["태그", "설비", "종류", "단위", "규격(LSL ~ USL)", "PLC IR", "deadband", "최대 간격(설비 s)", "UNS 토픽"], tr),
            table(["설비", "명령", "코드", "종류", "범위", "설명"], cr), table(["작업 정의", "설비", "종류", "명령", "파라미터", "설명"], wr), len(tr), len(cr), len(wr))


def prom():
    rows = []
    for f in ("it.yml", "dmz.yml", "ot-agent.yml"):
        y = yaml.safe_load((ROOT / "shared/monitoring-prometheus" / f).read_text(encoding="utf-8")) or {}
        for j in y.get("scrape_configs", []):
            tg = []
            for sc in j.get("static_configs", []):
                tg += sc.get("targets", [])
            rows.append([esc(f), code(j.get("job_name", "")), esc(j.get("metrics_path", "/metrics")), esc(", ".join(tg))])
    return table(["설정", "job", "경로", "대상"], rows)


def knowledge_routes():
    base = ROOT / "5_ai/server/knowledge/backend/src"
    app = (base / "host/app.py").read_text(encoding="utf-8")
    regs = re.findall(r"from \.\.modules\.([\w.]+) import (\w+) as \w+_router", app) + re.findall(r"from \.\.modules\.([\w.]+) import (?:\w+, )*?(router) as \w+", app)
    regs = sorted(set(regs))
    rows = []
    for mod, var in regs:
        f = base / "modules" / (mod.replace(".", "/") + ".py")
        s = f.read_text(encoding="utf-8")
        pm = re.search(rf"^{var}\s*=\s*APIRouter\(([^)]*)\)", s, re.M)
        pre = re.search(r"prefix\s*=\s*[\"']([^\"']+)", pm.group(1)).group(1) if pm and "prefix" in pm.group(1) else ""
        rows += I.routes([("knowledge", f)], ROOT, objs=(var,), prefixes={(f.name, var): pre})
        for m in re.finditer(r'\(\s*"(/api/[^"]+)",\s*(\w+)\s*\)', s) if var == "read_router" else []:
            rows.append(("knowledge", "GET", m.group(1), f"{f.relative_to(ROOT).as_posix()}:{s.count(chr(10), 0, m.start()) + 1}"))
    return rows, len(regs)


def build():
    t_svc, t_vol, t_net, names = I.compose(ROOT / "compose.yml")
    t_kafka, kafka = kafka_topics()
    ot_acl, dmz_acl = acl("2_ot/factory-broker-mosquitto/acl"), acl("3_dmz/dmz-broker-mosquitto/acl")
    t_rt, nrt = router()
    pg = I.sql_objects(sorted((ROOT / "4_it/db-postgres/init").glob("*.sql")), ROOT)
    flink = I.sql_objects(sorted((ROOT / "4_it/detection-flink/sql").glob("*.sql")), ROOT)
    fl_ins = []
    for p in sorted((ROOT / "4_it/detection-flink/sql").glob("*.sql")):
        s = p.read_text(encoding="utf-8")
        for m in re.finditer(r"insert\s+into\s+(\w+)", s, re.I):
            fl_ins.append([f'<span class="ref">{esc(p.name)}</span>', code(m.group(1))])
    ai_py = [p for p in (ROOT / "5_ai/server/knowledge/backend/src").rglob("*.py") if "test" not in p.name and "CREATE TABLE" in p.read_text(encoding="utf-8").upper()]
    ai = I.sql_objects(sorted(ai_py), ROOT)
    t_tag, t_cmd, t_wm, ntag, ncmd, nwm = registry()
    krt, nreg = knowledge_routes()
    am = (ROOT / "shared/monitoring-prometheus/alertmanager.yml").read_text(encoding="utf-8")
    h = (f'<h3 id="ap-svc">compose 서비스 {len(names["services"])}개</h3><p class="meta-note">근거: <code>compose.yml</code>. 환경변수는 이름만 실었습니다(값 · 키는 싣지 않음).</p>{t_svc}'
         f'<h3 id="ap-vol">볼륨 {len(names["volumes"])}개 · 망 {len(names["networks"])}개</h3><p class="meta-note">망 서브넷의 <code>${{NET_PREFIX}}</code>는 .env 값입니다.</p>{t_vol}{t_net}'
         f'<h3 id="ap-router">라우터 허용 경로 {nrt}개</h3><p class="meta-note">근거: <code>shared/network-router/rules.sh</code>의 allow 줄. 이 밖의 FORWARD는 모두 DROP.</p>{t_rt}'
         f'<h3 id="ap-kafka">Kafka 토픽 {len(kafka)}개</h3><p class="meta-note">근거: <code>4_it/stream-kafka/create-topics.sh</code> — 복제 1 · lz4.</p>{t_kafka}'
         f'<h3 id="ap-acl">MQTT ACL — OT 허브 {len(ot_acl)}줄 · DMZ 브로커 {len(dmz_acl)}줄</h3><p class="meta-note">근거: <code>2_ot/factory-broker-mosquitto/acl</code> · <code>3_dmz/dmz-broker-mosquitto/acl</code>. 익명 접속은 두 브로커 모두 금지.</p>'
         f'<h4>OT 허브(ot-hub)</h4>{table(["계정", "권한", "토픽"], [r[:3] for r in ot_acl])}<h4>DMZ 브로커(dmz-broker)</h4>{table(["계정", "권한", "토픽"], [r[:3] for r in dmz_acl])}'
         f'<h4>OT 허브 → DMZ 브리지(connection dmz)</h4>{bridge()}'
         f'<h3 id="ap-reg">등록부: 태그 {ntag} · 명령 {ncmd} · 작업 정의 {nwm}</h3><p class="meta-note">근거: <code>shared/registry/generated/</code>(정본 <code>equipment.yaml</code>에서 generate.py가 만든 것).</p>{t_tag}{t_cmd}{t_wm}'
         f'<h3 id="ap-pg">PostgreSQL 초기화 객체 {len(pg)}개</h3><p class="meta-note">근거: <code>4_it/db-postgres/init/*.sql</code>(빈 볼륨 첫 기동 때만 실행).</p>{I.sql_html(pg)}'
         f'<h3 id="ap-ai">knowledge 코드가 기동 때 만드는 표 {len(ai)}개</h3><p class="meta-note">근거: knowledge 코드 안의 CREATE TABLE 문. 파일 칸으로 어디에 생기는지 구분합니다: <code>session_store.py</code>는 SQLite <code>sessions.db</code>(볼륨 knowledge-data), 나머지는 PostgreSQL DB <code>ai</code>.</p>{I.sql_html(ai)}'
         f'<h3 id="ap-flink">Flink SQL 표 · 잡</h3>{I.sql_html(flink)}{table(["파일", "INSERT INTO(잡의 출력 표)"], fl_ins)}'
         f'<h3 id="ap-bento">Bento 스트림</h3>{bento()}'
         f'<h3 id="ap-prom">Prometheus 수집 대상</h3><p class="meta-note">감시 프로필에서만 뜹니다.</p>{prom()}'
         f'<h3 id="ap-am">Alertmanager 설정 원문</h3><pre class="code">{esc(am)}</pre>'
         f'<h3 id="ap-api">knowledge HTTP API — 앱에 등록된 경로 {len(krt)}개(라우터 {nreg}개)</h3><p class="meta-note"><code>host/app.py</code>가 include_router 한 라우터만 실었습니다. 코드에 남아 있지만 등록되지 않은 경로(온톨로지 편집 · agent_session 등)는 이 표에 없습니다.</p>{I.routes_html(krt)}')
    mqtt = sorted({r[3] for r in ot_acl + dmz_acl})
    return h, dict(names, kafka=kafka, mqtt=mqtt)
