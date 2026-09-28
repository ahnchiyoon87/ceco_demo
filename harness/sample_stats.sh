#!/usr/bin/env bash
# M5 샘플러: 지정한 컨테이너 이름 패턴의 CPU·메모리를 1초마다 기록한다. 호스트에서 실행.
#   harness/sample_stats.sh <출력.csv> <초> <이름정규식>
out=$1; secs=$2; pat=$3
echo "t_epoch,name,cpu_pct,mem_mib" > "$out"
end=$(( $(date +%s) + secs ))
while [ "$(date +%s)" -lt "$end" ]; do
  now=$(date +%s)
  docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' | grep -E "$pat" | \
    awk -F, -v t="$now" '{cpu=$2; sub(/%/,"",cpu); split($3,m," "); v=m[1]; u=v; gsub(/[0-9.]/,"",u); n=v+0; if(u=="GiB")n*=1024; if(u=="KiB")n/=1024; printf "%s,%s,%s,%.1f\n",t,$1,cpu,n}' >> "$out"
  sleep 1
done
