# ═══════════════════════════════════════════════════════════════
# Flink 2.2.1 + Kafka SQL 커넥터 5.0.0-2.2(2.2.x 호환 최신) + Prometheus 지표 + ONNX 이상탐지 잡(onnx-job)
# 빌드 컨텍스트: ./flink
# ═══════════════════════════════════════════════════════════════
FROM maven:3.9.16-eclipse-temurin-17 AS builder
WORKDIR /build
COPY onnx-job/pom.xml .
RUN mvn -q -B dependency:go-offline
COPY onnx-job/src ./src
RUN mvn -q -B clean package -DskipTests

FROM flink:2.2.1-scala_2.12-java17
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
ARG KAFKA_CONNECTOR=5.0.0-2.2
RUN curl -fsSL -o /opt/flink/lib/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar \
    https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONNECTOR}/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar
ARG FLINK_VER=2.2.1
RUN curl -fsSL -o /opt/flink/lib/flink-metrics-prometheus-${FLINK_VER}.jar \
    https://repo1.maven.org/maven2/org/apache/flink/flink-metrics-prometheus/${FLINK_VER}/flink-metrics-prometheus-${FLINK_VER}.jar
RUN install -d -o flink -g flink /opt/flink/checkpoints /opt/flink/savepoints /opt/models
COPY --chown=flink:flink --from=builder /build/target/anomaly-job-1.0.jar /opt/flink/job/anomaly-job.jar
COPY --chown=flink:flink onnx-job/job.properties /opt/flink/job/job.properties
USER flink
