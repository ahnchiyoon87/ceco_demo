package org.uengine.iiot;

import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.flink.api.common.state.MapState;
import org.apache.flink.api.common.state.MapStateDescriptor;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.api.common.functions.OpenContext;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;
import org.apache.flink.util.OutputTag;

import java.io.File;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Tier-2 · Autoencoder 기반 다변량 이상 탐지 (PDF p.9).
 *
 * <p>ONNX Runtime 을 TaskManager 프로세스 <b>내부</b>에서 직접 구동한다.
 * 외부 REST/gRPC 추론 서버를 호출하지 않으므로 네트워크 홉이 0 이며,
 * PDF p.10 의 "RPC Callout 지양 / In-Stream Embedded Serving" 권고를 만족한다.
 * onnxruntime JAR 은 linux-aarch64 / linux-x64 네이티브(C++)를 모두 번들한다.
 *
 * <p>텐서 조립 시 결측은 직전 유효값(LOCF)으로 채운다. 딥러닝 입력은 고정 차원의
 * 완전한 행렬이어야 하며, NaN 이 유입되면 재구성 손실이 폭증해 치명적 오탐을
 * 유발하기 때문이다 (PDF p.5).
 */
public class OnnxScorer extends KeyedProcessFunction<String, Reading, AnomalyScore> {

    public static final OutputTag<Alert> ALERT_TAG =
            new OutputTag<Alert>("ml-alerts", TypeInformation.of(Alert.class)) {};

    private final String modelPath;
    private final String metaPath;
    private final int steps;
    private final long inferenceIntervalMs;
    private final Double thresholdOverride;

    // ── 모델 메타 (학습 시 산출) ──
    private transient String[] tagOrder;
    private transient double[] mean;
    private transient double[] std;
    private transient double threshold;

    private transient OrtEnvironment env;
    private transient OrtSession session;
    private transient String inputName;

    /** 태그별 최신 관측치(직전 값 유지, LOCF) */
    private transient MapState<String, Double> latest;
    /** 아직 벡터로 만들지 않은 스캔: 순번 → (태그 → 값) */
    private transient MapState<Long, Map<String, Double>> pending;
    /** 스캔 순번 → 설비 시각(초) */
    private transient MapState<Long, Long> pendingPts;
    /** 스캔 순번 → 그 스캔의 첫 값이 도착한 처리 시각(ms) */
    private transient MapState<Long, Long> pendingAt;
    /** 슬라이딩 텐서 버퍼: step index → 12차원 벡터 */
    private transient MapState<Integer, double[]> window;
    private transient ValueState<Integer> filled;
    private transient ValueState<Long> lastEmittedSeq;
    private transient ValueState<Long> lastEmittedPts;
    private transient ValueState<String> siteState;
    /** 학습 표본 간격(설비 초). 창 안 스캔 간격이 이 값의 1.5배를 넘으면 창을 새로 시작한다 */
    private transient double sampleIntervalS;

    public OnnxScorer(String modelPath, String metaPath, int steps,
                      long inferenceIntervalMs, Double thresholdOverride) {
        this.modelPath = modelPath;
        this.metaPath = metaPath;
        this.steps = steps;
        this.inferenceIntervalMs = inferenceIntervalMs;
        this.thresholdOverride = thresholdOverride;
    }

    @Override
    public void open(OpenContext cfg) throws Exception {
        ObjectMapper om = new ObjectMapper();
        JsonNode meta = om.readTree(Files.readAllBytes(new File(metaPath).toPath()));

        List<String> tags = new ArrayList<>();
        meta.get("tags").forEach(n -> tags.add(n.asText()));
        tagOrder = tags.toArray(new String[0]);

        mean = readDoubles(meta.get("mean"));
        std = readDoubles(meta.get("std"));
        threshold = thresholdOverride != null ? thresholdOverride : meta.get("threshold").asDouble();

        env = OrtEnvironment.getEnvironment();
        OrtSession.SessionOptions opts = new OrtSession.SessionOptions();
        opts.setIntraOpNumThreads(1);   // Flink 슬롯당 1스레드 — 슬롯 간 CPU 경합 방지
        session = env.createSession(modelPath, opts);
        inputName = session.getInputNames().iterator().next();

        sampleIntervalS = meta.has("sample_interval_s") ? meta.get("sample_interval_s").asDouble() : 0.0;
        latest = getRuntimeContext().getMapState(
                new MapStateDescriptor<>("latest", Types.STRING, Types.DOUBLE));
        pending = getRuntimeContext().getMapState(
                new MapStateDescriptor<>("pending", Types.LONG, Types.MAP(Types.STRING, Types.DOUBLE)));
        pendingPts = getRuntimeContext().getMapState(
                new MapStateDescriptor<>("pendingPts", Types.LONG, Types.LONG));
        pendingAt = getRuntimeContext().getMapState(
                new MapStateDescriptor<>("pendingAt", Types.LONG, Types.LONG));
        window = getRuntimeContext().getMapState(
                new MapStateDescriptor<>("window", Types.INT, TypeInformation.of(double[].class)));
        filled = getRuntimeContext().getState(new ValueStateDescriptor<>("filled", Types.INT));
        lastEmittedSeq = getRuntimeContext().getState(new ValueStateDescriptor<>("lastSeq", Types.LONG));
        lastEmittedPts = getRuntimeContext().getState(new ValueStateDescriptor<>("lastPts", Types.LONG));
        siteState = getRuntimeContext().getState(new ValueStateDescriptor<>("site", Types.STRING));
    }

    private static double[] readDoubles(JsonNode n) {
        double[] a = new double[n.size()];
        for (int i = 0; i < a.length; i++) {
            a[i] = n.get(i).asDouble();
        }
        return a;
    }

    /**
     * 스캔 순번으로 벡터를 맞춘다(17번 K4: ML 입력 창만 설비 시각 기준). 한 스캔의 12태그가 다 오면 바로,
     * 덜 왔으면 다음·다다음 스캔이 올 때 또는 1.5초 뒤 직전 값(LOCF)으로 채워 벡터를 만든다.
     * 순번이 없는 보간값은 직전 값만 갱신한다. 규칙 탐지(SQL)는 벽시계 ts 기준이다.
     */
    @Override
    public void processElement(Reading in, Context ctx, Collector<AnomalyScore> out) throws Exception {
        if (siteState.value() == null) {
            siteState.update(in.site);
        }
        if (in.seq == null) {
            latest.put(in.tag, in.value);
            return;
        }
        Long last = lastEmittedSeq.value();
        if (last != null && in.seq <= last) {
            return;   // 이미 벡터로 만든 스캔의 늦은 값(재전송 등)
        }
        Map<String, Double> scan = pending.get(in.seq);
        if (scan == null) {
            scan = new HashMap<>();
            long now = ctx.timerService().currentProcessingTime();
            pendingAt.put(in.seq, now);
            ctx.timerService().registerProcessingTimeTimer(now + 1500);
        }
        scan.put(in.tag, in.value);
        pending.put(in.seq, scan);
        if (in.pts != null) {
            pendingPts.put(in.seq, in.pts);
        }
        // 이 스캔이 다 모였으면, 또는 두 스캔 이상 앞선 값이 왔으면 그 전 스캔까지 벡터로 만든다
        List<Long> ready = new ArrayList<>();
        for (Long s : pending.keys()) {
            if (s < in.seq - 1 || (s.equals(in.seq) && scan.size() >= tagOrder.length)) {
                ready.add(s);
            }
        }
        emitUpTo(ready, out, ctx);
    }

    @Override
    public void onTimer(long timestamp, OnTimerContext ctx, Collector<AnomalyScore> out) throws Exception {
        // 첫 값이 온 지 1.5초가 지난 스캔은 덜 모였어도 직전 값으로 채워 벡터로 만든다
        List<Long> ready = new ArrayList<>();
        for (Map.Entry<Long, Long> e : pendingAt.entries()) {
            if (e.getValue() + 1500 <= timestamp) {
                ready.add(e.getKey());
            }
        }
        emitUpTo(ready, out, ctx);
    }

    private void emitUpTo(List<Long> seqs, Collector<AnomalyScore> out, Context ctx) throws Exception {
        seqs.sort(Comparator.naturalOrder());
        for (Long s : seqs) {
            Map<String, Double> scan = pending.get(s);
            Long pts = pendingPts.get(s);
            pending.remove(s);
            pendingPts.remove(s);
            pendingAt.remove(s);
            if (scan == null) {
                continue;
            }
            for (Map.Entry<String, Double> e : scan.entrySet()) {
                latest.put(e.getKey(), e.getValue());
            }
            infer(s, pts, out, ctx);
        }
    }

    private void infer(long seq, Long pts, Collector<AnomalyScore> out, Context ctx) throws Exception {
        lastEmittedSeq.update(seq);
        // ── 12차원 벡터 조립 (결측은 LOCF, 한 번도 안 온 태그가 있으면 추론하지 않는다) ──
        double[] vec = new double[tagOrder.length];
        for (int i = 0; i < tagOrder.length; i++) {
            Double v = latest.get(tagOrder[i]);
            if (v == null) {
                return;
            }
            vec[i] = v;
        }
        // ── 창을 설비 시각으로 자른다: 스캔 간격이 학습 표본 간격의 1.5배를 넘으면(스캔 누락·재시작) 새로 채운다 ──
        Long prevPts = lastEmittedPts.value();
        if (pts != null) {
            if (prevPts != null && sampleIntervalS > 0 && (pts - prevPts > 1.5 * sampleIntervalS || pts < prevPts)) {
                window.clear();
                filled.update(0);
            }
            lastEmittedPts.update(pts);
        }
        // ── 슬라이딩 윈도우 전진 ──
        // 윈도우가 차기 전에는 뒤에 덧붙이기만 한다. 이 단계에서 좌측 시프트를 하면
        // 아직 기록되지 않은 슬롯을 읽어 MapState 에 null 을 넣게 된다
        // (RocksDB 상태 백엔드는 null 값을 거부한다).
        int n = filled.value() == null ? 0 : filled.value();
        if (n < steps) {
            window.put(n, vec);
            filled.update(n + 1);
            if (n + 1 < steps) {
                return;   // 윈도우가 아직 차지 않음
            }
        } else {
            for (int i = 0; i < steps - 1; i++) {
                window.put(i, window.get(i + 1));
            }
            window.put(steps - 1, vec);
        }

        // ── 정규화 후 평탄화: (steps × tags) → 1차원 입력 텐서 ──
        int dim = steps * tagOrder.length;
        float[] flat = new float[dim];
        for (int s = 0; s < steps; s++) {
            double[] row = window.get(s);
            for (int t = 0; t < tagOrder.length; t++) {
                double sd = std[t] > 1e-9 ? std[t] : 1.0;
                flat[s * tagOrder.length + t] = (float) ((row[t] - mean[t]) / sd);
            }
        }

        long t0 = System.nanoTime();
        float[] recon;
        try (OnnxTensor tensor = OnnxTensor.createTensor(env, new float[][]{flat});
             OrtSession.Result res = session.run(Map.of(inputName, tensor))) {
            recon = ((float[][]) res.get(0).getValue())[0];
        }
        double inferMs = (System.nanoTime() - t0) / 1_000_000.0;

        // ── 재구성 오차(MSE)와 센서별 기여도 ──
        double mse = 0.0;
        double[] perTag = new double[tagOrder.length];
        for (int i = 0; i < dim; i++) {
            double d = flat[i] - recon[i];
            mse += d * d;
            perTag[i % tagOrder.length] += d * d;
        }
        mse /= dim;

        AnomalyScore score = new AnomalyScore();
        score.ts = System.currentTimeMillis() * 1_000_000L;
        score.site = siteState.value();
        score.device = ctx.getCurrentKey();
        score.reconstruction_error = mse;
        score.threshold = threshold;
        score.is_anomaly = mse > threshold;
        score.inference_ms = Math.round(inferMs * 1000) / 1000.0;

        // ── 이상 기여도가 높은 센서 차원을 역추적 (PDF p.9) ──
        final double[] contrib = perTag;
        List<Integer> idx = new ArrayList<>();
        for (int i = 0; i < tagOrder.length; i++) {
            idx.add(i);
        }
        idx.sort(Comparator.comparingDouble((Integer i) -> contrib[i]).reversed());
        double total = 0.0;
        for (double c : contrib) {
            total += c;
        }
        final double denom = total > 1e-12 ? total : 1.0;
        String top = idx.stream().limit(3)
                .map(i -> String.format("%s(%.0f%%)", tagOrder[i], 100.0 * contrib[i] / denom))
                .collect(Collectors.joining(", "));
        score.top_contributors = top;

        score.seq = seq;
        score.pts = pts;
        out.collect(score);

        if (score.is_anomaly) {
            ctx.output(ALERT_TAG, new Alert(
                    score.ts, score.site, score.device, "MULTIVARIATE", mse,
                    "ML_AUTOENCODER", "WARNING", "TIER2_ML",
                    String.format("재구성오차 %.5f > 임계 %.5f · 기여 상위: %s · 추론 %.2fms",
                            mse, threshold, top, inferMs)));
        }
    }

    @Override
    public void close() throws Exception {
        if (session != null) {
            session.close();
        }
    }
}
