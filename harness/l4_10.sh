#!/usr/bin/env bash
# L4-10 규칙 변경(코드 없이): 4후보 모두 CEP 창 10→8초로 바꾸고 S04(6초, 여전히 탐지)·S06a(9.5초, 이제 미탐지)·S06b 재생.
#   harness/l4_10.sh <run>   (끝나면 창을 10초로 되돌린다)
set -uo pipefail
run=$1; W=${W:-8}
export COMPOSE_PATH_SEPARATOR=: MSYS_NO_PATHCONV=1 PYTHONUTF8=1
B="docker compose -f harness/l4bench/compose.yml"
T="$B --profile tools run --rm -T tools"
cancel() {  # $1 = JM host, $2 = 잡 이름 일부
  $T python -c "
import json,urllib.request
b='http://$1:8081'
for j in json.load(urllib.request.urlopen(b+'/jobs/overview'))['jobs']:
    if '$2' in j['name'] and j['state']=='RUNNING':
        urllib.request.urlopen(urllib.request.Request(b+'/jobs/'+j['jid']+'?mode=cancel',method='PATCH')); print('cancel',j['name'])
" 2>&1 | grep -v Container
}
setwin() {  # $1 = 창(초)
  for g in generated generated22; do
    sed -i -E "s/WITHIN INTERVAL '[0-9]+' SECOND/WITHIN INTERVAL '$1' SECOND/" harness/l4bench/$g/sql/04_tier1_cep.sql
    grep -o "WITHIN INTERVAL '[0-9]*' SECOND" harness/l4bench/$g/sql/04_tier1_cep.sql
  done
  cancel flink-jobmanager Tier1-CEP; cancel flink22-jobmanager Tier1-CEP; cancel flinkcep-jobmanager EXP111
  sleep 5
  $B --profile tools run --rm -T --entrypoint /bin/bash submit-flinksql -c "cat /opt/flink/sql/01_sources.sql /opt/flink/sql/04_tier1_cep.sql > /tmp/p.sql; /opt/flink/bin/sql-client.sh -f /tmp/p.sql 2>&1 | grep -E 'Job ID|ERROR'" 2>&1 | grep -v Container
  $B --profile flink22 run --rm -T --entrypoint /bin/bash submit-flink22 -c "cat /opt/flink/sql/01_sources.sql /opt/flink/sql/04_tier1_cep.sql > /tmp/p.sql; /opt/flink/bin/sql-client.sh -f /tmp/p.sql 2>&1 | grep -E 'Job ID|ERROR'" 2>&1 | grep -v Container
  PATTERN_WINDOW_S=$1 $B --profile flinkcep run --rm -T -e PATTERN_WINDOW_S=$1 --entrypoint /bin/bash submit-flinkcep -c "/opt/flink/bin/flink run -d -c exp.CepJob /opt/flink/usrlib/cep-job.jar 2>&1 | grep -E 'JobID|ERROR'" 2>&1 | grep -v Container
  PATTERN_WINDOW_S=$1 $B --profile python up -d l4-python 2>&1 | grep -v -E "Running|Waiting|Healthy"
  sleep 20
}
echo "## 창 ${W}초로 변경 (설정만)"; setwin "$W"
echo "$(date +%s) window=$W (SQL 선언·환경변수)" >> experiments/EXP-L4/raw/l4_10_${run}_actions.log
CANDIDATES="flinksql flink22 cep python" harness/run_l4_multi.sh EXP-L4 "$run" --cases S04,S06a,S06b --repeat 5 --seed 1010
echo "## 창 10초로 복구"; setwin 10
