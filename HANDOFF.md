# HANDOFF — ceco_demo (CECO 학회용 데모 산출물)

갱신 2026-09-30 · 작성 Claude Code
**이 문서가 유일한 정본이다.** 실제 파일·실행 상태·사용자 지시가 이 문서와 다르면 실제가 우선이고, 이 문서를 고친다.
조립 전 결정 전문(현업 구조·세부 규칙·스택 선택 이유, 옛 §2-1~§2-3)은 커밋 `2d8ddc8`의 `HANDOFF.md`에 있다. 경위는 `docs/decision-log.md`.

---

## 0. 새 세션이 처음 할 일
1. 실제 상태를 대조한다: `git status`, `docker compose ps -a`(§6과 다르면 실제가 우선이고 이 파일을 고친다).
2. 이 파일을 끝까지 읽는다. 이어서 `docs/QA.md`(사용자 지시 원문과 확정 답)를 읽는다. 같은 질문에는 QA.md의 확정 답을 기준으로 답한다.
3. 시스템 설명은 문서 두 개가 정본이다: `docs/시스템_아키텍처.html`(부품 36·선 49, 그림과 본문 번호 1:1), `docs/쉬운_설명.html`(이야기·비유). 구조를 바꾸면 두 문서를 함께 고친다. 아키텍처 문서는 생성기 `docs/src/arch_gen.py`로 만든다(§8).
4. **이 저장소는 더 개선하지 않는다(사용자 결정 2026-09-30).** 새 요청이 없으면 할 일은 §6 "남은 일"뿐이다.

## 1. 이 저장소는 무엇인가
- **무엇:** 반응 공정 한 줄을 가상으로 돌리고 OT·DMZ·IT 세 구역으로 나눠 계측 → 이상 탐지 → 경보 → AI 대응 → 승인된 작업 요청 → 설비 반영까지 보여 주는 **학생 수준 산출물 예시**. CECO 학회에 올린다.
- **실제 강의:** 새 래퍼로 따로 만든다. 이 저장소는 그 기반이 아니라 데모다.
- **원본과의 관계:** 원본 `D:\work\study\lecture-iiot-scada`(V1)를 폐기하고 이 저장소를 원본 베이스로 삼는다(사용자 결정 2026-09-30). 원본 폴더 삭제는 사용자 확인 대기(§6).
- **IoT-SCADA 층과 AI 층:** 설계검증 2차 결과(`docs/research/현업조사_2026-09/19_설계검증_결과.md`)를 반영한 뒤로 더 고치지 않는다.
- **배포 전제:** PC 한 대의 Docker Compose(Windows, Docker VM 약 7.6 GB). 비용 0원(LLM은 GCP LiteLLM만).

## 2. 구조 요약 (자세한 것은 `docs/시스템_아키텍처.html`)
- **망:** `ot-net`·`dmz-net`(외부 차단)·`it-net`. 세 망에 붙는 것은 라우터 컨테이너 하나(iptables, 허용 경로만 DNAT). 새 연결은 OT→DMZ(브리지 1883, 감시 9090), IT→DMZ(1883·8086·9090·게이트웨이 8088), 호스트→공개 포트만.
- **층(폴더 = 층, 이름 = 역할-제품):** `0_plant`(가상설비) · `1_control`(OpenPLC) · `2_ot`(엣지 Node-RED·OT 허브 Mosquitto·FUXA·화면 관문 Caddy) · `3_dmz`(DMZ 브로커·적재기 Bento·원시 사본 InfluxDB·요청 게이트웨이 Node-RED) · `4_it`(Kafka·IT 수집기 Bento·Flink·학습기·PostgreSQL·Grafana) · `5_ai`(AI 업무 도우미·화면·온톨로지·매뉴얼) · `shared`(등록부·라우터·감시·공용 설정).
- **설비 등록부가 정본:** `shared/registry/equipment.yaml` → `python shared/registry/generate.py`가 태그·토픽·허용 목록·요청 스키마·PLC 프로그램·엣지와 게이트웨이 흐름·FUXA 화면·온톨로지 씨앗·Bloblang 지도를 만든다(`--check`로 정본과 같은지 확인).
- **작업 요청 길(검사 세 겹):** 요청자(AI `ai-ops`·종류 ai, MES 흉내 `mes-01`·종류 mes) → PostgreSQL 기록·승인 → Kafka `request.approved` → IT 수집기 발송 스트림 → DMZ 게이트웨이(검사 1) → DMZ 브로커(MQTT 5 만료 30 s) → OT 허브 브리지 in → OT 수신기(검사 2, 모드·정비·운전원 대기 60 s) → PLC(검사 3, 인터록·범위·만료) → 응답 ⓐⓑⓒ → 업무 서비스의 시간 판정(ACK 5 s·재관측 10 s).
- **경보 길:** Flink → `sensor.alerts` → IT 수집기 → Alertmanager(설비·규칙으로 묶기, 정비·정지·설비 꺼짐 억제 = ISA-18.2) → webhook → PostgreSQL `alert` 기록 + `alerts.display` → DMZ → OT 허브 → FUXA "분석 경고(참고)". 같은 `sensor.alerts`를 업무 서비스가 AI 사건으로 접수.
- **2026-09-30 설계검증 반영(사용자 "리서치대로 하셈 … 그냥 시킨대로"):** 업무 서비스의 묶기·억제 → Alertmanager(#180), FUXA 손님 읽기 → Caddy 관문(#181), 수집기 입력 멈춤 경보(#182), DMZ 게이트웨이 자체 코드 → Node-RED(#183, 계약 시험 15건), IT 발송기 자체 코드 → Kafka 승인 토픽 + Bento http(#184), 요청자 종류 필드와 MES 흉내 요청자(#185), 엣지 편집기 읽기 전용·게이트웨이 편집기 없음(#186), 리서치 문서 오류 4곳 정정(#187). 역할 변경·폴더 층 구조·정리는 #179, 문서 두 개는 #188.

## 3. 기준
- **관문:** 비용 0원(LLM API만 예외). 금지 라이선스: BSL, SSPL, TSL, RCL, 체험판, 키로 여는 기능. 계속 유지되는 제품 계열만. `latest` 태그 금지, 버전 고정.
- **품질("됐다"의 조건):** ① 명령 한 번으로 모두 healthy(사람 손 0) ② 재시작 반복·설명 못 하는 오류 로그 0 ③ 주요 부품 재시작 뒤 스스로 복구 ④ 쓰지 않는 서비스·파일 0, 설정 정본 한 곳 ⑤ 새 폴더·빈 볼륨·다른 프로젝트 이름으로 `--build` 기동해도 같다.
- **판정:** 정확도·유실·중복은 V1보다 조금도 나쁘면 안 된다. 지연 p95·복구 시간은 +5 % 이내면 같다(3회 중앙값). 결과는 검증됨/실패/미검증/해당 없음으로 나눈다.

## 4. 작업 방식
1. 사용자에게는 한국어로 답한다. 질문에는 먼저 쉬운 자연어로 답하고, 번호 붙은 짧은 중간 보고 뒤 멈추지 않고 계속한다.
2. 사실만 쓴다. 재지 않은 수치는 쓰지 않는다. 확인 못 한 것은 "미확인"과 확인 방법으로 적는다.
3. 근본 수정만 한다. 수동 재시작·sleep 으로 순서 맞추기·검사 건너뛰기·실패를 통과로 세기는 금지. 막히면 멈추고 보고한다.
4. 엔진급 기능(스트림 처리·메시징·저장·탐지·경보 묶기)을 직접 짠 코드로 대체하지 않는다. 기성 제품으로 되는 것은 제품으로 한다.
5. 측정은 한 번에 하나씩(두 측정이 겹치면 고장 주입이 섞여 무효). 측정 도구는 `tests/e2e/`.
6. 실행 판단은 `docs/decision-log.md`에 추가한다(추가만). 확정된 사용자 답은 `docs/QA.md`에.

## 5. 기준값 — 다시 재지 않는다
**V1 기준값**(배속 600; 요약 `experiments/EXP-001/summary_V1_r2_.json`, 고장→알람 `experiments/EXP-000/raw/onset_v2sim_600*.json`, 탐지 `experiments/EXP-L4`, 기록 `experiments/REC-V1/`)
| 항목 | V1 값 |
|---|---|
| 자원 | 메모리 합계 5,918 MiB(29개) · CPU 51.2 % |
| 알람→화면 p95 | Kafka 1.67 s · FUXA 태그 1.84 s · 최근알람 1.98 s · AI 사건 2.06 s |
| 화면값 = 이력값 | 99.17 % |
| 수집기 단절 10 s | 복구 중앙 7.3 s · 유실 중앙 120 태그·초 |
| Kafka 재시작 | 복구 중앙 11.6 s · 유실 0 · 중복 중앙 150 |
| 탐지기 재시작 | 잡 소멸 · 알람 11~12 유실(HA 꺼짐) |
| 고장→알람 최대 | 스파이크 1.9 · 히터 5.9 · 베어링 8.1 · 결측 5.8 · 드리프트 2.8 s, 잡음(Z-Score) 확률적 약 10.8 s |
| 탐지 정확도 | 판정 70/70 · 기준 알람 263건 |

새 베이스 검증 전체는 `docs/BASE_VERIFY.md`, 결함과 교훈은 `docs/STABILITY.md`, 기능 대응(V1 → 새 베이스)은 `docs/FUNCTION_MAP.md`.

## 6. 지금 상태
{{STATE}}

## 7. 넘으면 안 되는 선
- 원본 `D:\work\study\lecture-iiot-scada`는 수정하지 않는다(삭제는 사용자 확인 뒤). 원본 이름(`iiot*`·`ar100*`)의 컨테이너·볼륨·이미지를 만들거나 덮어쓰지 않는다(이 저장소 이름 `ceco-*`).
- git push 금지. `latest` 태그 금지. §3 금지 라이선스.
- `5_ai/server/.env.local`의 키는 출력하거나 커밋하지 않는다. LiteLLM 마스터 키도 출력하지 않는다. LLM 호출은 필요한 만큼만(크레딧).
- `iiot*`·`capstone-*` 자원은 건드리지 않는다.

## 8. 명령
- 기동: `docker compose up -d --build`(프로젝트 `ceco-demo`, `.env`). 첫 기동은 약 5분(학습기·그래프 채우기 포함).
- 전체 검증: `PYTHONUTF8=1 python tests/verify.py`(호스트에서, 공개 포트·`docker exec`만).
- 측정 도구(사용법은 각 파일 머리말): `tests/e2e/control_base.sh`(제어·안전 S14~S22), `control_ai.sh`(AI 쪽), `gateway_contract.sh`(게이트웨이 계약), `dispatch_check.py`(발송·MES), `e1_base.sh`(알람→화면), `fault_onset_base.py`(고장→알람), `isolation_base.sh`(격리), `restart_base.sh`(재시작 복구), `coll_stall.sh`(수집기 멈춤). 모두 `tests/e2e/struct_base.sh`의 `base_client`(세 망에 붙는 일회용 측정 컨테이너 `e2e-client:1.2`)로 돈다.
- 등록부: `python shared/registry/generate.py`(`--check`).
- MES 흉내 지시(IT 망 안에서): `docker compose exec it-collector wget -qO- --header 'Content-Type: application/json' --post-data '{"work_master_id":"WM-R101-TEMPSP","equipment_id":"R-101","job_order_parameters":[{"id":"temp_sp_c","value":72}],"planner":"planner-01","summary":"배치 온도 지시"}' http://127.0.0.1:4195/mes_requester/orders`
- 아키텍처 문서 다시 만들기: `PYTHONUTF8=1 python docs/src/arch_gen.py docs/시스템_아키텍처.html docs/src/arch_tpl.html`. 부품·선·설명을 생성기 한 곳에서 정의하므로 그림과 본문 번호가 어긋나지 않는다. 구조를 바꾸면 생성기를 고치고 다시 만든다.
- 환경: 호스트 RAM 15.7 GB, Docker VM 7.6 GB. 긴 작업은 Git Bash. 컨테이너 경로 인자 앞에 `MSYS_NO_PATHCONV=1`. Python은 `PYTHONUTF8=1`.

## 9. 자산 지도
| 위치 | 역할 |
|---|---|
| `HANDOFF.md` | 유일한 정본 |
| `docs/시스템_아키텍처.html` · `docs/쉬운_설명.html` | 시스템 설명 문서 두 개(남에게 설명할 때 쓰는 것). 아키텍처 문서의 생성기는 `docs/src/` |
| `docs/QA.md` | 사용자 지시 원문과 질문·확정 답 |
| `docs/decision-log.md` | 실행·판정·경위(추가만) |
| `docs/BASE_VERIFY.md` · `docs/STABILITY.md` · `docs/FUNCTION_MAP.md` | 검증 결과 · 결함과 교훈 · V1 기능 대응표 |
| `docs/사용자발화_2026-09-29.md` | 09-29 세션 사용자 발화 원문 |
| `docs/research/현업조사_2026-09/` | 조사 의뢰서와 결과 12~19(19 = 설계검증 2차 정정판) |
| `experiments/` | 증거 원본(`GW-CMP` 게이트웨이, `DISP-CMP` 발송, `EDGE-LOCK` 편집기 잠금, `BASE-FINAL` 최종 회귀 등) |
| `tests/` | 측정 도구(솔루션 부품 아님) |
