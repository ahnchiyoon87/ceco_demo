package org.uengine.iiot;

import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.api.common.functions.OpenContext;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;

/**
 * 태그 단위 결측치 보간 (PDF p.5 표의 LOCF / 선형 보간 구현).
 *
 * <p>상태는 태그별로 유지되며 RocksDB 백엔드에 저장되므로 TaskManager 가 죽어도
 * 체크포인트에서 정확히 한 번 복구된다 (PDF p.6).
 *
 * <p>중요 — 무결성 원칙: 보간값은 절대 원본을 덮어쓰지 않는다.
 * 원본은 sensor.telemetry.raw 에 그대로 남고, 이 연산자의 출력(clean)에서만
 * 보간값이 채워지며 quality 필드로 추정치임이 명시된다. 그래야 사고 발생 시
 * 감사 추적에서 실측치와 추정치를 구분할 수 있다 (PDF p.5).
 */
public class Interpolator extends KeyedProcessFunction<String, Reading, Reading> {

    private final String mode;          // "linear" | "locf"
    private final long maxGapMs;
    private final long scanIntervalMs;

    private transient ValueState<Reading> lastGood;
    private transient ValueState<Long> lastEmittedTsNs;   // 중복 제거용

    public Interpolator(String mode, long maxGapMs, long scanIntervalMs) {
        this.mode = mode;
        this.maxGapMs = maxGapMs;
        this.scanIntervalMs = Math.max(scanIntervalMs, 1);
    }

    @Override
    public void open(OpenContext cfg) {
        lastGood = getRuntimeContext().getState(
                new ValueStateDescriptor<>("lastGood", TypeInformation.of(Reading.class)));
        lastEmittedTsNs = getRuntimeContext().getState(
                new ValueStateDescriptor<>("lastEmittedTs", TypeInformation.of(Long.class)));
    }

    @Override
    public void processElement(Reading in, Context ctx, Collector<Reading> out) throws Exception {
        // ── 멱등 처리: MQTT QoS1 재전송으로 인한 중복을 (tag, ts) 기준으로 제거 ──
        //    (PDF p.4 — QoS2 대신 QoS1 + 스트림 계층 멱등성)
        Long lastTs = lastEmittedTsNs.value();
        if (lastTs != null && in.ts <= lastTs) {
            return;
        }

        Reading prev = lastGood.value();
        if (prev != null) {
            long gapMs = in.millis() - prev.millis();
            // 스캔 주기의 1.5배를 넘으면 결측 구간으로 판정
            if (gapMs > scanIntervalMs * 1.5) {
                emitFill(prev, in, gapMs, out);
            }
        }

        out.collect(in);
        lastGood.update(in);
        lastEmittedTsNs.update(in.ts);
    }

    /** 결측 구간을 채운다. 공백이 너무 길면 선형 보간을 포기하고 LOCF 로 대체한다. */
    private void emitFill(Reading prev, Reading next, long gapMs, Collector<Reading> out) {
        int missing = (int) Math.round((double) gapMs / scanIntervalMs) - 1;
        if (missing <= 0) {
            return;
        }
        // 폭주 방지: 장시간 단절 시 무한정 채우지 않는다
        boolean useLinear = "linear".equalsIgnoreCase(mode) && gapMs <= maxGapMs;
        String quality = useLinear ? "INTERPOLATED_LINEAR" : "INTERPOLATED_LOCF";
        int cap = (int) Math.min(missing, maxGapMs / scanIntervalMs);

        for (int i = 1; i <= cap; i++) {
            long tsNs = prev.ts + (long) i * scanIntervalMs * 1_000_000L;
            double v;
            if (useLinear) {
                // 시간차에 비례한 선형 보간 (PDF p.5 — 온도·레벨 등 연속 물리량에 타당)
                double frac = (double) i / (missing + 1);
                v = prev.value + (next.value - prev.value) * frac;
            } else {
                // 직전 관측치 유지 (LOCF)
                v = prev.value;
            }
            out.collect(new Reading(tsNs, prev.site, prev.device, prev.tag, v, quality));
        }
    }
}
