# L4 후보 Apache Beam 2.76.0 Java + DirectRunner (Beam 자체 시험, Flink 러너 아님).
FROM maven:3.9.16-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src ./src
RUN mvn -q -B clean package -DskipTests

FROM eclipse-temurin:17.0.20_8-jre
WORKDIR /app
COPY --from=builder /build/target/beam-l4-1.0.jar /app/app.jar
CMD ["java", "-Xmx1g", "-jar", "/app/app.jar"]
