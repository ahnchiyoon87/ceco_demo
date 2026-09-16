# ═══════════════════════════════════════════════════════════════
# Flink 1.20 + Kafka SQL 커넥터 + ONNX 이상탐지 잡
#
# 빌드 컨텍스트: ./flink
# Maven 빌더 스테이지가 포함되어 있어 사용자는 `docker compose up` 한 번이면
# 됩니다. 두 번째 빌드부터는 레이어 캐시로 즉시 완료됩니다.
# ═══════════════════════════════════════════════════════════════

# ── 1단계: ONNX 이상탐지 잡 빌드 ──
FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /build
COPY onnx-job/pom.xml .
# 의존성만 먼저 받아 레이어 캐시를 극대화
RUN mvn -q -B dependency:go-offline
COPY onnx-job/src ./src
RUN mvn -q -B clean package -DskipTests

# ── 2단계: 런타임 ──
FROM flink:1.20.1-scala_2.12-java17

USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Flink SQL 용 Kafka 커넥터 (Tier-1 규칙/CEP 가 사용)
ARG KAFKA_CONNECTOR=3.3.0-1.20
RUN curl -fsSL -o /opt/flink/lib/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar \
    https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONNECTOR}/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar

# Prometheus 메트릭 리포터.
# Flink 1.20 도커 이미지의 opt/ 에는 메트릭 리포터가 포함되지 않으므로
# Maven Central 에서 직접 받는다.
ARG FLINK_VER=1.20.1
RUN curl -fsSL -o /opt/flink/lib/flink-metrics-prometheus-${FLINK_VER}.jar \
    https://repo1.maven.org/maven2/org/apache/flink/flink-metrics-prometheus/${FLINK_VER}/flink-metrics-prometheus-${FLINK_VER}.jar

# ONNX 이상탐지 잡
COPY --from=builder /build/target/anomaly-job-1.0.jar /opt/flink/job/anomaly-job.jar
COPY onnx-job/job.properties /opt/flink/job/job.properties

RUN mkdir -p /opt/flink/checkpoints /opt/flink/savepoints /opt/models \
 && chown -R flink:flink /opt/flink/checkpoints /opt/flink/savepoints /opt/flink/job /opt/models
USER flink
