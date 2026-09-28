package exp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.FileWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.apache.beam.runners.direct.DirectRunner;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.extensions.sql.SqlTransform;
import org.apache.beam.sdk.io.kafka.KafkaIO;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.options.StreamingOptions;
import org.apache.beam.sdk.schemas.Schema;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.Flatten;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.Values;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionList;
import org.apache.beam.sdk.values.Row;
import org.apache.beam.sdk.values.TypeDescriptors;
import org.apache.beam.sdk.transforms.windowing.AfterPane;
import org.apache.beam.sdk.transforms.windowing.GlobalWindows;
import org.apache.beam.sdk.transforms.windowing.Repeatedly;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.joda.time.Duration;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;

/**
 * L4 후보 Apache Beam 2.76.0 (DirectRunner) — V1 규칙을 Beam SQL(SqlTransform)로 옮긴 것.
 *
 * <ul>
 *   <li>L4-01 임계치: SqlTransform. 규격표(V1 tag_limits.csv)는 WHERE/CASE 식으로 펼친다.</li>
 *   <li>L4-02 Z-Score: 시도 — V1 과 같은 ROWS 프레임 OVER 창 SQL(문서: Beam SQL "Window functions: No").</li>
 *   <li>L4-03/04 CEP: 시도 — V1 MATCH_RECOGNIZE 그대로(문서: "MATCH_RECOGNIZE: No").</li>
 *   <li>L4-12 ONNX: Beam Java 에는 RunInference 가 없음(Python SDK 전용) — V1 ONNX 잡 이식 필요, 미시도로 기록.</li>
 * </ul>
 * 시도는 파이프라인 구성 시점(SqlTransform 확장)에서 엔진이 거부하면 그 예외 메시지를 시도 기록에 남기고 나머지로 계속한다.
 * 구성에 성공한 규칙은 실제로 실행되어 알람을 낸다(②에서 결과 비교).
 */
public class BeamL4 {
    static final ObjectMapper M = new ObjectMapper();
    static final Schema RAW = Schema.builder().addInt64Field("ts").addStringField("site").addStringField("device")
            .addStringField("tag").addDoubleField("v").addDateTimeField("et").build();   // et = ts/1e6 ms (V1 event_time)

    public static void main(String[] args) throws Exception {
        String boot = env("BOOTSTRAP", "kafka:9092");
        String out = env("ALERT_TOPIC", "exp.l4.alerts.beam");
        attempt("L4-12 ONNX", "Beam Java SDK", false, "Beam Java 에 RunInference 없음(Python SDK 전용). 미시도 — 결정(2026-09-29): ONNX 이식 안 함, ② 에서 CEP 실패가 먼저 확정되면 뒤 항목 생략");

        PipelineOptions o = PipelineOptionsFactory.fromArgs(args).create();
        o.setRunner(DirectRunner.class);
        o.as(StreamingOptions.class).setStreaming(true);
        Pipeline p = Pipeline.create(o);
        PCollection<Row> raw = source(p, boot);

        List<PCollection<Row>> alerts = new ArrayList<>();
        tryRule(alerts, raw, o, boot, "L4-01 임계치", thresholdSql());
        tryRule(alerts, raw, o, boot, "L4-02 Z-Score",
                "SELECT ts, site, device, tag, v, 'ZSCORE' AS alert_type, 'WARNING' AS severity, 'TIER1_ZSCORE' AS detector, "
                + "'z' AS detail FROM (SELECT ts, site, device, tag, v, mu, sd, "
                + " SUM(CASE WHEN sd > 1e-9 AND ABS(v - mu) / sd > 3.5 THEN 1 ELSE 0 END) OVER (PARTITION BY tag ORDER BY ts "
                + "  ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS viol_run FROM (SELECT ts, site, device, tag, v, "
                + "  AVG(v) OVER (PARTITION BY tag ORDER BY ts ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS mu, "
                + "  STDDEV_SAMP(v) OVER (PARTITION BY tag ORDER BY ts ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS sd, "
                + "  COUNT(*) OVER (PARTITION BY tag ORDER BY ts ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS n "
                + "  FROM PCOLLECTION) a WHERE n >= 30) b WHERE viol_run >= 3");
        String cepBase = "SELECT ts, site, device, 'VT-101' AS tag, v, 'CEP_BEARING' AS alert_type, 'CRITICAL' AS severity, "
                + "'TIER1_CEP' AS detector, 'cep' AS detail FROM PCOLLECTION MATCH_RECOGNIZE (PARTITION BY device ORDER BY et "
                + "MEASURES LAST(VIB.ts) AS ts, LAST(VIB.site) AS site, LAST(VIB.v) AS v "
                + "ONE ROW PER MATCH AFTER MATCH SKIP PAST LAST ROW PATTERN (OVERCURRENT OTHER*? VIB) %s"
                + "DEFINE OVERCURRENT AS OVERCURRENT.tag = 'IT-102' AND OVERCURRENT.v > 9.6, "
                + "VIB AS VIB.tag = 'VT-101' AND VIB.v > 7.1)";
        // V1 그대로(WITHIN 10초) 먼저, 엔진이 거부하면 WITHIN 없이 한 번 더(이 경우 10초 조건이 빠져 S06b 가 달라질 것 — ②에서 확인)
        if (!tryRule(alerts, raw, o, boot, "L4-03/04 CEP", String.format(cepBase, "WITHIN INTERVAL '10' SECOND "))) {
            tryRule(alerts, raw, o, boot, "L4-03/04 CEP (WITHIN 없음)", String.format(cepBase, ""));
        }
        if (alerts.isEmpty()) throw new IllegalStateException("구성된 규칙이 없음");

        PCollectionList.of(alerts).apply(Flatten.pCollections())
                .apply("json", MapElements.into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.strings()))
                        .via((Row r) -> {
                            ObjectNode a = M.createObjectNode();
                            a.put("ts", r.getInt64("ts")); a.put("site", r.getString("site")); a.put("device", r.getString("device"));
                            a.put("tag", r.getString("tag")); a.put("value", r.getDouble("v"));
                            a.put("alert_type", r.getString("alert_type")); a.put("severity", r.getString("severity"));
                            a.put("detector", r.getString("detector")); a.put("detail", r.getString("detail"));
                            return KV.of(r.getString("tag"), a.toString());
                        }))
                .apply("sink", KafkaIO.<String, String>write().withBootstrapServers(boot).withTopic(out)
                        .withKeySerializer(StringSerializer.class).withValueSerializer(StringSerializer.class));
        p.run().waitUntilFinish();
    }

    /** 카프카 원천 → Row(스키마 RAW). 규칙 검사용 빈 파이프라인에도 같은 비유계(unbounded) 원천을 쓴다. */
    static PCollection<Row> source(Pipeline p, String boot) {
        return p.apply("kafka", KafkaIO.<String, String>read()
                        .withBootstrapServers(boot).withTopic("exp.l4.raw")
                        .withKeyDeserializer(StringDeserializer.class).withValueDeserializer(StringDeserializer.class)
                        .withConsumerConfigUpdates(Map.of("group.id", "beam-l4", "auto.offset.reset", "latest"))
                        .withoutMetadata())
                .apply(Values.create())
                .apply("parse", ParDo.of(new DoFn<String, Row>() {
                    @ProcessElement
                    public void pe(@Element String s, OutputReceiver<Row> r) throws Exception {
                        JsonNode j = M.readTree(s);
                        r.output(Row.withSchema(RAW).addValues(j.path("ts").asLong(), j.path("site").asText(),
                                j.path("device").asText(), j.path("tag").asText(), j.path("value").asDouble(),
                                new org.joda.time.Instant(j.path("ts").asLong() / 1_000_000L)).build());
                    }
                })).setRowSchema(RAW);
    }

    /** 레코드마다 방출하는 트리거(비유계 입력에서 집계·패턴을 쓰려면 Beam 이 요구하는 설정). */
    static PCollection<Row> triggered(PCollection<Row> in, String name) {
        return in.apply(name, Window.<Row>into(new GlobalWindows())
                .triggering(Repeatedly.forever(AfterPane.elementCountAtLeast(1)))
                .withAllowedLateness(Duration.ZERO).discardingFiredPanes());
    }

    /**
     * 규칙 하나를 먼저 버리는 파이프라인(같은 비유계 원천)에 적용해 엔진이 받아들이는지 본다(실패한 apply 가 본 파이프라인을
     * 망가뜨리지 않게). ① 그대로 → ② 안 되면 레코드 단위 트리거 창을 씌워 한 번 더. 받아들여진 형태만 본 파이프라인에 붙인다.
     */
    static boolean tryRule(List<PCollection<Row>> alerts, PCollection<Row> raw, PipelineOptions o, String boot, String rule, String sql) {
        for (boolean trig : new boolean[]{false, true}) {
            String feature = trig ? "SqlTransform.query + GlobalWindows 레코드 단위 트리거" : "SqlTransform.query";
            try {
                Pipeline probe = Pipeline.create(o);
                PCollection<Row> in = source(probe, boot);
                (trig ? triggered(in, "w") : in).apply(rule, SqlTransform.query(sql));
            } catch (Exception e) {
                attempt(rule, feature, false, chain(e), sql);
                System.err.println(rule + " / " + feature + " 구성 실패: " + chain(e));
                continue;
            }
            PCollection<Row> in = trig ? triggered(raw, rule + " 창") : raw;
            alerts.add(in.apply(rule, SqlTransform.query(sql)));
            attempt(rule, feature, true, "", sql);
            return true;
        }
        return false;
    }

    /** 근본 원인부터 적는다(쿼리 원문이 앞에 붙는 SqlConversionException 때문에 잘리지 않게). */
    static String chain(Throwable e) {
        List<String> parts = new ArrayList<>();
        for (Throwable c = e; c != null; c = c.getCause()) {
            String m = c.getClass().getSimpleName() + ": " + String.valueOf(c.getMessage());
            parts.add(0, m.length() > 600 ? m.substring(0, 600) + "…" : m);
        }
        return String.join(" <- ", parts);
    }

    static String thresholdSql() throws Exception {
        List<String> conds = new ArrayList<>(), usl = new ArrayList<>(), det = new ArrayList<>();
        for (String line : Files.readAllLines(Path.of(env("TAG_LIMITS", "/app/tag_limits.csv")), StandardCharsets.UTF_8)) {
            String[] c = line.split(",", -1);
            if (c.length < 4) continue;
            List<String> parts = new ArrayList<>();
            if (!c[3].isBlank()) { parts.add("v > " + c[3]); usl.add("(tag = '" + c[0] + "' AND v > " + c[3] + ")"); }
            if (!c[2].isBlank()) parts.add("v < " + c[2]);
            if (!parts.isEmpty()) {
                conds.add("(tag = '" + c[0] + "' AND (" + String.join(" OR ", parts) + "))");
                det.add("WHEN tag = '" + c[0] + "' THEN ' " + c[1] + " / 규격 [" + (c[2].isBlank() ? "-" : c[2]) + ", "
                        + (c[3].isBlank() ? "-" : c[3]) + "]'");
            }
        }
        return "SELECT ts, site, device, tag, v, CASE WHEN " + String.join(" OR ", usl)
                + " THEN 'THRESHOLD_USL' ELSE 'THRESHOLD_LSL' END AS alert_type, 'CRITICAL' AS severity, "
                + "'TIER1_RULE' AS detector, tag || ' = ' || CAST(v AS VARCHAR) || CASE " + String.join(" ", det)
                + " ELSE '' END AS detail FROM PCOLLECTION WHERE " + String.join(" OR ", conds);
    }

    static void attempt(String rule, String feature, boolean ok, String error) {
        attempt(rule, feature, ok, error, "");
    }

    static void attempt(String rule, String feature, boolean ok, String error, String statement) {
        String f = env("ATTEMPTS_FILE", "/experiments/EXP-L4/raw/stage2_" + env("RUN", "manual") + "_attempts.jsonl");
        ObjectNode o = M.createObjectNode();
        o.put("engine", "beam"); o.put("rule", rule); o.put("feature", feature); o.put("ok", ok);
        o.put("error", error.length() > 2000 ? error.substring(0, 2000) : error); o.put("statement", statement);
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
