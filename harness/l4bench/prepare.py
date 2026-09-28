"""V1 Flink 설정·SQL에서 L4 벤치용 사본을 만든다.

바꾸는 것은 토픽 이름(실험 전용), 메모리 크기(벤치 PC 여유), 호스트 이름뿐이다.
탐지 로직(SQL 본문, 워터마크, 윈도, 임계치)은 V1 파일을 그대로 쓴다.

  generated/    V1 Flink 1.20.1 (EXP-112a)  → 알람 토픽 exp.l4.alerts.flinksql
  generated22/  Flink 2.2.1     (EXP-112)   → 알람 토픽 exp.l4.alerts.flink22, 호스트 flink22-*
  generated23/  Flink 2.3.0     (stage2 P1) → 알람 토픽 exp.l4.alerts.flink23, 호스트 flink23-*
  generatedha/  HA-A: ZooKeeper HA + 세션      → exp.l4.alerts.flinkha
  generatedhac/ HA-C: HA 없음 + 보존 체크포인트 + 재제출 스크립트(recover_hac.sh) → exp.l4.alerts.flinkhac
  generatedhad/ HA-D: HA 없음 + Kafka group-offsets 재개(SQL 잡만) → exp.l4.alerts.flinkhad
  generatedcep23/ Flink 2.3.0 + DataStream CEP(01~03 SQL + cep-job) → exp.l4.alerts.cep, 호스트 flinkcep23-*
  generatedhab/ HA-B: ZooKeeper HA + 애플리케이션 모드. 클러스터 2개(sql·onnx)라 config-sql.yaml·config-onnx.yaml 과
                app.sql(01~04 합본)을 만든다 → exp.l4.alerts.flinkhab
각 변형은 V1 ONNX 잡 설정(flink/onnx-job/job.properties)의 사본도 받는다. 토픽만 후보별로 바꾼다
(clean → exp.l4.clean.<후보>, score → exp.l4.score.<후보>, ML 알람 → 후보 알람 토픽). 보간·창·임계치 값은 V1 그대로.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent

# 자동 복구 후보에 덧붙이는 설정: Flink 고가용성(ZooKeeper). JobManager 재시작 시 잡을 마지막 체크포인트에서 복구
HA_EXTRA = """
# ── 자동 복구 후보: Flink 고가용성(ZooKeeper) ──
high-availability:
  type: zookeeper
  # 이미지에서 flink 사용자 소유로 만들어 둔 체크포인트 볼륨 안에 둔다(별도 명명 볼륨은 root 소유라 JM 이 못 쓴다)
  storageDir: file:///opt/flink/checkpoints/ha
  cluster-id: /l4bench-flinkha
  zookeeper:
    quorum: zookeeper:2181
    path:
      root: /flink
"""

VARIANTS = {
    "generated": {"alerts": "exp.l4.alerts.flinksql", "host": "flink", "group": "flink-tier1"},
    "generated22": {"alerts": "exp.l4.alerts.flink22", "host": "flink22", "group": "flink22-tier1"},
    # EXP-111: 전용 2.2.1 클러스터에 01~03 SQL(임계치·Z-Score) + DataStream CEP 잡. 04(SQL CEP)는 제출하지 않는다.
    "generatedcep": {"alerts": "exp.l4.alerts.cep", "host": "flinkcep", "group": "flinkcep-tier1"},
    # 이상탐지 자동 복구 후보: 같은 V1 SQL + 현업 표준 Flink HA(ZooKeeper) + JM·TM 공유 체크포인트 저장소
    "generatedha": {"alerts": "exp.l4.alerts.flinkha", "host": "flinkha", "group": "flinkha-tier1",
                    "extra": HA_EXTRA},
    # stage2 P1: 같은 제품 최신 Flink 2.3.0 (Kafka 커넥터 5.0.0-2.2 비공식 조합)
    "generated23": {"alerts": "exp.l4.alerts.flink23", "host": "flink23", "group": "flink23-tier1"},
    # HA-C: HA 없음. 보존 체크포인트(V1 설정 RETAIN_ON_CANCELLATION 그대로)에서 재제출 스크립트로 복구
    "generatedhac": {"alerts": "exp.l4.alerts.flinkhac", "host": "flinkhac", "group": "flinkhac-tier1"},
    # HA-D: HA 없음. SQL 소스를 group-offsets 로(처음은 latest) → 재제출 시 건너뛰지 않고 이어 읽음(윈도 상태는 잃음)
    "generatedhad": {"alerts": "exp.l4.alerts.flinkhad", "host": "flinkhad", "group": "flinkhad-tier1",
                     "startup": "group-offsets"},
    # 2.3 DataStream CEP: 같은 CEP 잡 소스를 2.3.0 으로 빌드(l4bench-flink23 이미지). 알람 토픽은 2.2 판과 같은 cep
    "generatedcep23": {"alerts": "exp.l4.alerts.cep", "host": "flinkcep23", "group": "flinkcep23-tier1"},
    # HA-B: 애플리케이션 클러스터 2개. config.yaml 은 sql 클러스터 기준, 아래 build_hab 가 클러스터별 파일을 따로 만든다
    "generatedhab": {"alerts": "exp.l4.alerts.flinkhab", "host": "flinkhab-sql", "group": "flinkhab-tier1",
                     "extra": HA_EXTRA.replace("/l4bench-flinkha", "/l4bench-flinkhab-sql")},
}


def build_hab():
    """HA-B: 클러스터별 설정(주소·HA cluster-id)과 SQL 합본. 탐지 SQL 은 generatedhab/sql 의 V1 사본 그대로."""
    out = HERE / "generatedhab"
    base = (out / "config.yaml").read_text(encoding="utf-8")
    (out / "config-sql.yaml").write_text(base, encoding="utf-8")
    onnx = (base.replace("address: flinkhab-sql-jobmanager", "address: flinkhab-onnx-jobmanager")
                .replace("host: flinkhab-sql-taskmanager", "host: flinkhab-onnx-taskmanager")
                .replace("/l4bench-flinkhab-sql", "/l4bench-flinkhab-onnx"))
    assert onnx.count("flinkhab-onnx") == 3, onnx.count("flinkhab-onnx")
    (out / "config-onnx.yaml").write_text(onnx, encoding="utf-8")
    parts = [(out / "sql" / n).read_text(encoding="utf-8")
             for n in ("01_sources.sql", "02_tier1_rules.sql", "03_tier1_zscore.sql", "04_tier1_cep.sql")]
    (out / "sql" / "app.sql").write_text("\n".join(parts), encoding="utf-8")
    print("generatedhab: config-sql.yaml·config-onnx.yaml·sql/app.sql")


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
        if v.get("startup") == "group-offsets" and "'scan.startup.mode' = 'latest-offset'" in text:
            text = text.replace("'scan.startup.mode' = 'latest-offset'",
                                "'scan.startup.mode' = 'group-offsets',\n    'properties.auto.offset.reset' = 'latest'")
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
    (out / "config.yaml").write_text(rehost(config) + v.get("extra", ""), encoding="utf-8")
    (out / "client-config.yaml").write_text(
        rehost((ROOT / "flink" / "conf" / "client-config.yaml").read_text(encoding="utf-8")), encoding="utf-8")

    leftover = [p.name for p in (out / "sql").glob("*.sql")
                if any(f"'{t}'" in p.read_text(encoding="utf-8") for t in topics)]
    assert not leftover, f"원본 토픽이 남은 SQL: {leftover}"
    suffix = v["alerts"].rsplit(".", 1)[1]
    props = (ROOT / "flink" / "onnx-job" / "job.properties").read_text(encoding="utf-8")
    subs = {"sensor.telemetry.raw": "exp.l4.raw", "sensor.telemetry.clean": f"exp.l4.clean.{suffix}",
            "sensor.anomaly.score": f"exp.l4.score.{suffix}", "sensor.alerts": v["alerts"],
            "flink-tier2-onnx": f"{v['host']}-tier2-onnx"}
    for old, new in subs.items():
        props, n = re.subn(rf"= {re.escape(old)}\n", f"= {new}\n", props)
        assert n == 1, (old, n)
    (out / "job.properties").write_text(props, encoding="utf-8")
    print(f"{outdir}: alerts={v['alerts']} host={v['host']}-* | JM 800m, TM 1600m, slots 8 (V1 동일)")


def main():
    for outdir, v in VARIANTS.items():
        build(outdir, v)
    build_hab()


if __name__ == "__main__":
    main()
