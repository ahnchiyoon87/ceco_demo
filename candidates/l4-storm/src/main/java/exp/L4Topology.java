package exp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.FileWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Properties;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.storm.Config;
import org.apache.storm.StormSubmitter;
import org.apache.storm.kafka.bolt.KafkaBolt;
import org.apache.storm.kafka.bolt.mapper.FieldNameBasedTupleToKafkaMapper;
import org.apache.storm.kafka.bolt.selector.DefaultTopicSelector;
import org.apache.storm.kafka.spout.FirstPollOffsetStrategy;
import org.apache.storm.kafka.spout.KafkaSpout;
import org.apache.storm.kafka.spout.KafkaSpoutConfig;
import org.apache.storm.topology.BasicOutputCollector;
import org.apache.storm.topology.OutputFieldsDeclarer;
import org.apache.storm.topology.TopologyBuilder;
import org.apache.storm.topology.base.BaseBasicBolt;
import org.apache.storm.topology.base.BaseWindowedBolt;
import org.apache.storm.topology.base.BaseWindowedBolt.Count;
import org.apache.storm.tuple.Fields;
import org.apache.storm.tuple.Tuple;
import org.apache.storm.tuple.Values;
import org.apache.storm.windowing.TupleWindow;

/**
 * L4 후보 Apache Storm 3.1.0 — V1 규칙을 Storm 토폴로지(스파우트·볼트·창 볼트)로 옮긴 것.
 *
 * <ul>
 *   <li>L4-01 임계치: 필터 볼트. 규격표는 V1 tag_limits.csv(제출 시 읽어 설정으로 넘김).</li>
 *   <li>L4-02 Z-Score: 태그마다 스트림을 나눠(스트림 id = 태그) 태그별 창 볼트 {@code withWindow(Count.of(60), Count.of(1))}
 *       → 태그별 {@code withWindow(Count.of(5), Count.of(1))} 에서 위반 합. Storm 창은 볼트 태스크 단위(키 단위 아님)라
 *       태그별 볼트로 나눈다(eKuiper 태그별 규칙과 같은 방식).</li>
 *   <li>L4-03/04 CEP: Storm 에 CEP 모듈 없음(Storm SQL 도 2.8.2 가 마지막) — 시도 기록만.</li>
 *   <li>L4-12 ONNX: V1 ONNX 잡 이식 필요(틱 튜플로 처리시각 표본 가능) — 이번 준비 범위 밖, 기록.</li>
 * </ul>
 * 알려진 차이: 도착 순서(창 볼트에 타임스탬프 필드를 주지 않음), 최소 한 번 처리(ack) — 중복 가능.
 */
public class L4Topology {
    static final ObjectMapper M = new ObjectMapper();

    static JsonNode read(String s) {
        try {
            return M.readTree(s);
        } catch (Exception e) {
            return M.createObjectNode();
        }
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

    static String sid(String tag) {
        return "t_" + tag.replace('-', '_');
    }

    /** 파싱 + 태그별 스트림 분배 + 임계치 판정(규격은 생성자에서 받은 표). */
    public static class Route extends BaseBasicBolt {
        final Map<String, String[]> limits;
        Route(Map<String, String[]> limits) { this.limits = limits; }

        @Override
        public void execute(Tuple t, BasicOutputCollector c) {
            String json = t.getStringByField("json");
            JsonNode r = read(json);
            String tag = r.path("tag").asText();
            if (!limits.containsKey(tag)) return;
            c.emit(sid(tag), new Values(tag, json));
            String[] l = limits.get(tag);          // unit, lsl, usl
            double v = r.path("value").asDouble();
            boolean usl = !l[2].isBlank() && v > Double.parseDouble(l[2]);
            boolean lsl = !l[1].isBlank() && v < Double.parseDouble(l[1]);
            if (usl || lsl) {
                ObjectNode a = base(r);
                a.put("alert_type", usl ? "THRESHOLD_USL" : "THRESHOLD_LSL");
                a.put("severity", "CRITICAL");
                a.put("detector", "TIER1_RULE");
                a.put("detail", String.format(Locale.ROOT, "%s = %s %s / 규격 [%s, %s]", tag, Math.round(v * 1000.0) / 1000.0,
                        l[0], l[1].isBlank() ? "-" : l[1], l[2].isBlank() ? "-" : l[2]));
                c.emit("alert", new Values(tag, a.toString()));
            }
        }

        @Override
        public void declareOutputFields(OutputFieldsDeclarer d) {
            for (String tag : limits.keySet()) d.declareStream(sid(tag), new Fields("key", "json"));
            d.declareStream("alert", new Fields("key", "message"));
        }
    }

    /** 최근 60행(현재 포함) 평균·표본표준편차 → 현재 행의 z, 위반 여부. */
    public static class ZStat extends BaseWindowedBolt {
        private transient org.apache.storm.task.OutputCollector out;

        @Override
        public void prepare(Map<String, Object> conf, org.apache.storm.task.TopologyContext ctx, org.apache.storm.task.OutputCollector c) {
            out = c;
        }

        @Override
        public void execute(TupleWindow w) {
            List<Tuple> all = w.get();
            List<Tuple> news = w.getNew();
            if (news.isEmpty()) return;
            int n = all.size();
            double s = 0, s2 = 0;
            for (Tuple t : all) { double v = read(t.getStringByField("json")).path("value").asDouble(); s += v; s2 += v * v; }
            if (n < 30) return;
            double mu = s / n, var = (s2 - s * s / n) / (n - 1), sd = var > 0 ? Math.sqrt(var) : 0;
            Tuple cur = news.get(news.size() - 1);
            ObjectNode r = (ObjectNode) read(cur.getStringByField("json"));
            double z = sd > 1e-9 ? Math.abs(r.path("value").asDouble() - mu) / sd : 0;
            r.put("mu", mu); r.put("sd", sd); r.put("z", z); r.put("viol", z > 3.5 ? 1 : 0);
            out.emit(new Values(r.path("tag").asText(), r.toString()));
        }

        @Override
        public void declareOutputFields(OutputFieldsDeclarer d) {
            d.declare(new Fields("key", "json"));
        }
    }

    /** 최근 5행 위반 합 >= 3 → Z-Score 알람. */
    public static class ZRun extends BaseWindowedBolt {
        private transient org.apache.storm.task.OutputCollector out;

        @Override
        public void prepare(Map<String, Object> conf, org.apache.storm.task.TopologyContext ctx, org.apache.storm.task.OutputCollector c) {
            out = c;
        }

        @Override
        public void execute(TupleWindow w) {
            List<Tuple> news = w.getNew();
            if (news.isEmpty()) return;
            int run = 0;
            for (Tuple t : w.get()) run += read(t.getStringByField("json")).path("viol").asInt();
            if (run < 3) return;
            JsonNode r = read(news.get(news.size() - 1).getStringByField("json"));
            ObjectNode a = base(r);
            a.put("alert_type", "ZSCORE");
            a.put("severity", "WARNING");
            a.put("detector", "TIER1_ZSCORE");
            a.put("detail", String.format(Locale.ROOT, "%s z=%.2f (μ=%.3f, σ=%.4f, 최근5중 %d회 위반)", r.path("tag").asText(),
                    r.path("z").asDouble(), r.path("mu").asDouble(), r.path("sd").asDouble(), run));
            out.emit(new Values(r.path("tag").asText(), a.toString()));
        }

        @Override
        public void declareOutputFields(OutputFieldsDeclarer d) {
            d.declare(new Fields("key", "message"));
        }
    }

    public static void main(String[] args) throws Exception {
        String boot = System.getenv().getOrDefault("BOOTSTRAP", "kafka:9092");
        String outTopic = System.getenv().getOrDefault("ALERT_TOPIC", "exp.l4.alerts.storm");
        Map<String, String[]> limits = new HashMap<>();
        for (String line : Files.readAllLines(Path.of(System.getenv().getOrDefault("TAG_LIMITS", "/app/tag_limits.csv")),
                StandardCharsets.UTF_8)) {
            String[] c = line.split(",", -1);
            if (c.length >= 4) limits.put(c[0], new String[]{c[1], c[2], c[3]});
        }
        attempt("L4-03/04 CEP", "Storm 모듈 목록", false,
                "Storm 3.1.0 에 CEP·패턴 모듈 없음, Storm SQL 은 2.8.2 가 마지막 — 시도할 엔진 기능이 없음");
        attempt("L4-12 ONNX", "틱 튜플 볼트", false, "미시도 — 결정(2026-09-29): ONNX 이식 안 함, ② 에서 CEP 실패가 먼저 확정되면 뒤 항목 생략");

        KafkaSpoutConfig<String, String> sc = KafkaSpoutConfig.builder(boot, "exp.l4.raw")
                .setProp(ConsumerConfig.GROUP_ID_CONFIG, "storm-l4")
                .setFirstPollOffsetStrategy(FirstPollOffsetStrategy.LATEST)
                .setRecordTranslator(r -> new Values(r.key(), r.value()), new Fields("key", "json"))
                .build();
        Properties pp = new Properties();
        pp.put("bootstrap.servers", boot);
        pp.put("acks", "all");
        pp.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
        pp.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");

        TopologyBuilder b = new TopologyBuilder();
        b.setSpout("raw", new KafkaSpout<>(sc), 1);
        b.setBolt("route", new Route(limits), 1).shuffleGrouping("raw");
        List<String> alertSources = new ArrayList<>();
        for (String tag : limits.keySet()) {
            String z60 = "z60_" + sid(tag), z5 = "z5_" + sid(tag);
            b.setBolt(z60, new ZStat().withWindow(Count.of(60), Count.of(1)), 1).shuffleGrouping("route", sid(tag));
            b.setBolt(z5, new ZRun().withWindow(Count.of(5), Count.of(1)), 1).shuffleGrouping(z60);
            alertSources.add(z5);
        }
        var sink = b.setBolt("alerts", new KafkaBolt<String, String>()
                .withProducerProperties(pp)
                .withTopicSelector(new DefaultTopicSelector(outTopic))
                .withTupleToKafkaMapper(new FieldNameBasedTupleToKafkaMapper<>("key", "message")), 1)
                .shuffleGrouping("route", "alert");
        for (String s : alertSources) sink.shuffleGrouping(s);

        Config conf = new Config();
        conf.setNumWorkers(1);
        conf.setMessageTimeoutSecs(120);
        StormSubmitter.submitTopology("l4", conf, b.createTopology());
        attempt("L4-01·L4-02", "StormSubmitter.submitTopology", true, "");
    }

    static void attempt(String rule, String feature, boolean ok, String error) {
        String f = System.getenv().getOrDefault("ATTEMPTS_FILE", "/experiments/EXP-L4/raw/stage2_" + System.getenv().getOrDefault("RUN", "manual") + "_attempts.jsonl");
        ObjectNode o = M.createObjectNode();
        o.put("engine", "storm"); o.put("rule", rule); o.put("feature", feature); o.put("ok", ok); o.put("error", error);
        o.put("at", System.currentTimeMillis() / 1000.0);
        try (FileWriter w = new FileWriter(f, StandardCharsets.UTF_8, true)) {
            w.write(o.toString() + "\n");
        } catch (Exception e) {
            System.err.println("attempt 기록 실패: " + e);
        }
    }
}
