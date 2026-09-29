package org.uengine.iiot;

/** sensor.anomaly.score 토픽 스키마. 재구성 오차와 기여도 상위 센서를 함께 싣는다. */
public class AnomalyScore {
    public long ts;
    public String site;
    public String device;
    public double reconstruction_error;
    public double threshold;
    public boolean is_anomaly;
    /** 오차 기여도 상위 센서 (역추적 결과) */
    public String top_contributors;
    public double inference_ms;

    public AnomalyScore() {}
}
