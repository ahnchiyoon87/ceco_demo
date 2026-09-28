# 운영 감시 벤치 ② 준비 (EXP-MON) — 2026-09-29 준비, **미실행**

판정 규칙 `QUESTIONS.md` §1, 후보 `CANDIDATES.md` §8(+개정 #74: Grafana 11.4·Alertmanager 0.28·cAdvisor v0.49.1 강제 교체 확정). E11·F10 은 `STRUCTURE.md`.

## 09-29 결정 반영
1. **자원 한도 없음(I5):** 실제 사용량이 ③ 효율 측정값. 공정성은 같은 호스트에서 벤치 하나씩.
2. **"탐지 잡 0개" 규칙 = V2 개선 후보 프로파일**(`prom315-v2`, `vm-v2`, 규칙 `conf/rules.v2.yml` `DetectorJobsZero`). **기준 `v1` 프로파일은 V1 그대로**(규칙 `prometheus/rules.yml` 만, 플래그·버전 V1) → V1 이 E11 의 탐지기 정지 항목에서 실패하면 그대로 기록.
3. **두 모드:** 단독(`MODE=standalone`, 기본 — 벤치 합성 대상만) · 전체 스택(`MODE=rot` + `compose.rot.yml` — rot-iiot 에 **읽기로만(스크레이프·조회)** 붙어 V1 과 같은 대상). rot 컨테이너는 멈추거나 바꾸지 않는다.

## 설계
- **설정 생성:** `mon_prepare.py` 가 V1 `prometheus/prometheus.yml` 에서 `conf/prometheus.{rot,standalone}.{v1,v2}.yml`·`conf/vm-scrape.{rot,standalone}.yml` 을 만든다. rot 모드 = V1 scrape_configs 그대로 + 벤치 잡 5개, 단독 모드 = prometheus 자신 + 벤치 잡 5개. 실행 때 `config_parity` 가 V1 파일과 잡·대상·경로, 규칙 파일이 V1 과 같은지(`rules_exactly_v1`)를 다시 대조.
- **벤치 합성 대상:** `synthetic-down`(없는 대상 → `PipelineServiceDown` 발화 → Alertmanager → 웹훅 `mon_sink.py` 전달 확인), `victim`(E11 ① 컨테이너 정지), `detector-sim`(E11 ② Flink JobManager 지표 흉내 `flink_jobmanager_numRunningJobs` 4 → 0), `cadvisor-next`·`kafka-next`(수집기 최신판, exporters 프로파일일 때만 up).
- **E11 판정:** ①·② 둘 다 탐지해야 통과. ② 는 V1 규칙에 식이 없어(`FlinkJobRestarting` 은 재시작 횟수만) v1 설정은 150초 안 미탐지가 예상 — 측정으로 확정. rot 모드에서는 실제 rot Flink 의 `numRunningJobs` 도 같은 순간 읽어 기록(V1_FACTS §5 "잡 0개" 재발 여부 관측, 읽기만).
- Alertmanager 설정은 V1 라우팅·억제 그대로, 수신처만 웹훅 추가.

## 후보 → 프로파일

| 후보 | 프로파일 | 이미지 | 규칙 | 모드 | 갭·주의 |
|---|---|---|---|---|---|
| 기준 V1 (Prometheus 3.1.0 + AM 0.28.0) | `v1` | `prom/prometheus:v3.1.0`, `prom/alertmanager:v0.28.0` | V1 그대로 | 단독·rot | 둘 다 강제 교체 대상(기준선 측정용). E11 ② 미탐지 예상 |
| **Prometheus 3.15** + AM 0.34.1 | `prom315` | `prom/prometheus:v3.15.0`, `prom/alertmanager:v0.34.1` | V1 그대로 | 단독·rot | 6주 주기 → 마이너 추종 |
| Prometheus 3.15 + V2 규칙 | `prom315-v2` | 같음 | V1 + `rules.v2.yml` | 단독·rot | V2 개선 후보(E11 ② 해소 확인) |
| Prometheus 3.13 LTS + AM 0.34.1 | `prom313` | `prom/prometheus:v3.13.3`, `prom/alertmanager:v0.34.1` | V1 그대로 | 단독·rot | LTS 2027-07-31 종료 → 다음 LTS 추종 |
| VictoriaMetrics single + vmalert + AM 0.34.1 | `vm` / `vm-v2` | `victoriametrics/victoria-metrics:v1.153.0`, `victoriametrics/vmalert:v1.153.0` | V1 그대로 / + v2 | 단독·rot | 컨테이너 +1(vmalert). 멀티테넌트 vmalert 는 Enterprise(미사용) |
| **Grafana 13.2** (AGPL ⚠) | `grafana13` (prom315 과 함께) | `grafana/grafana:13.2.2` | — | rot 전용 | V1 프로비저닝(데이터소스 2·대시보드 4) 그대로, 패널 질의 전부 `/api/ds/query`. 익명 Viewer 허용(V1 과 같음) — ① 기본 보안 점검 항목. InfluxDB 는 rot 스택 것을 읽음 |
| Grafana 11.4.0 (기준) | `grafana-v1` | `grafana/grafana:11.4.0` | — | rot 전용 | 강제 교체 대상(2025-09-05 종료) |
| cAdvisor v0.60.6 · kafka-exporter v1.10.0 | `exporters` (prom315 과 함께) | `ghcr.io/google/cadvisor:v0.60.6`, `danielqsj/kafka-exporter:v1.10.0` | — | rot 전용 | V1 규칙·대시보드가 쓰는 지표가 나오는지 V1 수집기와 개수 대조. V1 kafka-exporter 는 `latest` digest 고정 → v1.10.0 태그 고정 |
| Thanos · Mimir · Perses · GreptimeDB(PromQL) | — | — | — | — | P3. 장기 보관·대시보드-as-code — ② 기능(수집·규칙·발화)과 겹치지 않아 이번 준비 범위 밖 |

## 실행
```bash
PYTHONUTF8=1 python harness/monbench/mon_prepare.py        # 설정 재생성(V1 prometheus.yml 이 바뀌었을 때)
# 단독 모드(rot 스택 불필요 — 단, 가드는 rot 이 떠 있으면 거부: 무거운 측정 끝난 뒤 또는 FORCE=1)
for p in v1 prom315 prom315-v2 prom313 vm vm-v2; do harness/monbench/stage2.sh $p; done
# 전체 스택 모드(rot-iiot 대상이 떠 있어야 함 → FORCE=1)
for p in v1 prom315 prom315-v2 prom313 vm vm-v2 exporters grafana-v1 grafana13; do MODE=rot FORCE=1 harness/monbench/stage2.sh $p; done
```
산출: `experiments/EXP-MON/stage2_<profile>.<mode>.json`(check·e11·resolve·detector·exporters·grafana), `raw/sink_*.jsonl`, `raw/stats_*.csv`.
④ R09(장시간)은 같은 프로파일을 `KEEP=1` 로 두고 60분 자원 샘플 — ②에는 포함 안 함.

## 준비 검증(2026-09-29)
- 이미지: 외부 이미지 전부 받음(`experiments/BENCH-PREP/pull_20260929_0258.log`, 실패 0).
- `config -q` 통과: 단독(`compose.yml`), 전체 스택(`compose.yml` + `compose.rot.yml`, 외부 네트워크 `rot-iiot` 참조) 둘 다. latest 0. 자원 한도 0.
- `rules_exactly_v1`: v1 설정 파일의 `rule_files` 가 V1 과 같음(생성 시 확인, 실행 때 재대조).
- 미실행: 대상 up·발화·E11·Grafana 패널 결과 모두 미검증.
