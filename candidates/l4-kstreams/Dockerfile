# L4 후보 Kafka Streams 4.3.1 (CANDIDATES §1 [묶음 K-lib] P2). 앱 이미지 빌드(라이브러리 엔진).
FROM maven:3.9.16-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src ./src
RUN mvn -q -B clean package -DskipTests

FROM eclipse-temurin:17.0.20_8-jre
WORKDIR /app
COPY --from=builder /build/target/kstreams-l4-1.0.jar /app/app.jar
CMD ["java", "-Xmx512m", "-jar", "/app/app.jar"]
