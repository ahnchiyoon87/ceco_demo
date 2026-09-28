# 벤치 공통 측정 클라이언트(측정 도구 — 솔루션 부품 아님). 모든 벤치가 같은 이미지·같은 라이브러리 버전을 쓴다.
# 버전은 2026-09-29 PyPI 확인값. apache-iggy 는 manylinux_2_34 휠 → bookworm(glibc 2.36) 기반 필요.
FROM python:3.12.8-slim
RUN pip install --no-cache-dir \
      confluent-kafka==2.15.1 nats-py==2.16.0 pulsar-client==3.13.0 rstream==1.1.0 \
      apache-iggy==0.9.0 rocketmq-python-client==5.1.2 paho-mqtt==2.1.0 \
      psycopg[binary]==3.3.6 clickhouse-connect==1.9.0 apache-iotdb==2.0.11 \
      requests==2.34.2 pyyaml==6.0.3
WORKDIR /repo
