# L4 후보 Apache Storm 3.1.0 토폴로지 제출 이미지(공식 storm 이미지 + 토폴로지 jar). Storm 3.x = Java 25.
FROM maven:3.9.16-eclipse-temurin-25 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src ./src
RUN mvn -q -B clean package -DskipTests

FROM storm:3.1.0
COPY --from=builder /build/target/storm-l4-1.0.jar /app/topology.jar
