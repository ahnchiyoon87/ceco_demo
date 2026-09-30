#!/bin/sh
# 서비스별 계정과 AI 층 DATABASE. 비밀번호는 환경변수(.env)에서만 받는다.
#   ops        업무 서비스(alert 상태·타이머 판정·요청 이벤트·감사 추가)
#   dispatcher IT 발송(IT 수집기 발송 스트림: 보낼 요청 읽기, 발송 이벤트·감사 추가)
#   mes        MES 흉내 요청자(IT 수집기 스트림: 생산 지시를 요청·승인으로 추가)
#   ai_app     AI 업무 도우미(DATABASE ai 소유, 승인한 요청과 감사 추가)
#   reader     조회 전용(Grafana·보고서·시험 도구)
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE ops LOGIN PASSWORD '${PG_OPS_PASSWORD}';
CREATE ROLE dispatcher LOGIN PASSWORD '${PG_DISPATCHER_PASSWORD}';
CREATE ROLE mes LOGIN PASSWORD '${PG_MES_PASSWORD}';
CREATE ROLE ai_app LOGIN PASSWORD '${PG_AI_PASSWORD}';
CREATE ROLE reader LOGIN PASSWORD '${PG_READER_PASSWORD}';
CREATE DATABASE ai OWNER ai_app;
REVOKE ALL ON DATABASE ai FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
