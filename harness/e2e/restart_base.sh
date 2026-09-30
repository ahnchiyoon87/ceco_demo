#!/bin/bash
# [측정 도구] 새 베이스 재시작 복구(HANDOFF §3-5 '재시작 복구', V1 baseline.sh P3 와 같은 판정).
#   [RREPS=3] [COMPOSE_PROJECT_NAME=rot-base] bash harness/e2e/restart_base.sh <EXP> [시험 이름들]
#   기본 시험: othub dmzb kafka coll flink itinflux dmzinflux pg. 반복은 RREPS(기본 3), 대상 스택은 COMPOSE_PROJECT_NAME
# 한 회: 주입(정지·끊기·재시작) → 대기 → 되돌림 → 끝단 두 곳(DMZ 원시 사본 process_raw, IT 결과 process)에
#        2분 연속 흐름이 돌아온 시각 = 복구(wait_flow.py, V1 과 같은 정의) → 주입 10 s 전부터 지금까지 완전성(유실 태그·초, 중복).
# 사람 손은 쓰지 않는다: 스스로 복구하지 못하면 recover_s = null 로 남기고 다음 회 전에 기록만 한다(수동 조치 없음).
set -u
EXP=$1; shift
. harness/e2e/struct_base.sh
T="${*:-othub dmzb kafka coll flink itinflux dmzinflux pg}"
R=experiments/$EXP/raw; mkdir -p $R
OUT=$R/restart_base.jsonl
LOG=experiments/$EXP/restart_base.log
say(){ echo "[$(date +%T)] $*" | tee -a $LOG; }
ms(){ echo $(( $(date +%s) * 1000 )); }
DMZ_SINK="--influx http://dmz-influx:8086 --bucket-env DMZ_INFLUX_BUCKET --token-env DMZ_INFLUX_TOKEN"
IT_SINK="--influx http://it-influx:8086 --bucket-env IT_INFLUX_BUCKET --token-env IT_INFLUX_TOKEN --measurement process"
flow(){ base_client python harness/e2e/wait_flow.py --t0 $1 $2 2>/dev/null | tail -1; }
complete(){ base_client python harness/e2e/completeness.py --start-ms $1 --end-ms $2 $3 --out /repo/$R/$4.json 2>/dev/null | tail -1; }

rtest(){ # $1 이름 $2 주입 $3 되돌림 $4 대기초
  for k in $(seq 1 ${RREPS:-3}); do
    T0=$(ms); say "$1 #$k 주입: $2"
    sh -c "$2" >>$LOG 2>&1; sleep $4; sh -c "$3" >>$LOG 2>&1
    TF=$(date +%s)
    flow $TF "$DMZ_SINK" > $R/.f_dmz & P1=$!
    flow $TF "$IT_SINK" > $R/.f_it & P2=$!
    wait $P1 $P2
    fd=$(cat $R/.f_dmz); fi=$(cat $R/.f_it)
    say "$1 #$k 복구 DMZ $fd | IT $fi | Flink RUNNING $(jobs_running)"
    T1=$(ms)
    cd_=$(complete $((T0 - 10000)) $T1 "$DMZ_SINK" rs_${1}_${k}_dmz)
    ci_=$(complete $((T0 - 10000)) $T1 "$IT_SINK" rs_${1}_${k}_it)
    echo "{\"test\":\"$1\",\"k\":$k,\"down_s\":$4,\"flow_dmz\":${fd:-null},\"flow_it\":${fi:-null},\"complete_dmz\":${cd_:-null},\"complete_it\":${ci_:-null},\"flink_running\":$(jobs_running)}" >> $OUT
  done
}
has(){ case " $T " in *" $1 "*) return 0;; esac; return 1; }
say "== 재시작 복구 시작 ($T)"
has othub     && rtest othub     "docker stop $C_OTHUB" "docker start $C_OTHUB" 10
has dmzb      && rtest dmzb      "docker stop $C_DMZB" "docker start $C_DMZB" 10
has kafka     && rtest kafka     "docker restart $C_KAFKA" "true" 1
has coll      && rtest coll      "docker network disconnect ${P}_it-net $C_COLL" "docker network connect ${P}_it-net $C_COLL" 10
has flink     && rtest flink     "docker restart $C_JM" "true" 1
has itinflux  && rtest itinflux  "docker stop $C_ITI" "docker start $C_ITI" 30
has dmzinflux && rtest dmzinflux "docker stop $C_DMZI" "docker start $C_DMZI" 30
has pg        && rtest pg        "docker stop $C_PG" "docker start $C_PG" 30
rm -f $R/.f_dmz $R/.f_it
say "== 재시작 복구 끝"
