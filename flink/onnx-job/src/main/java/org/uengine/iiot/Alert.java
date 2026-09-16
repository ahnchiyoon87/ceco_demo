package org.uengine.iiot;

/** sensor.alerts 토픽 스키마. Flink SQL 의 Tier-1 알람과 동일 구조를 유지한다. */
public class Alert {
    public long ts;
    public String site;
    public String device;
    public String tag;
    public double value;
    public String alert_type;
    public String severity;
    public String detector;
    public String detail;

    public Alert() {}

    public Alert(long ts, String site, String device, String tag, double value,
                 String alertType, String severity, String detector, String detail) {
        this.ts = ts;
        this.site = site;
        this.device = device;
        this.tag = tag;
        this.value = value;
        this.alert_type = alertType;
        this.severity = severity;
        this.detector = detector;
        this.detail = detail;
    }
}
