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
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;
import org.apache.flink.util.OutputTag;

import java.io.File;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Comparator;
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

    /** 태그별 최신 관측치 */
    private transient MapState<String, Double> latest;
    /** 슬라이딩 텐서 버퍼: step index → 12차원 벡터 */
    private transient MapState<Integer, double[]> window;
    private transient ValueState<Integer> filled;
    private transient ValueState<Long> nextFireMs;
    private transient ValueState<String> siteState;

    public OnnxScorer(String modelPath, String metaPath, int steps,
                      long inferenceIntervalMs, Double thresholdOverride) {
        this.modelPath = modelPath;
        this.metaPath = metaPath;
        this.steps = steps;
        this.inferenceIntervalMs = inferenceIntervalMs;
        this.thresholdOverride = thresholdOverride;
    }

    @Override
    public void open(Configuration cfg) throws Exception {
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

        latest = getRuntimeContext().getMapState(
                new MapStateDescriptor<>("latest", Types.STRING, Types.DOUBLE));
        window = getRuntimeContext().getMapState(
                new MapStateDescriptor<>("window", Types.INT, TypeInformation.of(double[].class)));
        filled = getRuntimeContext().getState(new ValueStateDescriptor<>("filled", Types.INT));
        nextFireMs = getRuntimeContext().getState(new ValueStateDescriptor<>("nextFire", Types.LONG));
        siteState = getRuntimeContext().getState(new ValueStateDescriptor<>("site", Types.STRING));
    }

    private static double[] readDoubles(JsonNode n) {
        double[] a = new double[n.size()];
        for (int i = 0; i < a.length; i++) {
            a[i] = n.get(i).asDouble();
        }
        return a;
    }

    @Override
    public void processElement(Reading in, Context ctx, Collector<AnomalyScore> out) throws Exception {
        latest.put(in.tag, in.value);
        if (siteState.value() == null) {
            siteState.update(in.site);
        }
        // 처리시간 타이머로 고정 주기 텐서를 만든다. 센서마다 도착 시각이 미세하게
        // 다르므로 이벤트 단위로 추론하면 같은 시점이 중복 평가된다.
        if (nextFireMs.value() == null) {
            long fire = ctx.timerService().currentProcessingTime() + inferenceIntervalMs;
            nextFireMs.update(fire);
            ctx.timerService().registerProcessingTimeTimer(fire);
        }
    }

    @Override
    public void onTimer(long timestamp, OnTimerContext ctx, Collector<AnomalyScore> out) throws Exception {
        long next = timestamp + inferenceIntervalMs;
        nextFireMs.update(next);
        ctx.timerService().registerProcessingTimeTimer(next);

        // ── 12차원 벡터 조립 (결측은 LOCF, 미관측 태그는 학습 평균으로 대체) ──
        double[] vec = new double[tagOrder.length];
        int seen = 0;
        for (int i = 0; i < tagOrder.length; i++) {
            Double v = latest.get(tagOrder[i]);
            if (v != null) {
                vec[i] = v;
                seen++;
            } else {
                vec[i] = mean[i];
            }
        }
        if (seen < tagOrder.length) {
            return;   // 전 태그가 한 번은 관측되기 전에는 추론하지 않는다
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
