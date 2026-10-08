# ═══════════════════════════════════════════════════════════════════════════
# AR-100 IIoT/SCADA 새 베이스 (망 3구역: OT · DMZ · IT) — 정본 compose.yml, 설정·계정 .env, 설비 shared/registry/equipment.yaml
# ═══════════════════════════════════════════════════════════════════════════
.DEFAULT_GOAL := help
SHELL := /bin/bash
env = $(shell grep -E '^$(1)=' .env | cut -d= -f2-)
SIM := http://localhost:$(call env,PORT_SIM_API)
AUTH := -u $(call env,INSTRUCTOR_USER):$(call env,INSTRUCTOR_PASSWORD)
FAULT = curl -s $(AUTH) -XPOST $(SIM)/fault -H 'Content-Type: application/json'

.PHONY: help up up-full down clean ps logs urls regen train jobs verify state \
        fault-dropout fault-spike fault-noise fault-bearing fault-drift fault-heater fault-cooling fault-clear \
        scenario-1 scenario-1v scenario-2 scenario-2v scenario-3 scenario-3v

help:  ## 사용 가능한 명령
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up:  ## 기동(감시 부품 제외 — 데모·실습 기본)(직접 만드는 이미지는 빌드, 모델은 학습기가 기동 때 만든다)
	docker compose up -d --build

up-full:  ## 인프라 감시까지 전체 기동(Grafana·Prometheus·감시 도구 포함)
	docker compose --profile monitoring up -d --build

down:  ## 정지(볼륨 보존)
	docker compose down

clean:  ## 정지 + 볼륨 삭제(이력·모델·DB 모두 지움)
	docker compose down -v

ps:  ## 서비스 상태
	@docker compose ps -a --format "table {{.Service}}\t{{.Status}}"

logs:  ## 로그 팔로우 (make logs S=edge 로 개별 지정)
	docker compose logs -f $(S)

urls:  ## 사람용 접속 주소(모두 127.0.0.1)
	@echo ""
	@echo "  OT  FUXA (HMI, 운전원 명령은 로그인)  http://localhost:$(call env,PORT_FUXA)"
	@echo "  OT  현장 패널(가상설비 스위치)          http://localhost:$(call env,PORT_FIELD_PANEL)"
	@echo "  OT  강사 API(고장 주입, 계정)           http://localhost:$(call env,PORT_SIM_API)/state"
	@echo "  OT  엣지 Node-RED 편집(로그인)          http://localhost:$(call env,PORT_EDGE_UI)"
	@echo "  OT  OpenPLC 편집 API                    https://localhost:$(call env,PORT_PLC_API)"
	@echo "  OT  허브 MQTT(viewer, edgex/telemetry)  localhost:$(call env,PORT_OT_MQTT)"
	@echo "  IT  Grafana                             http://localhost:$(call env,PORT_GRAFANA)"
	@echo "  IT  Flink                               http://localhost:$(call env,PORT_FLINK_UI)"
	@echo "  IT  Prometheus                          http://localhost:$(call env,PORT_PROMETHEUS)"
	@echo "  IT  AI 업무 화면                        http://localhost:$(call env,PORT_AI_WEB)"
	@echo ""

regen:  ## 등록부(shared/registry/equipment.yaml)를 바꾼 뒤: 태그·흐름·PLC·FUXA·스키마 다시 만들고 반영
	python3 shared/registry/generate.py
	docker compose up -d --build plc edge dmz-gateway
	docker compose up -d fuxa-provisioner

train:  ## 오토인코더 다시 학습(모델 볼륨 교체) 뒤 Flink 잡 다시 제출
	docker compose run --rm model-trainer
	docker compose run --rm flink-job-submitter

jobs:  ## Flink 잡 상태
	@curl -s http://localhost:$(call env,PORT_FLINK_UI)/jobs/overview | python3 -m json.tool

# ── 고장 주입(강사 도구, 호스트 전용 계정). 각 시나리오가 특정 탐지 계층을 검증 ──
fault-dropout:  ## TT-101 결측 → Flink 보간
	@$(FAULT) -d '{"scenario":"dropout"}'; echo
fault-spike:  ## PT-101 계기 튐 → Tier1 규격 + PLC 고압 인터록
	@$(FAULT) -d '{"scenario":"spike"}'; echo
fault-noise:  ## TT-101 분산 급증 → Tier1 롤링 Z-Score
	@$(FAULT) -d '{"scenario":"noise"}'; echo
fault-bearing:  ## 전류↑ 뒤 진동↑ → Flink CEP
	@$(FAULT) -d '{"scenario":"bearing_wear"}'; echo
fault-drift:  ## pH/전도도 상관 붕괴 → 오토인코더만
	@$(FAULT) -d '{"scenario":"drift"}'; echo
fault-heater:  ## 히터 출력 고착 → TT 상승
	@$(FAULT) -d '{"scenario":"heater_stuck"}'; echo
fault-cooling:  ## 냉각 능력 상실
	@$(FAULT) -d '{"scenario":"cooling_loss"}'; echo
scenario-1:  ## 정비 시나리오 1: 냉각수 스트레이너 막힘(유량↓·차압↑ → 반응기 온도↑)
	@$(FAULT) -d '{"scenario":"strainer_fouling"}'; echo
scenario-1v:  ## 시나리오 1 변형: 재킷 전열면 스케일(유량 정상 · 열이 안 넘어감)
	@$(FAULT) -d '{"scenario":"jacket_fouling"}'; echo
scenario-2:  ## 정비 시나리오 2: 교반기 베어링 마모(전류 먼저 → 진동)
	@$(FAULT) -d '{"scenario":"bearing_wear"}'; echo
scenario-2v:  ## 시나리오 2 변형: 축 정렬 불량(진동만 크게)
	@$(FAULT) -d '{"scenario":"shaft_misalignment"}'; echo
scenario-3:  ## 정비 시나리오 3: PT-101 압력계 드리프트(오지시 → 인터록 오트립)
	@$(FAULT) -d '{"scenario":"pt_drift"}'; echo
scenario-3v:  ## 시나리오 3 변형: 배출 밸브 고착(실제 고압, 두 계기 일치)
	@$(FAULT) -d '{"scenario":"outlet_valve_stick"}'; echo
fault-clear:  ## 전체 고장 해제
	@curl -s $(AUTH) -XPOST $(SIM)/fault/clear; echo

state:  ## 가상설비 현재 상태(강사 API)
	@curl -s $(AUTH) $(SIM)/state | python3 -m json.tool

verify:  ## 전 계층 자동 검증 (make verify S=edge 로 단계 지정)
	@python3 tests/verify.py $(S)
