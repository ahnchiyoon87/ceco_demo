#!/usr/bin/env bash
# 운영 감시 ② (EXP-MON). 결과: experiments/EXP-MON/stage2_<profile>.<mode>.json
#   harness/monbench/stage2.sh v1|prom315|prom315-v2|prom313|vm|vm-v2          # MODE=standalone(기본): 벤치 합성 대상만
#   MODE=rot FORCE=1 harness/monbench/stage2.sh <profile>                        # 전체 스택: rot-iiot 에 읽기로 붙어 V1 과 같은 대상
#   MODE=rot FORCE=1 harness/monbench/stage2.sh exporters|grafana-v1|grafana13   # (rot 전용) 수집기 최신판 / V1 대시보드 패널
# 규칙: v1·prom315·prom313·vm = V1 rules.yml 만. *-v2 = + conf/rules.v2.yml(탐지 잡 0개, V2 개선 후보). v1 프로파일은 항상 V1 그대로.
# E11: ① mon-victim 정지 → PipelineServiceDown ② mon-detector 실행 잡 4→0 → DetectorJobsZero(v2 규칙에만 있음).
set -uo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
source harness/benchcommon/guard.sh
p=${1:?profile}
MODE=${MODE:-standalone}
F="-f harness/monbench/compose.yml"
if [ "$MODE" = rot ]; then
  docker network inspect "${ROT_NETWORK:-rot-iiot}" >/dev/null 2>&1 || { echo "rot-iiot 네트워크 없음 — 전체 스택 모드 불가"; exit 7; }
  F="$F -f harness/monbench/compose.rot.yml"
fi
case $p in exporters|grafana-v1|grafana13) [ "$MODE" = rot ] || { echo "$p 는 MODE=rot 전용"; exit 2; } ;; esac
DC="docker compose $F"
RAW=experiments/EXP-MON/raw; mkdir -p "$RAW/detector_www"
[ -n "$(docker ps -q --filter label=com.docker.compose.project=monbench)" ] && { echo "monbench 가 이미 떠 있음"; exit 4; }
rules=v1; cprof=$p
case $p in
  prom315-v2) cprof=prom315; rules=v2 ;;
  vm-v2) cprof=vm; rules=v2; export MON_VM_V2=rules.v2.yml ;;
  v1) rules=v1 ;;                                   # 기준선은 V1 그대로(규칙 추가 금지)
esac
export MON_MODE=$MODE MON_PROM_CFG="prometheus.$MODE.$rules.yml"
case $p in
  exporters) profs="--profile prom315 --profile exporters" ;;
  grafana-v1|grafana13) profs="--profile prom315 --profile $p" ;;
  *) profs="--profile $cprof" ;;
esac
label="$p.$MODE"; export MON_PROFILE=$label
printf '# TYPE flink_jobmanager_numRunningJobs gauge\nflink_jobmanager_numRunningJobs 4\n' > "$RAW/detector_www/metrics"
$DC --profile tools build client >/dev/null || exit 5
rm -f "$RAW/sink_$label.jsonl" "$RAW/${label}_victim_"* "$RAW/${label}_detector_"*
$DC $profs up -d || { $DC $profs logs --no-color > "experiments/EXP-MON/raw/${p}_up_fail.log" 2>&1; $DC $profs logs --tail 60; $DC --profile '*' down -v --remove-orphans >/dev/null 2>&1; exit 6; }   # 실패 시 정리(#116)
$DC $profs images | tail -n +2 | awk '{print $2":"$3" "$4}' > "$RAW/images_$label.txt"
harness/sample_stats.sh "$RAW/stats_$label.csv" 1200 "^monbench-" &
sp=$!
CL="$DC --profile tools run --rm -T client python /repo/harness/monbench/mon_stage2.py"
case $p in
  grafana-v1|grafana13) sleep 30; $CL grafana --profile "$label" | tail -1 ;;
  exporters) sleep 60; $CL exporters --profile "$label" | tail -1 ;;
  *)
    $CL check --profile "$label" | tail -1
    date +%s.%N > "$RAW/${label}_victim_stopped"; docker stop -t 2 monbench-victim-1 >/dev/null
    $CL e11 --profile "$label" | tail -1
    date +%s.%N > "$RAW/${label}_victim_started"; docker start monbench-victim-1 >/dev/null
    $CL resolve --profile "$label" | tail -1
    printf '# TYPE flink_jobmanager_numRunningJobs gauge\nflink_jobmanager_numRunningJobs 0\n' > "$RAW/detector_www/metrics"
    date +%s.%N > "$RAW/${label}_detector_zeroed"
    $CL detector --profile "$label" | tail -1
    printf '# TYPE flink_jobmanager_numRunningJobs gauge\nflink_jobmanager_numRunningJobs 4\n' > "$RAW/detector_www/metrics"
    date +%s.%N > "$RAW/${label}_detector_restored"
    [ "$rules" = v2 ] && $CL detector_resolve --profile "$label" | tail -1 ;;
esac
sleep 5; kill $sp 2>/dev/null
$DC $profs logs --no-color > "$RAW/${label}_services.log" 2>&1
$CL summarize --profile "$label" | tail -1
[ "${KEEP:-0}" = 1 ] || $DC $profs down -v --remove-orphans >/dev/null 2>&1
