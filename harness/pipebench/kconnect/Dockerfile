# 중계 후보 P2(P-D): Kafka Connect(apache/kafka 4.3.1 동봉 connect-standalone) + Lenses Stream Reactor 12.1.2 MQTT source.
# Stream Reactor 12.x 는 Kafka >= 4.0 필요 → pipebench 를 KAFKA_IMAGE=apache/kafka:4.3.1 로 띄울 때만 쓴다.
# 플러그인 zip 은 GitHub 릴리스 자산(https://github.com/lensesio/stream-reactor/releases/tag/12.1.2).
FROM apache/kafka:4.3.1
USER root
ADD https://github.com/lensesio/stream-reactor/releases/download/12.1.2/kafka-connect-mqtt-12.1.2.zip /tmp/sr-mqtt.zip
RUN mkdir -p /opt/connect-plugins && cd /opt/connect-plugins && unzip -q /tmp/sr-mqtt.zip && rm /tmp/sr-mqtt.zip && chown -R appuser /opt/connect-plugins
COPY worker.properties mqtt-source.properties /opt/connect/
USER appuser
CMD ["/opt/kafka/bin/connect-standalone.sh", "/opt/connect/worker.properties", "/opt/connect/mqtt-source.properties"]
