# EXP-112 L4 후보: V1 과 같은 SQL 을 Flink 2.2.1 에서 실행 (V1 flink/Dockerfile 과 같은 구성, 버전만 올림)
FROM flink:2.2.1-scala_2.12-java17
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
# Flink 2.2 용 Kafka SQL 커넥터 (Maven Central, 2026-06 게시)
ARG KAFKA_CONNECTOR=5.0.0-2.2
RUN curl -fsSL -o /opt/flink/lib/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar \
    https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONNECTOR}/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar
RUN mkdir -p /opt/flink/checkpoints && chown -R flink:flink /opt/flink/checkpoints
USER flink
