# m3 무효 — 측정기 결함 2건 (2026-09-28)
- 정확도는 유효 정보: 4후보(1.20 SQL·2.2 SQL·2.2 DataStream CEP·Python) 모두 70/70, 알람 258건 상호 차이 0.
- 결함 1: DataStream CEP 지연 −1ms. Flink DataStream KafkaSink 는 레코드 타임스탬프를 이벤트 시각으로 찍고 SQL 싱크는 기록 시각을 찍어, CreateTime 기준 지연이 후보마다 다른 의미가 됨. → 알람 토픽을 LogAppendTime 으로 재생성.
- 결함 2: Flink 1.20 지연 p95 47s·CPU 93%. 유휴 시 Kafka CPU 205% — 벤치 Kafka 힙 384m GC 과부하로 판단. → 힙 768m, 벤치 전체 재기동.
- 판정에 쓰지 않는다. 재측정 m4·m5.
