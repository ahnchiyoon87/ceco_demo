#!/usr/bin/env bash
# stage2 (QUESTIONS §1 ② 기동·기능) 한 후보 실행기. 한 번에 한 후보만 띄운다(메모리 여유가 작아 동시 소비 대신 V1 기록과 대조).
#   harness/l4bench/stage2.sh <profile> [run_id]
#   profile: flinksql(V1 기준 재측정) flink22 flink23 flinkcep flinkcep23 flinkha flinkhab flinkhac flinkhad
#            ekuiper quix kstreams risingwave proton arroyo storm beam streampipes
#   환경변수
#     SEED(기본 1001) REPEAT(10) JITTER(1)   리플레이 조건. 기본값 = EXP-L4 m1(V1 알람 기록이 있는 조건)
#     REF_RUN(기본: 같은 시드의 가장 최근 stage2 flinksql 실행, 없으면 SEED 에 맞는 m1/m2/m3/m4/m5)
#     S13(기본 1)       ONNX 경로가 있는 후보에서 S13 점수 동일성도 잰다
#     R05=1             Flink 후보: 기능 판정 뒤 JobManager kill/start(S09) 로 전체 재시작 복구도 잰다
#     KEEP=1            끝나도 내리지 않는다(디버깅)   FORCE=1  rot-iiot/rot-ai 가 떠 있어도 실행
#     STATS_SECS(기본 400)
# 순서: 메모리 가드 → Kafka(+토픽) → 후보 서비스 기동·건강 대기 → 규칙 배포 → 사전 점검 → 리플레이(replay.py, run_l4_multi 와 같은 인자)
#       → 판정(evaluate.py) → V1 대조(stage2_compare.py) → S13 → experiments/EXP-L4/stage2_<profile>.json 누적 → 내림
# 규칙 시도 기록: 배포 스크립트·앱이 V1 규칙(임계치·Z-Score·CEP·ONNX)을 엔진에 실제로 내 보고 성공·엔진 오류를
#   experiments/EXP-L4/raw/stage2_<run>_attempts.jsonl 에 남긴다 → 결과 JSON 의 attempts. "기능 불가"는 이 실행 기록으로 확정한다.
# 실패도 결과다: 어느 단계에서 멈췄는지 JSON 에 남기고 내린다(② 탈락 근거).
set -uo pipefail
prof=${1:?profile 필요}; run=${2:-s2_${1}_$(date +%m%d%H%M)}
export RUN=$run   # compose 의 ${RUN} → 배포·앱 컨테이너가 시도 기록 파일 이름에 쓴다
cd "$(dirname "$0")/../.." || exit 1
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8
B="docker compose -f harness/l4bench/compose.yml"
EXP=EXP-L4; raw=experiments/$EXP/raw; mkdir -p "$raw"
out=experiments/$EXP/stage2_${prof}.json
log=$raw/stage2_${run}.log
SEED=${SEED:-1001}; REPEAT=${REPEAT:-10}; JITTER=${JITTER:-1}
rargs="--repeat $REPEAT --seed $SEED"; [ "$JITTER" = 1 ] && rargs="$rargs --jitter"
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$log"; }

# ── 0. 메모리 가드: 실험 스택(rot-iiot·rot-ai)과 동시에 돌리지 않는다 ──
busy=$(docker ps --format '{{.Names}} {{.Label "com.docker.compose.project"}}' | awk '$2=="rot-iiot"||$2=="rot-ai"||$1~/^rot-/' | wc -l)
if [ "$busy" -gt 0 ] && [ "${FORCE:-0}" != 1 ]; then
  echo "거부: rot-iiot/rot-ai 컨테이너 ${busy}개 실행 중(메모리 부족 위험). 내린 뒤 다시 실행하거나 FORCE=1"; exit 3
fi

# ── 1. 후보 정의: 기동 서비스 / 배포 방법 / 알람 토픽 접미사 / 통계용 컨테이너 이름 / 잡 수 / ONNX 여부 ──
profile_arg="--profile $prof"; build=0; bsvcs=""; rest=""; jobs=0; onnx=1; deploy=""; vols=""
case "$prof" in
  flinksql)   svcs="flink-jobmanager flink-taskmanager"; profile_arg="--profile tools"; deploy="run submit-flinksql"
              rest=http://flink-jobmanager:8081; jobs=4; pat="l4bench-flink-(job|task)manager" ;;
  flink22)    svcs="flink22-jobmanager flink22-taskmanager"; deploy="run submit-flink22"
              rest=http://flink22-jobmanager:8081; jobs=4; pat="l4bench-flink22-" ;;
  flink23)    svcs="flink23-jobmanager flink23-taskmanager"; deploy="run submit-flink23"; build=1
              rest=http://flink23-jobmanager:8081; jobs=4; pat="l4bench-flink23-" ;;
  flinkcep)   svcs="flinkcep-jobmanager flinkcep-taskmanager"; deploy="run submit-flinkcep"; topic=cep
              rest=http://flinkcep-jobmanager:8081; jobs=4; pat="l4bench-flinkcep-" ;;
  flinkcep23) svcs="flinkcep23-jobmanager flinkcep23-taskmanager"; deploy="run submit-flinkcep23"; topic=cep; build=1
              bsvcs="flinkcep23-jobmanager"; rest=http://flinkcep23-jobmanager:8081; jobs=4; pat="l4bench-flinkcep23-" ;;
  flinkhab)   svcs="zookeeper flinkhab-sql-jobmanager flinkhab-sql-taskmanager flinkhab-onnx-jobmanager flinkhab-onnx-taskmanager"
              build=1; bsvcs="flinkhab-sql-jobmanager flinkhab-onnx-jobmanager"; vols="flinkhab-ckpt"
              rest="http://flinkhab-sql-jobmanager:8081 http://flinkhab-onnx-jobmanager:8081"; jobs=1   # 클러스터마다 잡 1개
              pat="l4bench-(zookeeper|flinkhab-)" ;;
  flinkha)    svcs="zookeeper flinkha-jobmanager flinkha-taskmanager"; deploy="run submit-flinkha"
              rest=http://flinkha-jobmanager:8081; jobs=4; pat="l4bench-(zookeeper|flinkha-)"; vols="flinkha-ckpt" ;;
  flinkhac)   svcs="flinkhac-jobmanager flinkhac-taskmanager"; deploy="run submit-flinkhac"
              rest=http://flinkhac-jobmanager:8081; jobs=4; pat="l4bench-flinkhac-"; vols="flinkhac-ckpt" ;;
  flinkhad)   svcs="flinkhad-jobmanager flinkhad-taskmanager"; deploy="run submit-flinkhad"
              rest=http://flinkhad-jobmanager:8081; jobs=4; pat="l4bench-flinkhad-" ;;
  ekuiper)    svcs="ekuiper"; deploy="run deploy-ekuiper"; onnx=0; pat="l4bench-ekuiper-"; vols="ekuiper-data" ;;
  quix)       svcs="quix"; deploy=""; build=1; pat="l4bench-quix-"; vols="quix-state" ;;   # ONNX 시도 경로 있음 → S13
  kstreams)   svcs="kstreams"; build=1; onnx=0; pat="l4bench-kstreams-"; vols="kstreams-state" ;;
  storm)      svcs="zookeeper storm-nimbus storm-supervisor"; deploy="run submit-storm"; build=1; bsvcs="submit-storm"; onnx=0
              pat="l4bench-(zookeeper|storm-)"; vols="storm-data" ;;
  beam)       svcs="beam"; build=1; onnx=0; pat="l4bench-beam-" ;;
  streampipes) svcs="couchdb nats influxdb backend extensions-all-iiot"; deploy="run deploy-streampipes"; onnx=0
              pat="l4bench-(couchdb|nats|influxdb|backend|extensions)"; vols="sp-backend sp-couchdb sp-influxdb sp-influxdb2" ;;
  risingwave) svcs="risingwave"; deploy="run deploy-risingwave"; onnx=0; pat="l4bench-risingwave-"; vols="risingwave-data" ;;
  proton)     svcs="proton"; deploy="run deploy-proton"; onnx=0; pat="l4bench-proton-"; vols="proton-data" ;;
  arroyo)     svcs="arroyo"; deploy="run deploy-arroyo"; onnx=0; pat="l4bench-arroyo-"; vols="arroyo-data" ;;
  *) echo "모르는 profile: $prof (STAGE2.md 참조)"; exit 2 ;;
esac
topic=${topic:-$prof}
C="$B $profile_arg"
T="$B --profile tools run --rm -T tools"

stage="init"; status="ok"; note=""
finish() {  # 결과 JSON 누적 + 내림
  python - "$out" "$raw" "$run" "$prof" "$stage" "$status" "$note" "$SEED" "$REPEAT" "$JITTER" "${REF_USED:-}" "$pat" <<'EOF'
import json, pathlib, sys, time, csv, statistics as st
out, raw, run, prof, stage, status, note, seed, rep, jit, ref, pat = sys.argv[1:]
raw = pathlib.Path(raw)
rd = lambda n: json.loads((raw / n).read_text(encoding="utf-8")) if (raw / n).exists() else None
entry = {"run": run, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "stopped_at": stage, "status": status, "note": note,
         "replay": {"seed": int(seed), "repeat": int(rep), "jitter": jit == "1"},
         "cases": rd(f"result_{run}.json"), "v1_compare": rd(f"stage2_cmp_{run}.json"), "s13": rd(f"s13_{run}_s13.json")}
att = raw / f"stage2_{run}_attempts.jsonl"
if att.exists():   # 엔진에 실제로 낸 규칙 시도와 엔진 응답(기능 불가 확정 근거)
    rows = [json.loads(l) for l in att.read_text(encoding="utf-8").splitlines() if l.strip()]
    entry["attempts"] = [{k: r.get(k) for k in ("rule", "feature", "ok", "error")} for r in rows]
    by = {}
    for r in rows:
        by.setdefault(r["rule"], []).append(bool(r["ok"]))
    entry["rules_by_execution"] = {k: ("accepted" if any(v) else "rejected") for k, v in by.items()}
if entry["cases"]:
    c = entry["cases"]; entry["cases"] = {k: c[k] for k in ("pass", "fail", "record", "cep_latency_ms")}
r05 = rd(f"result_{run}_r05.json")
if r05:
    jobs = raw / f"{run}_r05_jobs_after.txt"
    entry["r05"] = {"pass": r05["pass"], "fail": r05["fail"], "rows": r05["rows"],
                    "jobs_after": jobs.read_text(encoding="utf-8").strip() if jobs.exists() else None}
st_path = raw / f"stats_{run}.csv"
if st_path.exists():
    tot = {}
    for r in csv.DictReader(open(st_path)):
        m, cp = tot.get(r["t_epoch"], (0.0, 0.0)); tot[r["t_epoch"]] = (m + float(r["mem_mib"]), cp + float(r["cpu_pct"]))
    if tot:
        v = list(tot.values())
        entry["resources"] = {"containers": pat, "n": len(v), "mem_avg_mib": round(st.mean(a for a, _ in v)),
                              "mem_max_mib": round(max(a for a, _ in v)), "cpu_avg_pct": round(st.mean(b for _, b in v), 1),
                              "cpu_max_pct": round(max(b for _, b in v), 1)}
p = pathlib.Path(out)
doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"profile": prof, "runs": []}
doc["runs"].append(entry)
p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(entry, ensure_ascii=False)[:1500])
EOF
  if [ "${KEEP:-0}" != 1 ]; then
    say "내림: $svcs + kafka"
    $C rm -sfv $svcs >>"$log" 2>&1
    $B rm -sfv kafka kafka-init >>"$log" 2>&1
    for v in $vols; do docker volume rm "l4bench_$v" >>"$log" 2>&1; done   # 후보 상태 볼륨(다음 실행이 옛 규칙·체크포인트를 물려받지 않게)
  fi
}
fail(){ status="fail"; note="$*"; say "실패($stage): $*"; $C logs --no-color $svcs > "$raw/stage2_${run}_services.log" 2>&1; finish; exit 1; }   # 실패 원인 확인용 후보 로그(#113)

# ── 2. 기동 (지난 실행이 남긴 후보 상태 볼륨은 먼저 지운다) ──
for v in $vols; do docker volume rm "l4bench_$v" >/dev/null 2>&1; done
stage="build"
if [ "$build" = 1 ]; then b=${bsvcs:-$svcs}; say "빌드: $b"; $C build $b >>"$log" 2>&1 || fail "이미지 빌드 실패(로그 $log)"; fi
stage="kafka"; say "Kafka + 토픽"
$B up -d --wait --wait-timeout 180 kafka >>"$log" 2>&1 || fail "kafka 기동 실패"
$B up kafka-init >>"$log" 2>&1 || fail "토픽 생성 실패"
stage="up"; say "기동: $svcs"
$C up -d --wait --wait-timeout 300 $svcs >>"$log" 2>&1 || { $C logs --tail 80 $svcs >>"$log" 2>&1; fail "서비스 기동·건강 대기 실패"; }

# ── 3. 규칙 배포 ──
stage="deploy"
if [ -n "$deploy" ]; then
  say "배포: $deploy"
  $C ${deploy/run/run --rm -T} 2>&1 | grep -v -E "Container|Running|Waiting|Healthy" | tee -a "$log"
  [ "${PIPESTATUS[0]}" = 0 ] || fail "배포 명령 실패"
fi
sleep 20

# ── 4. 사전 점검 ──
stage="precheck"
if [ -n "$rest" ]; then
  for r in $rest; do   # HA-B 는 클러스터 2개(잡 1개씩). 애플리케이션 모드는 JM 기동 뒤 잡이 스스로 올라오므로 최대 90초 기다린다
    for i in $(seq 1 18); do
      st=$($T python -c "import json,urllib.request;j=json.load(urllib.request.urlopen('$r/jobs/overview'))['jobs'];print(sum(x['state']=='RUNNING' for x in j),sum(x['state'] not in ('CANCELED','FINISHED') for x in j))" 2>/dev/null | tail -1)
      [ "$st" = "$jobs $jobs" ] && break; sleep 5
    done
    say "Flink 잡 상태 $r (RUNNING, 살아 있는 잡) = '$st' / 기대 '$jobs $jobs'"
    [ "$st" = "$jobs $jobs" ] || { $C logs --tail 120 $svcs >>"$log" 2>&1; fail "잡 제출·기동 실패($r): '$st'"; }
  done
else
  n=$(docker ps --filter "label=com.docker.compose.project=l4bench" --format '{{.Names}}' | grep -cE "$pat")
  [ "$n" -ge 1 ] || fail "후보 컨테이너가 떠 있지 않음"
  say "컨테이너 $n개 실행 중(엔진 규칙 상태는 배포 로그 참조)"
fi

# ── 5. 리플레이 (run_l4_multi.sh 와 같은 replay.py·인자) + 자원 표본 ──
stage="replay"
harness/sample_stats.sh "$raw/stats_${run}.csv" "${STATS_SECS:-400}" "$pat" & sp=$!
say "리플레이 $rargs"
$T python /repo/harness/tools/replay.py --exp "$EXP" --run "$run" $rargs 2>&1 | grep -v Container | tail -2 | tee -a "$log"
[ -s "$raw/replay_${run}_emitted.jsonl" ] || { kill $sp 2>/dev/null; fail "리플레이 미실행"; }
sleep 15; kill $sp 2>/dev/null

# ── 6. 판정: 케이스 기대값(manifest) + V1 알람 집합 대조 ──
stage="evaluate"
$T python /repo/harness/tools/evaluate.py --exp "$EXP" --run "$run" --alerts "exp.l4.alerts.$topic" 2>&1 | grep -v Container | tail -1 | tee -a "$log"
[ -s "$raw/result_${run}.json" ] || fail "판정 결과 없음"
cp "$raw/alerts_${run}.jsonl" "$raw/alerts_${run}_${topic}.jsonl"
if [ -z "${REF_RUN:-}" ]; then
  REF_RUN=$(ls -t experiments/$EXP/stage2_flinksql.json >/dev/null 2>&1 && python -c "
import json,sys
d=json.load(open('experiments/$EXP/stage2_flinksql.json',encoding='utf-8'))
ok=[r['run'] for r in d['runs'] if r['status']=='ok' and r['replay']['seed']==$SEED and r['run']!='$run']
print(ok[-1] if ok else '')" 2>/dev/null)
  if [ -z "$REF_RUN" ]; then case "$SEED" in 1001) REF_RUN=m1;; 2002) REF_RUN=m2;; 3003) REF_RUN=m3;; 4004) REF_RUN=m4;; 5005) REF_RUN=m5;; esac; fi
fi
if [ -n "${REF_RUN:-}" ] && [ "$REF_RUN" != "$run" ] && [ -f "$raw/alerts_${REF_RUN}_flinksql.jsonl" ]; then
  REF_USED=$REF_RUN
  python harness/tools/stage2_compare.py --cand-dir "$raw" --cand-run "$run" --cand-alerts "alerts_${run}_${topic}.jsonl" \
    --ref-dir "$raw" --ref-run "$REF_RUN" --ref-alerts "alerts_${REF_RUN}_flinksql.jsonl" --out "$raw/stage2_cmp_${run}.json" \
    | python -c "import json,sys;d=json.load(sys.stdin);print('V1 대조', d['ref']['run'], 'equal', d['equal'], 'only_cand', d['only_cand'], 'only_v1', d['only_ref'])" | tee -a "$log"
else
  say "V1 대조 생략: 같은 시드($SEED)의 V1 기준 알람 없음(REF_RUN='${REF_RUN:-}')"
fi

# ── 7. S13 ONNX 점수 동일성(해당 후보만) ──
stage="s13"
if [ "$onnx" = 1 ] && [ "${S13:-1}" = 1 ]; then
  say "S13 (점수 1e-6·ML 알람·clean 보간)"
  $T python /repo/harness/tools/s13.py --exp "$EXP" --run "${run}_s13" --cands "$topic" 2>&1 | grep -v Container | tail -3 | tee -a "$log"
fi

# ── 8. (선택) R05 전체 재시작: R05=1 이면 S09 패턴 진행 중 JobManager 를 죽였다 살린다(harness/s09.sh 재사용) ──
#    HA-A(flinkha)는 도커 재시작 정책과 ZK 가 잡을 되살리는지, HA-C 는 recover_hac.sh, HA-D 는 재제출로 복구한다.
if [ "${R05:-0}" = 1 ] && [ -n "$rest" ]; then
  stage="r05"
  jm=$(docker ps --format '{{.Names}}' | grep -E "^l4bench-${prof/flinksql/flink}(-sql)?-jobmanager-1$" | head -1)
  rest=${rest%% *}   # 복구 확인은 첫 클러스터(HA-B 는 sql 클러스터)
  say "R05: kill/start $jm (과전류 +${KILL_AT:-3}s kill, +${START_AT:-8}s start, 진동 +6s)"
  FLINK_REST=$rest harness/s09.sh "$EXP" "${run}_r05" "$jm" --repeat 1 2>&1 | tail -3 | tee -a "$log"
  sleep 60
  case "$prof" in
    flinkhac) $C run --rm -T submit-flinkhac recover 2>&1 | grep -v Container | tee -a "$log"; sleep 30 ;;
    flinkhad|flinksql|flink22|flink23|flinkcep|flinkcep23) say "HA 없음: 잡 재제출(V1 운영 절차)"; $C ${deploy/run/run --rm -T} 2>&1 | grep -v Container | tail -5 | tee -a "$log"; sleep 30 ;;
  esac
  $T python -c "import json,urllib.request;print({j['name']:j['state'] for j in json.load(urllib.request.urlopen('$rest/jobs/overview'))['jobs']})" 2>&1 | grep -v Container | tail -1 | tee "$raw/${run}_r05_jobs_after.txt" | tee -a "$log"
  $T python /repo/harness/tools/evaluate.py --exp "$EXP" --run "${run}_r05" --alerts "exp.l4.alerts.$topic" 2>&1 | grep -v Container | tail -1 | tee -a "$log"
fi

stage="done"; finish
