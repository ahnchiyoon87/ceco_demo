# EDGE-LOCK — 엣지·게이트웨이 Node-RED 편집기 잠금과 패치 확인 (2026-09-30)

근거: 설계검증 결과 §3 "엣지 Node-RED의 패치와 편집기 잠금이 필요하다(2026 p.23 OT gateway devices … high-value targets)".

| 확인 | 기대 | 결과 |
|---|---|---|
| 판 | 최신 | node-red 5.0.7 = npm latest, node-red-contrib-modbus 5.60.2 = npm latest(09-30 `npm view`) |
| 엣지: 로그인 없이 흐름 읽기 | 401 | 401 |
| 엣지: 모든 권한(scope *) 토큰 요청 | 거부 | invalid_grant |
| 엣지: 읽기 토큰으로 흐름 읽기 | 200(보기는 됨) | 200 |
| 엣지: 읽기 토큰으로 배포(POST /flows) | 거부 | 401, 흐름 파일 크기 그대로(40304 B) |
| 엣지: 노드 설치(POST /nodes) | 거부 | 404(팔레트 설치 꺼짐) |
| DMZ 게이트웨이: 편집기 | 없음 | `httpAdminRoot: false` — /flows·/ 모두 404 |

설정: `2_ot/edge-nodered/settings.js` `permissions: 'read'`, `3_dmz/gateway-nodered/settings.js` `httpAdminRoot: false`.
흐름은 기동마다 등록부 생성본으로 다시 배포된다(start.sh).
