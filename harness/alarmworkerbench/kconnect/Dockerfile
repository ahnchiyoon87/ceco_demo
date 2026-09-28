# 알람 워커 후보: Kafka Connect(apache/kafka 4.3.1 동봉) + Aiven JDBC sink v6.12.0(Apache-2.0).
# Confluent JDBC 커넥터는 Confluent Community License(비 OSI) → ① 관문 제외. Aiven 판은 v6.12.0 바이너리 자산이 없어 소스 태그에서 빌드.
FROM eclipse-temurin:21.0.8_9-jdk AS build
ADD https://github.com/Aiven-Open/jdbc-connector-for-apache-kafka/archive/refs/tags/v6.12.0.tar.gz /src.tgz
RUN mkdir /src && tar -xzf /src.tgz -C /src --strip-components=1 && cd /src && ./gradlew --no-daemon installDist -x test \
    && mkdir -p /plugins/aiven-jdbc && cp -r build/install/*/* /plugins/aiven-jdbc/
FROM apache/kafka:4.3.1
COPY --from=build /plugins /opt/connect-plugins
COPY worker.properties jdbc-sink.properties /opt/connect/
CMD ["/opt/kafka/bin/connect-standalone.sh", "/opt/connect/worker.properties", "/opt/connect/jdbc-sink.properties"]
