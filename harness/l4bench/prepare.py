"""V1 Flink 설정·SQL에서 L4 벤치용 사본을 만든다.

바꾸는 것은 토픽 이름(실험 전용), 메모리 크기(벤치 PC 여유), Kafka 주소뿐이다.
탐지 로직(SQL 본문, 워터마크, 윈도, 임계치)은 V1 파일을 그대로 쓴다.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent / "generated"

TOPICS = {
    "sensor.telemetry.raw": "exp.l4.raw",
    "sensor.telemetry.clean": "exp.l4.clean",
    "sensor.alerts": "exp.l4.alerts.flinksql",
}


def main():
    (OUT / "sql").mkdir(parents=True, exist_ok=True)
    for src in sorted((ROOT / "flink" / "sql").glob("*")):
        text = src.read_text(encoding="utf-8")
        for old, new in TOPICS.items():
            text = text.replace(f"'{old}'", f"'{new}'")
        (OUT / "sql" / src.name).write_text(text, encoding="utf-8")

    config = (ROOT / "flink" / "conf" / "config.yaml").read_text(encoding="utf-8")
    config, n_jm = re.subn(r"(jobmanager:\n(?:.*\n)*?\s+process:\n\s+size:) \S+", r"\1 800m", config, count=1)
    # 슬롯 수는 V1(8)을 그대로 둔다: SQL 잡 3개 × 병렬도 2 = 6 슬롯이 필요 (4로 줄였던 r1 은 CEP 잡이 슬롯 부족으로 실패)
    config, n_tm = re.subn(r"(taskmanager:\n(?:.*\n)*?\s+process:\n\s+size:) \S+", r"\1 1600m", config, count=1)
    n_slots = config.count("numberOfTaskSlots: 8")
    assert (n_jm, n_tm, n_slots) == (1, 1, 1), (n_jm, n_tm, n_slots)
    (OUT / "config.yaml").write_text(config, encoding="utf-8")
    (OUT / "client-config.yaml").write_text(
        (ROOT / "flink" / "conf" / "client-config.yaml").read_text(encoding="utf-8"), encoding="utf-8")

    changed = [p.name for p in (OUT / "sql").glob("*.sql")
               if any(t in (OUT / "sql" / p.name).read_text(encoding="utf-8") for t in TOPICS.values())]
    leftover = [p.name for p in (OUT / "sql").glob("*.sql")
                if any(f"'{t}'" in p.read_text(encoding="utf-8") for t in TOPICS)]
    assert not leftover, f"원본 토픽이 남은 SQL: {leftover}"
    print("sql:", sorted(changed), "| config: JM 800m, TM 1600m, slots 8 (V1 동일)")


if __name__ == "__main__":
    main()
