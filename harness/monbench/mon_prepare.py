"""monbench 설정 생성(호스트, 컨테이너 없이). V1 prometheus/prometheus.yml 을 읽어 4+2개 파일을 만든다.

    PYTHONUTF8=1 python harness/monbench/mon_prepare.py

conf/prometheus.{rot,standalone}.{v1,v2}.yml  — rot: V1 scrape_configs 그대로 / standalone: prometheus 자신만. v1: V1 rules.yml 만, v2: + rules.v2.yml
conf/vm-scrape.{rot,standalone}.yml          — VictoriaMetrics 용(같은 scrape_configs)
두 모드 모두 벤치 합성 대상 5개(synthetic-down·victim·detector-sim·cadvisor-next·kafka-next)를 덧붙인다.
"""
import pathlib

import yaml

HERE = pathlib.Path(__file__).resolve().parent
CONF = HERE / "conf"
v1 = yaml.safe_load(open(HERE.parents[1] / "prometheus" / "prometheus.yml", encoding="utf-8"))
BENCH_JOBS = [
    {"job_name": "synthetic-down", "static_configs": [{"targets": ["mon-nonexistent:9999"]}]},
    {"job_name": "victim", "static_configs": [{"targets": ["mon-victim:8080"]}]},
    {"job_name": "detector-sim", "static_configs": [{"targets": ["mon-detector:8080"]}]},
    {"job_name": "cadvisor-next", "static_configs": [{"targets": ["mon-cadvisor:8080"]}]},
    {"job_name": "kafka-next", "static_configs": [{"targets": ["mon-kafka-exporter:9308"]}]},
]
SELF = [j for j in v1["scrape_configs"] if j["job_name"] == "prometheus"]
HDR = {"rot": "# 전체 스택 모드: V1 prometheus/prometheus.yml 의 scrape_configs 그대로(rot-iiot 에 읽기로 붙어 같은 대상) + 벤치 합성 대상.\n",
       "standalone": "# 단독 모드: V1 대상 없이 벤치 합성 대상만(규칙 적재·발화·E11·자원). V1 잡은 prometheus 자신만.\n"}

for mode in ("rot", "standalone"):
    jobs = (v1["scrape_configs"] if mode == "rot" else SELF) + BENCH_JOBS
    for rs in ("v1", "v2"):
        cfg = {"global": v1["global"],
               "alerting": {"alertmanagers": [{"static_configs": [{"targets": ["mon-am:9093"]}]}]},
               "rule_files": ["/etc/prometheus/rules.yml"] + (["/etc/prometheus/rules.v2.yml"] if rs == "v2" else []),
               "scrape_configs": jobs}
        note = ("# 규칙: V1 prometheus/rules.yml 만(V1 그대로).\n" if rs == "v1"
                else "# 규칙: V1 rules.yml + V2 개선 후보 conf/rules.v2.yml(탐지 잡 0개).\n")
        (CONF / f"prometheus.{mode}.{rs}.yml").write_text(
            "# mon_prepare.py 가 생성(손으로 고치지 말 것). V1 과 차이: alertmanager=mon-am, 벤치 잡 5개.\n" + HDR[mode] + note
            + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")
    vm = {"global": {"scrape_interval": v1["global"]["scrape_interval"], "external_labels": v1["global"]["external_labels"]},
          "scrape_configs": [dict(j, static_configs=[{"targets": ["mon-vm:9090"]}]) if j["job_name"] == "prometheus" else j
                             for j in jobs]}
    (CONF / f"vm-scrape.{mode}.yml").write_text(f"# mon_prepare.py 생성. VictoriaMetrics -promscrape.config ({mode}). 규칙은 vmalert.\n"
                                                + yaml.safe_dump(vm, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")
print("generated", sorted(p.name for p in CONF.glob("*.yml")))
