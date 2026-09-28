#!/bin/sh
# RisingWave 배포(deploy-risingwave 컨테이너 = postgres:17.6-alpine 의 psql).
# 규격표 CSV → INSERT, 이어서 규칙 파일을 하나씩 낸다. 파일마다 성공·엔진 오류를 시도 기록(JSONL)에 남기고 계속한다.
#   01 소스 · 02 임계치 · 03 Z-Score (엔진 기능으로 표현) / 04 CEP · 05 ONNX (문서상 미지원 — 실제 오류 확인용 시도)
set -u
D=/repo/candidates/l4-risingwave
A=/experiments/EXP-L4/raw/stage2_${RUN:-manual}_attempts.jsonl
P="psql -h risingwave -p 4566 -U root -d dev -v ON_ERROR_STOP=1"
esc() { tr '\t\r' '  ' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | awk '{printf "%s%s", (NR>1 ? "\\n" : ""), $0}'; }
rec() {  # $1 rule  $2 file  $3 ok(true/false)  $4 출력 파일
  printf '{"engine":"risingwave","rule":"%s","feature":"%s","ok":%s,"error":"%s"}\n' \
    "$1" "$2" "$3" "$(tail -c 1800 "$4" | esc)" >> "$A"
}
i=0; until $P -c 'SELECT 1' >/dev/null 2>&1; do i=$((i+1)); [ $i -gt 90 ] && { echo "RisingWave 응답 없음"; exit 1; }; sleep 2; done
$P -c "CREATE TABLE IF NOT EXISTS tag_limits (tag VARCHAR PRIMARY KEY, unit VARCHAR, lsl DOUBLE PRECISION, usl DOUBLE PRECISION)" || exit 1
awk -F, 'NF>=4 { l=($3=="")?"NULL":$3; u=($4=="")?"NULL":$4; printf "INSERT INTO tag_limits VALUES (%c%s%c, %c%s%c, %s, %s);\n", 39,$1,39, 39,$2,39, l, u }' \
  /repo/flink/sql/tag_limits.csv | $P || exit 1
$P -c "FLUSH"
ok_th=false
for f in 01_sources:소스 02_threshold:L4-01 03_zscore:L4-02 04_cep_attempt:L4-03/04 05_onnx_attempt:L4-12; do
  file=${f%%:*}; rule=${f#*:}
  if $P -f "$D/$file.sql" > /tmp/out 2>&1; then ok=true; else ok=false; fi
  cat /tmp/out; rec "$rule" "$file.sql" "$ok" /tmp/out
  [ "$file" = 02_threshold ] && ok_th=$ok
done
$P -c "SHOW SINKS" -c "SHOW MATERIALIZED VIEWS" -c "SELECT count(*) AS limits FROM tag_limits"
[ "$ok_th" = true ] || { echo "임계치 규칙조차 배포 못 함"; exit 1; }
