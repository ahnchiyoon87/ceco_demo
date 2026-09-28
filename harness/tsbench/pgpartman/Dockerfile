# PostgreSQL 18.6 + pg_partman(PGDG apt, PostgreSQL License). 공식 이미지에 PGDG 저장소가 이미 있다.
# 설치된 pg_partman 버전은 ts_stage2 가 SELECT extversion 으로 결과에 남긴다(CANDIDATES 기준 5.5.0).
FROM postgres:18.6-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-18-partman && rm -rf /var/lib/apt/lists/*
