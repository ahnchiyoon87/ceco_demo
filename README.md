# ceco_demo — AR-100 반응기 라인 · SCADA + AI 정비 데모

가상 반응 공정 한 줄을 공장(OT)·완충지대(DMZ)·사무(IT) 세 구역으로 나눠 돌리는 학생 수준의 예시 시스템입니다.
고장이 나면 탐지하고, AI가 원인을 분석해 정비 계획을 세웁니다. 담당자가 승인하면 단계별 작업 요청과 가상 정비팀의 수리로 설비가 회복되고, 작업 보고서가 남습니다.
모든 부품은 무료 공개 제품이고(LLM만 OpenAI API) 도커 컴포즈 한 벌로 뜹니다.

```text
가상설비 ─Modbus─ PLC ─Modbus─ 엣지(Node-RED) ─MQTT─ OT 허브 ═브리지═ DMZ 브로커 ─ IT 수집기(Bento) ─ Kafka ─ Flink(탐지)
                                                                                                   │
  AI 업무 도우미(에이전트·판단 엔진·정비 실행기) ← 사건 ← 업무 서비스 ←──────────────────────────────┘
        │ 승인된 작업 요청
        └→ PostgreSQL → Kafka → IT 수집기 → DMZ 게이트웨이(검사 1) → OT 수신기(검사 2) → PLC(검사 3) 또는 가상 정비팀
```

## 먼저 읽을 문서

| 문서 | 내용 |
|---|---|
| [docs/마스터_가이드.html](docs/마스터_가이드.html) (PDF 같은 이름) | 두 가지로 된 문서: 시스템 아키텍처 그림 한 장(층별 구성요소 카드와 번호 붙은 화살표 — 프로토콜·토픽·저장소) + 그 그림을 처음부터 끝까지 지나가는 이야기 「베어링이 닳던 날」(설비 → PLC → 공장 게시판 → DMZ → 사무실 → AI 원인 분석 → 사람 승인 → 세 겹 검사로 설비까지 → 정비팀 수리 → 회복·보고), 순조롭지 않을 때의 갈림길, 데이터 리니지 요약, 알려진 한계 |
| [docs/데모_진행_안내.md](docs/데모_진행_안내.md) | 정비 시나리오 3종 시연 순서·확인할 값·문제 대처 |
| [docs/기록/](docs/기록/) | 인계(`HANDOFF_정비시나리오.md`), 질문과 확정 답(`QA.md`), 결정 기록, 검증 기록 |

## 빠른 시작

```bash
# 1) AI 키: .gitignore 로 제외된 파일에만 둔다(커밋하지 않는다)
echo "OPENAI_API_KEY=..." > 5_ai/server/.env.local

# 2) 기동 — 데모 경로 전체(감시 부품 제외, 약 3 GB). 첫 기동은 빌드·모델 학습으로 약 5분
make up
make ps          # 전부 healthy 인지
make urls        # 접속 주소

# 인프라 감시(Grafana·Prometheus·cAdvisor·exporter·IT InfluxDB)까지 띄우려면
make up-full
```

| 화면 | 주소 | 용도 |
|---|---|---|
| AI 업무 화면 | http://localhost:38180 | 사건 · AI 진행 · 정비 계획 카드 · 승인/반려 · 단계 진행 · 작업 보고서 · 공정 대시보드 |
| 강사 화면 | http://localhost:37080/ (강사 계정) | 이상 발생 버튼 6개 · 전체 초기화 · 현재 진값 |
| FUXA | http://localhost:37018 (관문 계정 → FUXA 계정) | 운전원 화면 · 운전 모드 · 인터록 리셋 |
| Flink | http://localhost:37081 | 탐지 잡 4개 상태 |
| Grafana · Prometheus | http://localhost:37030 · 37090 | `make up-full` 일 때만 |

포트·계정은 `.env` 한 곳에서 바꿉니다. 같은 PC에서 다른 큰 도커 스택과 함께 띄우면 메모리가 모자랄 수 있습니다. 데모는 단독 실행을 권합니다.

## 정비 시나리오

| 명령 | 고장 | AI가 가려야 할 것 |
|---|---|---|
| `make scenario-1` | 냉각수 스트레이너 막힘 → 반응기 온도 상승 | 유량↓·차압↑ → 스트레이너(온라인 전환·세척) |
| `make scenario-1v` | 재킷 스케일 | 유량·차압 정상, 냉각수 온도차 작음 → 정지 후 화학 세정 |
| `make scenario-2` | 교반기 베어링 마모 | 전류가 진동보다 먼저 → 베어링 교체(지금 / 배치 후, 손익 비교) |
| `make scenario-2v` | 축 정렬 불량 | 진동만 큼 → 축 정렬 |
| `make scenario-3` | 압력계 PT-101 드리프트 → 인터록 오트립 | 독립 계기 PT-102 와 불일치 → 비교 교정 + 운전원 리셋 |
| `make scenario-3v` | 배출 밸브 고착(실제 고압) | 두 계기 일치·트립 전 배출 유량↓ → 밸브 정비 |
| `make fault-clear` | 전체 고장 해제 | |

고장은 저절로 낫지 않고, 원인에 맞는 정비만 회복시킵니다. 원인을 틀리면 정비팀이 "부품 정상"으로 답하고 계획이 멈춥니다. 손익 1위라도 규칙(인터록 우회·상한 초과 운전 등)에 걸리면 제외됩니다.
자동 시험: `python tests/e2e/maintenance_scenarios.py s1 s1v s2 s2v s3 s3v s2m [--reject-first 사유]` (실제 LLM 호출, 경우마다 수 분).

탐지 계층만 따로 보는 고장 주입도 있습니다: `make fault-spike`(규격·인터록) · `fault-noise`(Z-Score) · `fault-bearing`(CEP) · `fault-drift`(오토인코더) · `fault-dropout`(결측 보간) · `fault-heater` · `fault-cooling`.

## 그 밖의 명령

| 명령 | 내용 |
|---|---|
| `make regen` | 설비 등록부(`shared/registry/equipment.yaml`)를 바꾼 뒤 태그·흐름·PLC·FUXA·스키마 다시 만들기 |
| `make train` | 오토인코더 다시 학습 후 Flink 잡 다시 제출 |
| `make verify` | 전 계층 자동 검증(감시 부품이 꺼져 있으면 그 항목은 "해당 없음") |
| `make state` | 가상설비 현재 상태 |
| `make down` / `make clean` | 정지(볼륨 보존) / 정지 + 볼륨 삭제 |

## 폴더

| 경로 | 내용 |
|---|---|
| [0_plant/simulator/](0_plant/simulator/) | 가상설비(물리 계산·배속 600) · 강사 화면 · 현장 패널 · 가상 정비팀 |
| [1_control/](1_control/) | OpenPLC 프로그램(운전 모드·인터록·외부 요청 검사) |
| [2_ot/](2_ot/) | 엣지 Node-RED(수집·명령 + OT 수신기) · OT 허브 · FUXA · 화면 관문 |
| [3_dmz/](3_dmz/) | DMZ 브로커 · 원시 사본 InfluxDB · 적재기 · 요청 게이트웨이 |
| [4_it/](4_it/) | Kafka · IT 수집기 · Flink 탐지 · 학습기 · PostgreSQL · Grafana · 이력 적재기 |
| [5_ai/](5_ai/) | AI 백엔드(에이전트·판단 엔진·정비 실행기) · 화면(Vue) · 온톨로지 · 매뉴얼 |
| [shared/](shared/) | 설비 등록부와 생성기 · 구역 라우터 · 브로커·Bento·감시 공용 설정 |
| [tests/](tests/) | 검증 스크립트 · 정비 시나리오 시험 도구 |
| [experiments/](experiments/) | 측정 원출력 · 화면 캡처 |
