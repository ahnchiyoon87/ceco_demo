"""[측정 도구 — 솔루션 부품 아님] 복구 판정: 텔레메트리가 끝단(InfluxDB process_raw)에 '2분 연속' 흐를 때 복구로 본다.

잠깐 흘렀다 멈추는 경우(#97: Kafka 재시작 뒤 중계기가 버퍼만 흘리고 정지)를 복구로 오판하지 않기 위해
흐름이 처음 다시 보인 시각부터 --sustain-s 동안 끊김(최근 --window-s 초에 TT-101 0건)이 없어야 한다.
끊기면 시작 시각을 버리고 다시 센다. --timeout-s 안에 연속 흐름이 없으면 recover_s = null(스스로 복구 안 됨).
  docker run --rm --network ceco-demo_it-net --env-file .env e2e-client:1.2 python tests/e2e/wait_flow.py --t0 <epoch_s>
출력(stdout 한 줄 JSON): {"recover_s": 복구까지 초 또는 null, "flaps": 흐름 재개 후 다시 끊긴 횟수, "waited_s": 총 대기}
"""
import argparse, json, os, time, urllib.parse, urllib.request


SINK = {"url": "http://influxdb:8086", "bucket_env": "INFLUX_BUCKET", "token_env": "INFLUX_TOKEN", "measurement": "process_raw"}


def flowing(window_s):
    q = (f'from(bucket:"{os.environ[SINK["bucket_env"]]}") |> range(start:-{window_s}s) '
         f'|> filter(fn:(r)=>r._measurement=="{SINK["measurement"]}" and r.tag=="TT-101") |> count()')
    req = urllib.request.Request(SINK["url"] + "/api/v2/query?" + urllib.parse.urlencode({"org": os.environ["INFLUX_ORG"]}),
                                 json.dumps({"query": q, "type": "flux"}).encode(),
                                 {"Authorization": "Token " + os.environ[SINK["token_env"]], "Content-Type": "application/json", "Accept": "application/csv"})
    try:
        return ",_value" in urllib.request.urlopen(req, timeout=5).read().decode()
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--t0", type=float, required=True, help="복구 시간 기준 시각(epoch 초, 복구 조치 시각)")
    ap.add_argument("--sustain-s", type=int, default=120)
    ap.add_argument("--window-s", type=int, default=5)
    ap.add_argument("--timeout-s", type=int, default=420)
    # 새 베이스 끝단: DMZ 원시 사본 = --influx http://dmz-influx:8086 --bucket-env DMZ_INFLUX_BUCKET --token-env DMZ_INFLUX_TOKEN
    #               IT 결과 = --influx http://it-influx:8086 --bucket-env IT_INFLUX_BUCKET --token-env IT_INFLUX_TOKEN --measurement process
    ap.add_argument("--influx", default=SINK["url"]); ap.add_argument("--bucket-env", default=SINK["bucket_env"])
    ap.add_argument("--token-env", default=SINK["token_env"]); ap.add_argument("--measurement", default=SINK["measurement"])
    a = ap.parse_args()
    SINK.update(url=a.influx, bucket_env=a.bucket_env, token_env=a.token_env, measurement=a.measurement)
    start, flaps = None, 0
    while True:
        now = time.time()
        if flowing(a.window_s):
            if start is None:
                start = now
            elif now - start >= a.sustain_s:
                print(json.dumps({"recover_s": round(start - a.t0, 1), "flaps": flaps, "waited_s": round(now - a.t0, 1)}))
                return
        elif start is not None:
            start, flaps = None, flaps + 1
        if now - a.t0 > a.timeout_s + a.sustain_s or (start is None and now - a.t0 > a.timeout_s):
            print(json.dumps({"recover_s": None, "flaps": flaps, "waited_s": round(now - a.t0, 1)}))
            return
        time.sleep(2)


if __name__ == "__main__":
    main()
