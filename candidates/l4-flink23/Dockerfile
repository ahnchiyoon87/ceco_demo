# L4 후보 Flink 2.3.0 (같은 제품 최신, CANDIDATES §1 [묶음 F] P1).
# V1 flink/Dockerfile 과 같은 구성: Kafka SQL 커넥터 + Prometheus 리포터 + ONNX 잡(빌드 스테이지).
# 빌드 컨텍스트: candidates/ (compose 가 지정). 탐지 로직(SQL·ONNX 잡 소스)은 바꾸지 않는다.
#
# 주의(②의 첫 항목): Flink 2.3 호환 Kafka 커넥터 공식 릴리스가 없다(2026-09-29, 05-gate-verification.md).
#   5.0.0-2.2(공식 호환 2.1.x·2.2.x)를 2.3 에 "비공식 조합"으로 올린다. 기동·제출 실패 = ② 탈락 사유로 기록.

# ── 1단계: V1 ONNX 잡(2.x 이식본 candidates/l4-flink22-onnx)·DataStream CEP 잡을 Flink 2.3.0 API 로 다시 컴파일 ──
# (로컬 JDK17+Maven 으로 두 잡 모두 -Dflink.version=2.3.0 컴파일 통과 확인 2026-09-29)
FROM maven:3.9.16-eclipse-temurin-17 AS builder
WORKDIR /build
COPY l4-flink22-onnx/pom.xml onnx/pom.xml
COPY l4-flink22-onnx/src onnx/src
RUN cd onnx && mvn -q -B -Dflink.version=2.3.0 clean package -DskipTests
# Flink 2.3 DataStream CEP 후보(CANDIDATES §1 P2): 기존 candidates/l4-flink-cep 소스를 2.3.0 으로 다시 빌드
COPY l4-flink-cep/pom.xml cep/pom.xml
COPY l4-flink-cep/src cep/src
RUN cd cep && mvn -q -B -Dflink.version=2.3.0 clean package -DskipTests

# ── 2단계: 런타임 ──
FROM flink:2.3.0-scala_2.12-java17
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
ARG KAFKA_CONNECTOR=5.0.0-2.2
RUN curl -fsSL -o /opt/flink/lib/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar \
    https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONNECTOR}/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar
# L4-11 운영 지표: V1 과 같이 Prometheus 리포터를 lib 에 둔다(Maven Central 2.3.0 확인 2026-09-29)
ARG FLINK_VER=2.3.0
RUN curl -fsSL -o /opt/flink/lib/flink-metrics-prometheus-${FLINK_VER}.jar \
    https://repo1.maven.org/maven2/org/apache/flink/flink-metrics-prometheus/${FLINK_VER}/flink-metrics-prometheus-${FLINK_VER}.jar
COPY --from=builder /build/onnx/target/anomaly-job-1.0.jar /opt/flink/usrlib/anomaly-job.jar
COPY --from=builder /build/cep/target/cep-job-1.0.jar /opt/flink/usrlib/cep-job.jar
RUN mkdir -p /opt/flink/checkpoints /opt/flink/savepoints /opt/models \
 && chown -R flink:flink /opt/flink/checkpoints /opt/flink/savepoints /opt/flink/usrlib /opt/models
USER flink
