#!/usr/bin/env bash
# HA-C (CANDIDATES §1 "보존 체크포인트 + 재기동 스크립트"): HA 없는 Flink 세션에서 잡을 보존 체크포인트로 재제출한다.
# 이 스크립트는 연결 로직(QUESTIONS §1 허용 범위)이다 — 상태 복원 자체는 Flink 의 execution.state-recovery.path 가 한다.
# submit-flinkhac 컨테이너 안에서 실행한다(/opt/flink/checkpoints 는 JM·TM 과 공유하는 볼륨).
#   recover_hac.sh submit    처음 제출(01+02, 01+03, 01+04 SQL 잡 3개 + ONNX 잡) 후 잡 이름→jid 기록
#   recover_hac.sh recover   기록된 jid 별 최신 chk-*/_metadata 에서 같은 잡을 다시 제출하고 기록 갱신
set -uo pipefail
mode=${1:-submit}
JM=${JM_REST:-http://flinkhac-jobmanager:8081}
CK=/opt/flink/checkpoints
MAP=$CK/hac_jobs.txt          # "<키> <jid>" 줄. 키 = 02_tier1_rules | 03_tier1_zscore | 04_tier1_cep | onnx
SQL=/opt/flink/sql
JAR=/opt/flink/extlib/anomaly-job.jar; [ -f /opt/flink/usrlib/anomaly-job.jar ] && JAR=/opt/flink/usrlib/anomaly-job.jar
PROPS=/opt/flink/job/job.properties

key_of() {  # 잡 이름 → 키
  case "$1" in
    *Threshold*) echo 02_tier1_rules;; *ZScore*) echo 03_tier1_zscore;; *CEP*) echo 04_tier1_cep;; *) echo onnx;;
  esac
}

record_map() {  # REST 에서 RUNNING 잡의 jid·이름을 읽어 기록
  sleep 5
  curl -sf "$JM/jobs/overview" | grep -o '"jid":"[0-9a-f]*","name":"[^"]*"[^}]*"state":"RUNNING"' |
    sed -E 's/"jid":"([0-9a-f]+)","name":"([^"]*)".*/\1 \2/' | while read -r jid name; do
      echo "$(key_of "$name") $jid"
    done > "$MAP.new"
  mv "$MAP.new" "$MAP"; echo "== 잡 기록"; cat "$MAP"
}

submit_sql() {  # $1 = 키, $2 = 복구 경로(없으면 빈 값)
  { cat "$SQL/01_sources.sql"
    [ -n "$2" ] && echo "SET 'execution.state-recovery.path' = '$2';"
    cat "$SQL/$1.sql"; } > /tmp/p.sql
  /opt/flink/bin/sql-client.sh -f /tmp/p.sql 2>&1 | sed -E 's/\x1b\[[0-9;]*m//g' | grep -E "Job ID|ERROR|Exception" | head -5
}

submit_onnx() {  # $1 = 복구 경로(없으면 빈 값)
  if [ -n "$1" ]; then s="-s $1"; else s=""; fi
  /opt/flink/bin/flink run -d $s -c org.uengine.iiot.AnomalyJob "$JAR" "$PROPS" 2>&1 | grep -E "JobID|ERROR|Exception" | head -5
}

latest_chk() {  # $1 = jid → 가장 큰 번호의 완료 체크포인트 디렉터리
  ls -d "$CK/$1"/chk-*/ 2>/dev/null | while read -r d; do [ -f "$d/_metadata" ] && echo "${d%/}"; done |
    sort -t- -k2 -n | tail -1
}

case "$mode" in
  submit)
    for k in 02_tier1_rules 03_tier1_zscore 04_tier1_cep; do echo "== $k"; submit_sql "$k" ""; done
    echo "== onnx"; submit_onnx ""
    record_map ;;
  recover)
    [ -s "$MAP" ] || { echo "잡 기록 없음($MAP) — 복구 불가"; exit 1; }
    while read -r k jid; do
      p=$(latest_chk "$jid")
      echo "== $k (옛 jid $jid) 복구 경로: ${p:-없음 → 빈 상태로 재제출}"
      if [ "$k" = onnx ]; then submit_onnx "$p"; else submit_sql "$k" "$p"; fi
    done < "$MAP"
    record_map ;;
  *) echo "사용법: $0 submit|recover"; exit 2;;
esac
