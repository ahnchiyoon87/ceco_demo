"""V1 Flink 설정·SQL에서 L4 벤치용 사본을 만든다.

바꾸는 것은 토픽 이름(실험 전용), 메모리 크기(벤치 PC 여유), 호스트 이름뿐이다.
탐지 로직(SQL 본문, 워터마크, 윈도, 임계치)은 V1 파일을 그대로 쓴다.

  generated/    V1 Flink 1.20.1 (EXP-112a)  → 알람 토픽 exp.l4.alerts.flinksql
  generated22/  Flink 2.2.1     (EXP-112)   → 알람 토픽 exp.l4.alerts.flink22, 호스트 flink22-*
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent

VARIANTS = {
    "generated": {"alerts": "exp.l4.alerts.flinksql", "host": "flink", "group": "flink-tier1"},
    "generated22": {"alerts": "exp.l4.alerts.flink22", "host": "flink22", "group": "flink22-tier1"},
}


def build(outdir, v):
    out = HERE / outdir
    topics = {"sensor.telemetry.raw": "exp.l4.raw", "sensor.telemetry.clean": "exp.l4.clean",
              "sensor.alerts": v["alerts"]}
    (out / "sql").mkdir(parents=True, exist_ok=True)
    for src in sorted((ROOT / "flink" / "sql").glob("*")):
        text = src.read_text(encoding="utf-8")
        for old, new in topics.items():
            text = text.replace(f"'{old}'", f"'{new}'")
        text = text.replace("'properties.group.id' = 'flink-tier1'", f"'properties.group.id' = '{v['group']}'")
        (out / "sql" / src.name).write_text(text, encoding="utf-8")

    def rehost(text):
        return (text.replace("address: flink-jobmanager", f"address: {v['host']}-jobmanager")
                    .replace("host: flink-taskmanager", f"host: {v['host']}-taskmanager"))

    config = (ROOT / "flink" / "conf" / "config.yaml").read_text(encoding="utf-8")
    config, n_jm = re.subn(r"(jobmanager:\n(?:.*\n)*?\s+process:\n\s+size:) \S+", r"\1 800m", config, count=1)
    # 슬롯 수는 V1(8)을 그대로 둔다: SQL 잡 3개 × 병렬도 2 = 6 슬롯이 필요 (4로 줄였던 r1 은 CEP 잡이 슬롯 부족으로 실패)
    config, n_tm = re.subn(r"(taskmanager:\n(?:.*\n)*?\s+process:\n\s+size:) \S+", r"\1 1600m", config, count=1)
    n_slots = config.count("numberOfTaskSlots: 8")
    assert (n_jm, n_tm, n_slots) == (1, 1, 1), (n_jm, n_tm, n_slots)
    (out / "config.yaml").write_text(rehost(config), encoding="utf-8")
    (out / "client-config.yaml").write_text(
        rehost((ROOT / "flink" / "conf" / "client-config.yaml").read_text(encoding="utf-8")), encoding="utf-8")

    leftover = [p.name for p in (out / "sql").glob("*.sql")
                if any(f"'{t}'" in p.read_text(encoding="utf-8") for t in topics)]
    assert not leftover, f"원본 토픽이 남은 SQL: {leftover}"
    print(f"{outdir}: alerts={v['alerts']} host={v['host']}-* | JM 800m, TM 1600m, slots 8 (V1 동일)")


def main():
    for outdir, v in VARIANTS.items():
        build(outdir, v)


if __name__ == "__main__":
    main()
