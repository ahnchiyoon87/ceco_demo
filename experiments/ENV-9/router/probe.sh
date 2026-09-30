#!/bin/bash
# 연결 시도 표: 기대(OK/BLOCK)와 실제
export MSYS_NO_PATHCONV=1
t(){ # name container url expect
  out=$(docker exec $2 python -c "import urllib.request,sys
try:
  print(urllib.request.urlopen('$3',timeout=3).read().decode().strip())
except Exception as e: print('ERR',type(e).__name__)" 2>&1)
  if [[ "$out" == *-ok ]]; then got=OK; else got=BLOCK; fi
  [[ $got == $4 ]] && v=PASS || v=FAIL
  printf '%-44s expect=%-5s got=%-5s %s  (%s)\n' "$1" "$4" "$got" "$v" "$out"
}
t "ot->dmz 1883 via router alias"   rot-envchk-otapp-1 http://dmz-broker:1883/ OK
t "ot->dmz 9090 via router"         rot-envchk-otapp-1 http://10.231.10.2:9090/ OK
t "ot->dmz 5555 (not allowed)"      rot-envchk-otapp-1 http://10.231.10.2:5555/ BLOCK
t "ot->dmz 8086 (not allowed ot)"   rot-envchk-otapp-1 http://10.231.10.2:8086/ BLOCK
t "ot->dmz direct IP"               rot-envchk-otapp-1 http://10.231.20.10:1883/ BLOCK
t "ot->internet"                    rot-envchk-otapp-1 http://example.com/ BLOCK
t "dmz->ot direct IP"               rot-envchk-dmzsrv-1 http://10.231.10.10:8000/ BLOCK
t "dmz->ot via router dmz ip"       rot-envchk-dmzsrv-1 http://10.231.20.2:8000/ BLOCK
t "dmz->it direct IP"               rot-envchk-dmzsrv-1 http://10.231.30.10:8000/ BLOCK
t "dmz->internet"                   rot-envchk-dmzsrv-1 http://example.com/ BLOCK
t "it->dmz 8086 via router"         rot-envchk-itapp-1 http://10.231.30.2:8086/ OK
t "it->dmz 8088 via router"         rot-envchk-itapp-1 http://10.231.30.2:8088/ OK
t "it->dmz 5555 (not allowed)"      rot-envchk-itapp-1 http://10.231.30.2:5555/ BLOCK
t "it->ot direct IP"                rot-envchk-itapp-1 http://10.231.10.10:8000/ BLOCK
t "it->ot human port on router"     rot-envchk-itapp-1 http://10.231.30.2:8000/ BLOCK
out=$(curl -s -m 3 http://127.0.0.1:39018/ || echo ERR)
[[ $out == ot-ok ]] && echo "host->ot human port 127.0.0.1:39018        expect=OK    got=OK    PASS" || echo "host->ot human port FAIL ($out)"
