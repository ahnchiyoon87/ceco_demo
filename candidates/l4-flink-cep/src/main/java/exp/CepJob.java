package exp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.cep.CEP;
import org.apache.flink.cep.PatternStream;
import org.apache.flink.cep.functions.PatternProcessFunction;
import org.apache.flink.cep.nfa.aftermatch.AfterMatchSkipStrategy;
import org.apache.flink.cep.pattern.Pattern;
import org.apache.flink.cep.pattern.conditions.SimpleCondition;
import org.apache.flink.connector.base.DeliveryGuarantee;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.SingleOutputStreamOperator;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.util.Collector;
import org.apache.flink.util.OutputTag;

/**
 * EXP-111: V1 04_tier1_cep.sql 과 같은 패턴을 DataStream CEP API 로 구현한다.
 * "교반기 전류 IT-102 > 9.6A 후 10초 이내 진동 VT-101 > 7.1mm/s", device 별, 매치 후 마지막 이벤트 뒤로 건너뜀.
 * 이벤트 시간·워터마크는 V1 01_sources.sql 과 같게: ts(ns)/1e6, 지연 5s, 유휴 5s, 시작 오프셋 latest, 체크포인트 10s.
 * 늦은 레코드는 사이드 출력으로 exp.l4.dropped.cep 에 기록한다(폐기+기록).
 */
public class CepJob {

    public static class Reading {
        public long tsNs;
        public long tsMs;
        public String site;
        public String device;
        public String tag;
        public double value;
        public String json;
        public Reading() {}
    }

    static final ObjectMapper M = new ObjectMapper();

    static Reading parse(String s) {
        try {
            JsonNode n = M.readTree(s);
            Reading r = new Reading();
            r.tsNs = n.get("ts").asLong();
            r.tsMs = r.tsNs / 1_000_000L;
            r.site = n.path("site").asText();
            r.device = n.path("device").asText();
            r.tag = n.path("tag").asText();
            r.value = n.get("value").asDouble();
            r.json = s;
            return r;
        } catch (Exception e) {
            return null;
        }
    }

    public static void main(String[] args) throws Exception {
        String boot = System.getenv().getOrDefault("BOOTSTRAP", "kafka:9092");
        // 규칙 값은 제출 시 환경변수로 받는다(L4-10: 코드·재빌드 없이 규칙 변경). 기본값 = V1 04_tier1_cep.sql
        final double itLimit = Double.parseDouble(System.getenv().getOrDefault("IT102_LIMIT", "9.6"));
        final double vtLimit = Double.parseDouble(System.getenv().getOrDefault("VT101_LIMIT", "7.1"));
        final long windowS = Long.parseLong(System.getenv().getOrDefault("PATTERN_WINDOW_S", "10"));
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.enableCheckpointing(10_000);

        KafkaSource<String> source = KafkaSource.<String>builder()
                .setBootstrapServers(boot)
                .setTopics("exp.l4.raw")
                .setGroupId("cep-ds")
                .setStartingOffsets(OffsetsInitializer.latest())
                .setValueOnlyDeserializer(new SimpleStringSchema())
                .build();

        // 소스에서 파티션별 워터마크 생성 (SQL WATERMARK + idle-timeout 과 같은 위치)
        WatermarkStrategy<String> ws = WatermarkStrategy.<String>forBoundedOutOfOrderness(Duration.ofSeconds(5))
                .withTimestampAssigner((s, prev) -> {
                    Reading r = parse(s);
                    return r == null ? prev : r.tsMs;
                })
                .withIdleness(Duration.ofSeconds(5));

        DataStream<Reading> readings = env.fromSource(source, ws, "exp.l4.raw")
                .map(CepJob::parse).returns(Reading.class)
                .filter(r -> r != null && ("IT-102".equals(r.tag) || "VT-101".equals(r.tag)));

        Pattern<Reading, ?> pattern = Pattern.<Reading>begin("oc", AfterMatchSkipStrategy.skipPastLastEvent())
                .where(SimpleCondition.of(r -> "IT-102".equals(r.tag) && r.value > itLimit))
                .followedBy("vib")
                .where(SimpleCondition.of(r -> "VT-101".equals(r.tag) && r.value > vtLimit))
                .within(Duration.ofSeconds(windowS));

        OutputTag<Reading> late = new OutputTag<Reading>("late") {};
        PatternStream<Reading> ps = CEP.pattern(readings.keyBy(r -> r.device), pattern).sideOutputLateData(late);

        SingleOutputStreamOperator<String> alerts = ps.process(new PatternProcessFunction<Reading, String>() {
            @Override
            public void processMatch(Map<String, List<Reading>> m, Context ctx, Collector<String> out) {
                Reading oc = m.get("oc").get(0);
                Reading vib = m.get("vib").get(0);
                long secs = (vib.tsMs - oc.tsMs) / 1000L;
                ObjectNode a = M.createObjectNode();
                a.put("ts", vib.tsNs);
                a.put("site", vib.site);
                a.put("device", vib.device);
                a.put("tag", "VT-101");
                a.put("value", vib.value);
                a.put("alert_type", "CEP_BEARING");
                a.put("severity", "CRITICAL");
                a.put("detector", "TIER1_CEP");
                a.put("detail", String.format("교반기 전류 %.2fA (정격 120%% 초과) 후 %d초 내 진동 %.2fmm/s 상회 → 베어링 열화 의심",
                        oc.value, secs, vib.value));
                out.collect(a.toString());
            }
        });

        alerts.sinkTo(sink(boot, "exp.l4.alerts.cep")).name("alerts");
        alerts.getSideOutput(late)
                .map(r -> {
                    ObjectNode d = (ObjectNode) M.readTree(r.json);
                    d.put("reason", "late");
                    return d.toString();
                }).returns(String.class)
                .sinkTo(sink(boot, "exp.l4.dropped.cep")).name("dropped");

        env.execute("EXP111-DataStream-CEP");
    }

    static KafkaSink<String> sink(String boot, String topic) {
        return KafkaSink.<String>builder()
                .setBootstrapServers(boot)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(topic)
                        .setValueSerializationSchema(new SimpleStringSchema())
                        .build())
                .setDeliveryGuarantee(DeliveryGuarantee.AT_LEAST_ONCE)   // V1 SQL Kafka 싱크 기본과 같음
                .build();
    }
}
