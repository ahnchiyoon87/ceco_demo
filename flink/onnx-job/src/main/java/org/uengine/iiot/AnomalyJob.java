package org.uengine.iiot;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.DeserializationSchema;
import org.apache.flink.api.common.serialization.SerializationSchema;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.connector.base.DeliveryGuarantee;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.SingleOutputStreamOperator;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.Properties;

/**
 * Tier 3 · Flink 잡 — 결측 보간 → 텐서 조립 → 임베디드 ONNX 추론.
 *
 * <pre>
 *   sensor.telemetry.raw
 *        │
 *        ├─ Interpolator (태그별 keyed state, RocksDB)
 *        │     ├─▶ sensor.telemetry.clean   (quality 로 실측/추정 구분)
 *        │     │
 *        │     └─▶ OnnxScorer (디바이스별 keyed state)
 *        │             ├─▶ sensor.anomaly.score
 *        │             └─▶ sensor.alerts     (side output)
 * </pre>
 *
 * Tier-1 규칙 탐지(임계치·Z-Score·CEP)는 이 잡이 아니라 flink/sql/*.sql 이 담당한다.
 */
public class AnomalyJob {

    public static void main(String[] args) throws Exception {
        Properties p = load(args.length > 0 ? args[0] : "/opt/flink/job/job.properties");

        String bootstrap = p.getProperty("kafka.bootstrap", "kafka:9092");
        String rawTopic = p.getProperty("kafka.topic.raw", "sensor.telemetry.raw");
        String cleanTopic = p.getProperty("kafka.topic.clean", "sensor.telemetry.clean");
        String scoreTopic = p.getProperty("kafka.topic.score", "sensor.anomaly.score");
        String alertTopic = p.getProperty("kafka.topic.alerts", "sensor.alerts");
        String groupId = p.getProperty("kafka.group.id", "flink-tier2-onnx");

        String mode = p.getProperty("interpolation.mode", "linear");
        long maxGapMs = Long.parseLong(p.getProperty("interpolation.max-gap-ms", "20000"));
        long scanMs = Long.parseLong(p.getProperty("scan.interval.ms", "1000"));

        String modelPath = p.getProperty("model.path", "/opt/models/model.onnx");
        String metaPath = p.getProperty("model.meta", "/opt/models/model_meta.json");
        int steps = Integer.parseInt(p.getProperty("window.steps", "10"));
        long inferMs = Long.parseLong(p.getProperty("inference.interval.ms", "1000"));
        String thrRaw = p.getProperty("anomaly.threshold", "").trim();
        Double threshold = thrRaw.isEmpty() ? null : Double.valueOf(thrRaw);

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        KafkaSource<Reading> source = KafkaSource.<Reading>builder()
                .setBootstrapServers(bootstrap)
                .setTopics(rawTopic)
                .setGroupId(groupId)
                .setStartingOffsets(OffsetsInitializer.latest())
                .setValueOnlyDeserializer(new JsonDeser<>(Reading.class))
                .build();

        DataStream<Reading> raw = env.fromSource(
                source, WatermarkStrategy.noWatermarks(), "sensor.telemetry.raw");

        // ── 1단계: 태그별 중복제거 + 결측 보간 ──
        DataStream<Reading> clean = raw
                .keyBy(r -> r.tag)
                .process(new Interpolator(mode, maxGapMs, scanMs))
                .name("interpolate(" + mode + ")")
                .uid("interpolator");

        clean.sinkTo(jsonSink(bootstrap, cleanTopic, "clean"))
                .name("sink:" + cleanTopic);

        // ── 2단계: 디바이스별 텐서 조립 + 임베디드 ONNX 추론 ──
        SingleOutputStreamOperator<AnomalyScore> scored = clean
                .keyBy(r -> r.device)
                .process(new OnnxScorer(modelPath, metaPath, steps, inferMs, threshold))
                .name("onnx-autoencoder")
                .uid("onnx-scorer");

        scored.sinkTo(jsonSink(bootstrap, scoreTopic, "score"))
                .name("sink:" + scoreTopic);

        scored.getSideOutput(OnnxScorer.ALERT_TAG)
                .sinkTo(jsonSink(bootstrap, alertTopic, "ml-alert"))
                .name("sink:" + alertTopic);

        env.execute("AR100-Tier2-OnnxAnomalyDetection");
    }

    private static Properties load(String path) throws IOException {
        Properties p = new Properties();
        try (FileInputStream in = new FileInputStream(path)) {
            p.load(in);
        }
        return p;
    }

    private static <T> KafkaSink<T> jsonSink(String bootstrap, String topic, String txPrefix) {
        return KafkaSink.<T>builder()
                .setBootstrapServers(bootstrap)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(topic)
                        .setValueSerializationSchema(new JsonSer<T>())
                        .build())
                .setDeliveryGuarantee(DeliveryGuarantee.AT_LEAST_ONCE)
                .build();
    }

    /** Jackson 기반 JSON 역직렬화. 알 수 없는 필드는 무시해 스키마 확장에 견딘다. */
    public static class JsonDeser<T> implements DeserializationSchema<T> {
        private final Class<T> type;
        private transient ObjectMapper mapper;

        public JsonDeser(Class<T> type) {
            this.type = type;
        }

        private ObjectMapper mapper() {
            if (mapper == null) {
                mapper = new ObjectMapper()
                        .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
            }
            return mapper;
        }

        @Override
        public T deserialize(byte[] message) throws IOException {
            return mapper().readValue(message, type);
        }

        @Override
        public boolean isEndOfStream(T nextElement) {
            return false;
        }

        @Override
        public TypeInformation<T> getProducedType() {
            return TypeInformation.of(type);
        }
    }

    public static class JsonSer<T> implements SerializationSchema<T> {
        private transient ObjectMapper mapper;

        @Override
        public byte[] serialize(T element) {
            try {
                if (mapper == null) {
                    mapper = new ObjectMapper();
                }
                return mapper.writeValueAsBytes(element);
            } catch (Exception e) {
                throw new RuntimeException("JSON 직렬화 실패", e);
            }
        }
    }
}
