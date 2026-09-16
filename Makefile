# ═══════════════════════════════════════════════════════════════════════════
# AR-100 IIoT/SCADA 파이프라인
# ═══════════════════════════════════════════════════════════════════════════
.DEFAULT_GOAL := help
SHELL := /bin/bash
SIM := http://localhost:$(shell grep -E '^PORT_SIM_API=' .env | cut -d= -f2)
CURL := docker run --rm --network iiot curlimages/curl:latest -s

.PHONY: help up lite down clean ps logs urls train regen-edgex regen-fuxa jobs \
        fault-dropout fault-spike fault-noise fault-bearing fault-drift fault-netdown fault-clear \
        state verify

help:  ## 사용 가능한 명령
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up:  ## 전체 스택 기동 (EdgeX 경유)
	docker compose up -d --build
	@echo "기동 중... 최초 실행은 이미지 빌드/모델 학습으로 수 분 걸립니다."
	@$(MAKE) --no-print-directory urls

lite:  ## EdgeX 를 우회해 기동 (시뮬레이터 → EMQX 직결, 경량)
	COMPOSE_PROFILES=lite DIRECT_MQTT_ENABLE=true docker compose up -d --build
	@$(MAKE) --no-print-directory urls

down:  ## 중지 (데이터 보존)
	docker compose --profile edgex --profile lite down

clean:  ## 중지 + 볼륨/데이터 완전 삭제
	docker compose --profile edgex --profile lite down -v --remove-orphans

ps:  ## 서비스 상태
	@docker compose ps --format "table {{.Name}}\t{{.Status}}"

logs:  ## 전체 로그 팔로우 (make logs S=flink-jobmanager 로 개별 지정)
	docker compose logs -f $(S)

urls:  ## 접속 주소
	@echo ""
	@echo "  FUXA (P&ID 관제·제어)  http://localhost:$$(grep -E '^PORT_FUXA=' .env | cut -d= -f2)"
	@echo "  Grafana (트렌드·ML)    http://localhost:$$(grep -E '^PORT_GRAFANA=' .env | cut -d= -f2)"
	@echo "  Flink (잡·체크포인트)  http://localhost:$$(grep -E '^PORT_FLINK_UI=' .env | cut -d= -f2)"
	@echo "  Prometheus (인프라)    http://localhost:$$(grep -E '^PORT_PROMETHEUS=' .env | cut -d= -f2)"
	@echo "  EMQX 대시보드          http://localhost:$$(grep -E '^PORT_EMQX_DASHBOARD=' .env | cut -d= -f2)  (admin/public)"
	@echo "  InfluxDB               http://localhost:$$(grep -E '^PORT_INFLUXDB=' .env | cut -d= -f2)"
	@echo "  EdgeX UI               http://localhost:$$(grep -E '^PORT_EDGEX_UI=' .env | cut -d= -f2)"
	@echo "  시뮬레이터 API         http://localhost:$$(grep -E '^PORT_SIM_API=' .env | cut -d= -f2)/state"
	@echo ""

train:  ## Autoencoder 재학습 (모델 교체)
	docker compose run --rm model-trainer

jobs:  ## Flink 잡 재제출
	docker compose run --rm flink-job-submitter

regen-edgex:  ## plant.yaml 변경 후 EdgeX 프로파일 재생성
	cd edgex && python3 gen_profile.py

regen-fuxa:  ## plant.yaml 변경 후 FUXA 프로젝트 재생성 + 재주입
	cd fuxa && python3 build_project.py
	docker compose run --rm fuxa-provisioner

# ── 고장 주입 (각 시나리오가 특정 탐지 계층을 검증) ──
fault-dropout:  ## TT-101 결측 15초 → Flink 보간 검증
	@$(CURL) -XPOST http://plant-simulator:8080/fault -H 'Content-Type: application/json' -d '{"scenario":"dropout"}'; echo
fault-spike:  ## PT-101 과압 → Tier1 임계치 + 고압 인터록 검증
	@$(CURL) -XPOST http://plant-simulator:8080/fault -H 'Content-Type: application/json' -d '{"scenario":"spike"}'; echo
fault-noise:  ## TT-101 분산 급증 → Tier1 롤링 Z-Score 검증
	@$(CURL) -XPOST http://plant-simulator:8080/fault -H 'Content-Type: application/json' -d '{"scenario":"noise"}'; echo
fault-bearing:  ## 전류↑후 진동↑ → Flink CEP MATCH_RECOGNIZE 검증
	@$(CURL) -XPOST http://plant-simulator:8080/fault -H 'Content-Type: application/json' -d '{"scenario":"bearing_wear"}'; echo
fault-drift:  ## pH/전도도 상관 붕괴 → Autoencoder 만 탐지
	@$(CURL) -XPOST http://plant-simulator:8080/fault -H 'Content-Type: application/json' -d '{"scenario":"drift"}'; echo
fault-clear:  ## 전체 고장 해제
	@$(CURL) -XPOST http://plant-simulator:8080/fault/clear; echo

fault-netdown:  ## EMQX 30초 정지 → EdgeX Store-and-Forward 무손실 검증
	@echo "EMQX 정지 (30초)..."; docker compose pause emqx
	@sleep 30; docker compose unpause emqx
	@echo "복구. app-mqtt-export 로그에서 재전송을 확인하세요:"
	@echo "  docker compose logs edgex-app-mqtt-export | grep -i 'store'"

state:  ## 시뮬레이터 현재 상태
	@$(CURL) http://plant-simulator:8080/state | python3 -m json.tool

verify:  ## 전 계층 자동 검증 실행
	@python3 scripts/verify.py $(S)
