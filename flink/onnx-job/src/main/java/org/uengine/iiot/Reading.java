package org.uengine.iiot;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;

/** 파이프라인 전 구간 공통 스키마. Kafka 의 telemetry.raw / telemetry.clean 양쪽에 쓰인다. */
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
public class Reading {
    public long ts;              // 나노초 epoch
    public String site;
    public String device;
    public String tag;
    public double value;
    /** GOOD | INTERPOLATED_LOCF | INTERPOLATED_LINEAR */
    public String quality = "GOOD";
    /** 현장 장치 스캔 순번·설비 시각(초). 원시값에만 있고 보간값에는 없다(ML 입력 창을 스캔에 맞추는 기준, 17번 K4) */
    public Long seq;
    public Long pts;

    public Reading() {}

    public Reading(long ts, String site, String device, String tag, double value, String quality) {
        this.ts = ts;
        this.site = site;
        this.device = device;
        this.tag = tag;
        this.value = value;
        this.quality = quality;
    }

    public long millis() {
        return ts / 1_000_000L;
    }
}
