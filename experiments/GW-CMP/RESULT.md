# GW-CMP — DMZ 게이트웨이: 자체 코드(Python) → Node-RED 교체 시험 (2026-09-30)

근거: 설계검증 결과(docs/research/현업조사_2026-09/19_설계검증_결과.md) "DMZ 게이트웨이 — 시험 후 교체".
도구: `bash tests/e2e/gateway_contract.sh GW-CMP <이름> [URL]` — 같은 요청을 두 구현에 보내 답을 비교한다.

| 단계 | 사례 | Python(자체 코드) | Node-RED(옆에 띄움) | Node-RED(교체 후 본 서비스) |
|---|---|---|---|---|
| 정상 | 토큰·JSON·스키마·허용 목록·설비·파라미터 없음/범위·요청자·승인자·나이·수용·MQTT 5 만료 30 s·중복 (13건) | 13/13 | 13/13 | 13/13 |
| 브로커 정지(docker stop) | 즉시 BROKER_UNAVAILABLE(2 s 안) | 통과 | 통과(0.04 s) | 통과 |
| 브로커 무응답(docker pause) | 발행 확인 2 s 뒤 BROKER_UNAVAILABLE(3 s 안) | **실패: 8 s 안에 답 없음(2회)** | 통과 | 통과 |

판정: Node-RED 가 모든 사례를 통과하고 무응답 사례에서는 자체 코드보다 낫다 → 교체(compose `dmz-gateway`, `3_dmz/gateway-nodered`).
비용: 메모리 39 MiB → 62 MiB(교체 직후 docker stats 1회). 편집기는 끔(`httpAdminRoot: false`) — 흐름은 등록부 생성본만.
남은 차이: 발행 확인을 못 받아 거부한 요청이 브로커가 살아나며 늦게 전달될 수 있다(TCP 버퍼·클라이언트 재전송). 두 구현 공통이며
MQTT 5 만료 30 s·본문 expires_at·OT 수신기의 만료·중복 검사가 막는다. 늦은 전달 여부는 이번 시험에서 재지 않았다(미검증).

원자료: `raw/gw_python_*.json`, `raw/gw_nodered_*.json`(옆에 띄운 것), `raw/gw_nodered_final_*.json`(교체 후).
