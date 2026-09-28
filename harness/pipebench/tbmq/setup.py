"""TBMQ 2.4.0 Kafka 통합(Integration Executor) 재현(09-29 결정: UI 설정은 API 재적용일 때만 인정). 패턴 P-C.

    python /repo/harness/pipebench/tbmq/setup.py apply    # exported.json 있으면 그것, 없으면 아래 SPEC 으로 POST /api/integration
    python /repo/harness/pipebench/tbmq/setup.py export   # 현재 통합 목록을 exported.json 으로

SPEC: 토픽 필터 iiot/# → Kafka kafka:9092 sensor.telemetry.raw, acks=all, lz4. 레코드 key 는 설정 가능한지 [미확인]
(V1 key=tag). 필드 이름은 TBMQ 2.x 통합 모델 기준 [미검증: 기동 금지 중 작성] — 틀리면 UI 로 1회 만든 뒤 export.
④ 운영 부담: 통합 설정이 DB(PostgreSQL)에 있어 파일로 버전 관리하려면 export 절차 필요.
"""
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

BASE = "http://tbmq:8083/api"
HERE = pathlib.Path(__file__).parent
SPEC = {"name": "pipebench-raw", "type": "KAFKA", "enabled": True, "allowCreateTopics": False,
        "configuration": {"topicFilters": ["iiot/#"], "clientConfiguration": {
            "bootstrapServers": "kafka:9092", "topic": "sensor.telemetry.raw", "key": "", "clientIdPrefix": "tbmq-ie-pipebench",
            "retries": 2147483647, "batchSize": 16384, "linger": 5, "bufferMemory": 33554432, "acks": "all",
            "compression": "lz4", "otherProperties": {"enable.idempotence": "true"}, "kafkaHeaders": {}, "sendMetadata": False}}}


def req(method, path, body=None, token=None):
    r = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Content-Type": "application/json"})
    if token:
        r.add_header("X-Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            t = resp.read().decode()
            return resp.status, (json.loads(t) if t.strip().startswith(("{", "[")) else t)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "apply"
    tok = None
    for _ in range(90):
        try:
            code, body = req("POST", "/auth/login", {"username": "sysadmin@thingsboard.org", "password": "sysadmin"})
            if code == 200:
                tok = body["token"]
                break
        except OSError:
            pass
        time.sleep(5)
    if not tok:
        sys.exit("TBMQ 로그인 실패")
    if mode == "export":
        _, page = req("GET", "/integrations?pageSize=100&page=0", token=tok)
        pathlib.Path("/experiments/EXP-PIPE/raw/tbmq_exported.json").write_text(json.dumps(page, ensure_ascii=False, indent=1), encoding="utf-8")
        print("내보냄: experiments/EXP-PIPE/raw/tbmq_exported.json → harness/pipebench/tbmq/exported.json 로 복사하면 apply 정본")
        return
    ex = HERE / "exported.json"
    items = json.loads(ex.read_text(encoding="utf-8")).get("data", []) if ex.exists() else [SPEC]
    for it in items:
        it = {k: v for k, v in it.items() if k not in ("id", "createdTime", "tenantId", "status")}
        code, body = req("POST", "/integration", it, tok)
        print("integration", it.get("name"), code, str(body)[:300], flush=True)
        if code not in (200, 201):
            sys.exit("통합 생성 실패")


if __name__ == "__main__":
    main()
