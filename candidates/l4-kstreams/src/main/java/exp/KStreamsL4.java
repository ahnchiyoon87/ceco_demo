package exp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.FileWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Properties;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Materialized;
import org.apache.kafka.streams.kstream.Produced;
import org.apache.kafka.streams.processor.TimestampExtractor;

/**
 * L4 후보 Kafka Streams 4.3.1 — V1 규칙(flink/sql/02·03)을 Kafka Streams DSL 로 옮긴 것.
 *
 * <ul>
 *   <li>L4-01 임계치: {@code filter} + {@code mapValues}. 규격표는 V1 tag_limits.csv(설정 파일)를 시작 시 적재.</li>
 *   <li>L4-02 Z-Score: 키(=tag, 리플레이가 key=tag 로 발행) 단위 {@code groupByKey().aggregate()} 로 최근 60행을 KTable 상태
 *       (RocksDB + changelog)에 두고 통계를 낸 뒤, 다시 {@code aggregate()} 로 최근 5행 위반 합. 캐시 0 으로 레코드마다 방출.
 *       경계: Kafka Streams 창은 시간 기반뿐이라 "최근 N행" 은 집계 함수(Aggregator) 안에서 목록을 유지한다 — DSL 의 집계 기능은
 *       쓰지만 창 모양은 우리 코드다(STAGE2.md 약점 열에 표시).</li>
 *   <li>L4-03/04 CEP: DSL 에 패턴 연산 없음. Processor API 로는 NFA(CEP 엔진) 재구현이 필요 → 시도하지 않고 기록.</li>
 *   <li>L4-12 ONNX: V1 ONNX 잡(처리시각 1초 표본·보간)을 Processor API punctuator 로 이식해야 함 → 이번 준비 범위 밖, 기록.</li>
 * </ul>
 * 알려진 차이: 도착 순서 처리(V1 은 이벤트 시각 정렬 + 워터마크 5초 뒤 폐기).
 */
public class KStreamsL4 {
    static final ObjectMapper M = new ObjectMapper();
    static final Map<String, double[]> LIMITS = new HashMap<>();   // tag → {lsl, usl} (NaN = 없음)
    static final Map<String, String> UNITS = new HashMap<>();

    /** 이벤트 시각 = ts(ns)/1e6 ms (V1 과 같은 변환). */
    public static class TsExtractor implements TimestampExtractor {
        @Override
        public long extract(ConsumerRecord<Object, Object> r, long partitionTime) {
            try {
                return M.readTree((String) r.value()).get("ts").asLong() / 1_000_000L;
            } catch (Exception e) {
                return partitionTime;
            }
        }
    }

    static void loadLimits() throws java.io.IOException {
        for (String line : Files.readAllLines(Path.of(env("TAG_LIMITS", "/app/tag_limits.csv")), StandardCharsets.UTF_8)) {
            String[] c = line.split(",", -1);
            if (c.length < 4) continue;
            LIMITS.put(c[0], new double[]{c[2].isBlank() ? Double.NaN : Double.parseDouble(c[2]),
                                          c[3].isBlank() ? Double.NaN : Double.parseDouble(c[3])});
            UNITS.put(c[0], c[1]);
        }
    }

    public static void main(String[] args) throws Exception {
        String boot = env("BOOTSTRAP", "kafka:9092");
        String out = env("ALERT_TOPIC", "exp.l4.alerts.kstreams");
        loadLimits();
        attempt("L4-03/04 CEP", "DSL 연산자·Processor API", false,
                "Kafka Streams DSL 에 패턴(CEP) 연산 없음. Processor API 로는 CEP 엔진(NFA) 재구현 필요 — 직접 제작 금지로 미구현");
        attempt("L4-12 ONNX", "Processor API punctuator", false,
                "V1 ONNX 잡(처리시각 1초 표본·선형 보간) 이식 필요 — 이번 준비 범위 밖, 미시도");

        Properties p = props(boot);
        org.apache.kafka.streams.Topology t = topology(out);
        KafkaStreams s = new KafkaStreams(t, p);
        Runtime.getRuntime().addShutdownHook(new Thread(s::close));
        attempt("L4-01·L4-02", "topology", true, "", t.describe().toString());
        s.start();
    }

    static Properties props(String boot) {
        Properties p = new Properties();
        p.put(StreamsConfig.APPLICATION_ID_CONFIG, env("APP_ID", "l4-kstreams"));
        p.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, boot);
        p.put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG, StreamsConfig.EXACTLY_ONCE_V2);
        p.put(StreamsConfig.STATE_DIR_CONFIG, env("STATE_DIR", "/state"));
        p.put(StreamsConfig.STATESTORE_CACHE_MAX_BYTES_CONFIG, 0);        // 집계 갱신마다 방출(= 행마다 판정)
        p.put(StreamsConfig.REPLICATION_FACTOR_CONFIG, 1);
        p.put(StreamsConfig.consumerPrefix(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG), "latest");   // V1 latest-offset
        p.put(StreamsConfig.DEFAULT_TIMESTAMP_EXTRACTOR_CLASS_CONFIG, TsExtractor.class);

        return p;
    }

    /** 규칙 토폴로지(TopologyTestDriver 로도 쓴다). */
    static org.apache.kafka.streams.Topology topology(String out) {
        StreamsBuilder b = new StreamsBuilder();
        KStream<String, String> raw = b.stream("exp.l4.raw", Consumed.with(Serdes.String(), Serdes.String()));
        Produced<String, String> prod = Produced.with(Serdes.String(), Serdes.String());

        // ── L4-01 ──
        raw.filter((k, v) -> violates(read(v))).mapValues(v -> threshold(read(v))).to(out, prod);

        // ── L4-02 ──
        raw.groupByKey()
           .aggregate(() -> "{\"vals\":[]}", (k, v, agg) -> push(agg, read(v), 60),
                      Materialized.<String, String, org.apache.kafka.streams.state.KeyValueStore<org.apache.kafka.common.utils.Bytes, byte[]>>as("z60")
                                  .withKeySerde(Serdes.String()).withValueSerde(Serdes.String()))
           .toStream()
           .mapValues(KStreamsL4::zstats)
           .filter((k, v) -> v != null)
           .groupByKey()
           .aggregate(() -> "{\"vals\":[]}", (k, v, agg) -> pushViol(agg, read(v)),
                      Materialized.<String, String, org.apache.kafka.streams.state.KeyValueStore<org.apache.kafka.common.utils.Bytes, byte[]>>as("z5")
                                  .withKeySerde(Serdes.String()).withValueSerde(Serdes.String()))
           .toStream()
           .mapValues(KStreamsL4::zalert)
           .filter((k, v) -> v != null)
           .to(out, prod);

        return b.build();
    }

    static JsonNode read(String v) {
        try {
            return M.readTree(v);
        } catch (Exception e) {
            return M.createObjectNode();
        }
    }

    static boolean violates(JsonNode r) {
        double[] l = LIMITS.get(r.path("tag").asText());
        if (l == null || !r.has("value")) return false;
        double v = r.get("value").asDouble();
        return (!Double.isNaN(l[1]) && v > l[1]) || (!Double.isNaN(l[0]) && v < l[0]);
    }

    static ObjectNode base(JsonNode r) {
        ObjectNode a = M.createObjectNode();
        a.put("ts", r.path("ts").asLong());
        a.put("site", r.path("site").asText());
        a.put("device", r.path("device").asText());
        a.put("tag", r.path("tag").asText());
        a.put("value", r.path("value").asDouble());
        return a;
    }

    static String fmt(double x) {
        return Double.isNaN(x) ? "-" : String.valueOf(x);
    }

    static String threshold(JsonNode r) {
        String tag = r.path("tag").asText();
        double[] l = LIMITS.get(tag);
        double v = r.path("value").asDouble();
        ObjectNode a = base(r);
        a.put("alert_type", !Double.isNaN(l[1]) && v > l[1] ? "THRESHOLD_USL" : "THRESHOLD_LSL");
        a.put("severity", "CRITICAL");
        a.put("detector", "TIER1_RULE");
        a.put("detail", String.format(Locale.ROOT, "%s = %s %s / 규격 [%s, %s]", tag,
                Math.round(v * 1000.0) / 1000.0, UNITS.get(tag), fmt(l[0]), fmt(l[1])));
        return a.toString();
    }

    /** 집계 상태 = 최근 n 개 값 + 마지막 레코드. */
    static String push(String agg, JsonNode r, int n) {
        ObjectNode s = (ObjectNode) read(agg);
        ArrayNode vals = (ArrayNode) s.get("vals");
        vals.add(r.path("value").asDouble());
        while (vals.size() > n) vals.remove(0);
        s.set("row", r);
        return s.toString();
    }

    static String zstats(String agg) {
        JsonNode s = read(agg);
        JsonNode vals = s.get("vals");
        int n = vals.size();
        if (n < 30) return null;
        double sum = 0, sum2 = 0;
        for (JsonNode x : vals) { sum += x.asDouble(); sum2 += x.asDouble() * x.asDouble(); }
        double mu = sum / n;
        double var = n > 1 ? (sum2 - sum * sum / n) / (n - 1) : 0;
        double sd = var > 0 ? Math.sqrt(var) : 0;
        JsonNode r = s.get("row");
        double z = sd > 1e-9 ? Math.abs(r.path("value").asDouble() - mu) / sd : 0;
        ObjectNode o = (ObjectNode) r.deepCopy();
        o.put("mu", mu); o.put("sd", sd); o.put("z", z); o.put("viol", z > 3.5 ? 1 : 0);
        return o.toString();
    }

    static String pushViol(String agg, JsonNode r) {
        ObjectNode s = (ObjectNode) read(agg);
        ArrayNode vals = (ArrayNode) s.get("vals");
        vals.add(r.path("viol").asInt());
        while (vals.size() > 5) vals.remove(0);
        s.set("row", r);
        return s.toString();
    }

    static String zalert(String agg) {
        JsonNode s = read(agg);
        int run = 0;
        for (JsonNode x : s.get("vals")) run += x.asInt();
        if (run < 3) return null;
        JsonNode r = s.get("row");
        ObjectNode a = base(r);
        a.put("alert_type", "ZSCORE");
        a.put("severity", "WARNING");
        a.put("detector", "TIER1_ZSCORE");
        a.put("detail", String.format(Locale.ROOT, "%s z=%.2f (μ=%.3f, σ=%.4f, 최근5중 %d회 위반)", r.path("tag").asText(),
                r.path("z").asDouble(), r.path("mu").asDouble(), r.path("sd").asDouble(), run));
        return a.toString();
    }

    static void attempt(String rule, String feature, boolean ok, String error) {
        attempt(rule, feature, ok, error, "");
    }

    static void attempt(String rule, String feature, boolean ok, String error, String statement) {
        String f = env("ATTEMPTS_FILE", "/experiments/EXP-L4/raw/stage2_" + env("RUN", "manual") + "_attempts.jsonl");
        ObjectNode o = M.createObjectNode();
        o.put("engine", "kstreams"); o.put("rule", rule); o.put("feature", feature); o.put("ok", ok);
        o.put("error", error); o.put("statement", statement.length() > 3000 ? statement.substring(0, 3000) : statement);
        o.put("at", System.currentTimeMillis() / 1000.0);
        try (FileWriter w = new FileWriter(f, StandardCharsets.UTF_8, true)) {
            w.write(o.toString() + "\n");
        } catch (Exception e) {
            System.err.println("attempt 기록 실패: " + e);
        }
    }

    static String env(String k, String d) {
        String v = System.getenv(k);
        return v == null || v.isBlank() ? d : v;
    }
}
