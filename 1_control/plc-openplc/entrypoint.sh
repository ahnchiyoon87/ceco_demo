#!/bin/bash
# OpenPLC 런타임을 띄운다. 프로그램은 이미지 빌드 때 설치돼 있어 런타임이 스스로 RUN 한다.
# 첫 계정은 런타임 규칙상 누구나 만들 수 있으므로 기동 때 바로 만든다(PLC_ADMIN_USER / PLC_ADMIN_PASSWORD, 편집기 접속용).
# 설치된 프로그램이 이미지의 묶음과 다를 때만(예: 편집기로 다른 프로그램을 올린 뒤) 이미지의 묶음을 다시 올린다.
set -uo pipefail
cd /workdir
bash ./start_openplc.sh &
RT=$!
API=https://127.0.0.1:8443/api
MARK=build/.ar100_program.sha256
WANT=$(cat /opt/ar100/program.sha256)
log(){ echo "[ar100-loader] $*"; }

for _ in $(seq 1 180); do
  curl -skf -o /dev/null "$API/version" && break
  kill -0 $RT 2>/dev/null || { log "런타임 프로세스 종료"; exit 1; }
  sleep 1
done

body=$(printf '{"username":"%s","password":"%s","role":"admin"}' "$PLC_ADMIN_USER" "$PLC_ADMIN_PASSWORD")
curl -sk -o /dev/null -X POST "$API/create-user" -H 'Content-Type: application/json' -d "$body"
if [ "$(cat $MARK 2>/dev/null)" = "$WANT" ] && ls build/libplc_*.so >/dev/null 2>&1; then
  log "프로그램 ${WANT:0:12} 설치됨"
else
  TOKEN=$(curl -sk -X POST "$API/login" -H 'Content-Type: application/json' -d "$body" \
          | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))')
  [ -n "$TOKEN" ] || { log "로그인 실패"; kill $RT; exit 1; }
  AUTH="Authorization: Bearer $TOKEN"
  log "프로그램 ${WANT:0:12} 올리기"
  curl -sk -X POST -H "$AUTH" -F "file=@/opt/ar100/program.zip" "$API/upload-file"; echo
  status=""
  for _ in $(seq 1 300); do
    status=$(curl -sk -H "$AUTH" "$API/compilation-status" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("status",""))')
    [ "$status" = "SUCCESS" ] || [ "$status" = "FAILED" ] && break
    sleep 1
  done
  if [ "$status" != "SUCCESS" ]; then
    log "컴파일 실패($status)"; curl -sk -H "$AUTH" "$API/compilation-status" | tail -c 2000; kill $RT; exit 1
  fi
  echo "$WANT" > "$MARK"
  curl -sk -o /dev/null -H "$AUTH" "$API/start-plc"
  log "적재·RUN 완료"
fi
wait $RT
