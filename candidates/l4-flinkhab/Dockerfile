# Flink HA-B (ZooKeeper HA + 애플리케이션 모드, CANDIDATES §1 [묶음 F] P2). 빌드 컨텍스트: candidates/
# 애플리케이션 클러스터 2개: sql(V1 SQL 01~04 → 잡 1개, StatementSet) · onnx(V1 ONNX 잡). HA 애플리케이션 모드는 클러스터당 잡 1개.
# 타깃: --target sql / --target onnx. BASE 기본값 = 벤치의 Flink 2.2.1 이미지(2.3 판은 BASE=l4bench-flink23:2.3.0, FLINK_VERSION=2.3.0).
ARG BASE=l4bench-flink22:2.2.1
FROM maven:3.9.16-eclipse-temurin-17 AS builder
ARG FLINK_VERSION=2.2.1
WORKDIR /build
COPY l4-flink-sqlrunner/pom.xml sqlrunner/pom.xml
COPY l4-flink-sqlrunner/src sqlrunner/src
COPY l4-flink22-onnx/pom.xml onnx/pom.xml
COPY l4-flink22-onnx/src onnx/src
RUN cd sqlrunner && mvn -q -B -Dflink.version=${FLINK_VERSION} clean package
RUN cd onnx && mvn -q -B -Dflink.version=${FLINK_VERSION} clean package -DskipTests

FROM ${BASE} AS sql
COPY --from=builder /build/sqlrunner/target/sql-runner-1.0.jar /opt/flink/usrlib/sql-runner.jar

FROM ${BASE} AS onnx
COPY --from=builder /build/onnx/target/anomaly-job-1.0.jar /opt/flink/usrlib/anomaly-job.jar
