package org.uengine.iiot;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

/** 파이프라인 전 구간 공통 스키마. Kafka 의 telemetry.raw / telemetry.clean 양쪽에 쓰인다. */
@JsonIgnoreProperties(ignoreUnknown = true)
public class Reading {
    public long ts;              // 나노초 epoch
    public String site;
    public String device;
    public String tag;
    public double value;
    /** GOOD | INTERPOLATED_LOCF | INTERPOLATED_LINEAR */
    public String quality = "GOOD";

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
