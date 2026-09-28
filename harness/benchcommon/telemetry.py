"""V1 모양 텔레메트리·알람 생성기 (측정 도구 — 솔루션 부품 아님).

레코드는 harness/SCHEMA.md §3 raw 와 같다: {"ts"(ns), "site", "device", "tag", "value", "quality"}.
측정용 추가 필드(SCHEMA §4, 기존 소비자는 무시): "seq"(태그·장치별 1부터), "emit_ns"(발행 시각 ns).
값은 plant.yaml 정상 범위 안의 결정적 함수(재현 가능). 이상 주입이 아니라 적재·전달 동작을 재기 위한 값이다.
"""
from __future__ import annotations

import json
import math

SITE = "AR-100"
DEVICE0 = "reactor-line-01"
# plant.yaml 순서·단위. (정상 중심값, 진폭)
TAGS = {
    "LT-101": (60.0, 5.0), "LT-102": (53.0, 4.0), "TT-101": (70.0, 3.0), "TT-102": (85.0, 4.0),
    "PT-101": (3.2, 0.3), "FT-101": (12.0, 1.0), "FT-102": (11.8, 1.0), "IT-101": (9.0, 0.6),
    "IT-102": (8.0, 0.4), "VT-101": (3.0, 0.5), "pH-101": (7.2, 0.2), "CT-101": (1.8, 0.1),
}
TAG_NAMES = list(TAGS)
# V1 alerts 레코드(SCHEMA §3) 예시 모양
ALERT_TYPES = ["THRESHOLD_USL", "THRESHOLD_LSL", "ZSCORE", "CEP_BEARING", "ML_AUTOENCODER"]


def devices(n: int) -> list[str]:
    """N=1 이면 V1 과 같은 장치 하나. N>1 이면 reactor-line-01..N."""
    return [DEVICE0] if n <= 1 else [f"reactor-line-{i:02d}" for i in range(1, n + 1)]


def value(tag: str, t_s: float, dev_idx: int = 0) -> float:
    c, a = TAGS[tag]
    k = TAG_NAMES.index(tag)
    return round(c + a * math.sin(t_s / (60.0 + 7 * k) + dev_idx) + 0.1 * a * math.sin(t_s / 3.1 + k), 4)


def record(tag: str, device: str, ts_ns: int, seq: int, emit_ns: int | None = None, dev_idx: int = 0) -> dict:
    r = {"ts": ts_ns, "site": SITE, "device": device, "tag": tag,
         "value": value(tag, ts_ns / 1e9, dev_idx), "quality": "GOOD", "seq": seq}
    if emit_ns is not None:
        r["emit_ns"] = emit_ns
    return r


def encode(r: dict) -> bytes:
    return json.dumps(r, separators=(",", ":")).encode()


def key_of(r: dict) -> str:
    """V1 파티션 키 = tag (SCHEMA §3). 장치가 여럿이면 device/tag."""
    return r["tag"] if r["device"] == DEVICE0 else f'{r["device"]}/{r["tag"]}'


def pct(values, q):
    v = sorted(values)
    if not v:
        return None
    return round(v[min(len(v) - 1, int(round(q * (len(v) - 1))))], 3)


def check_stream(expected: dict, received: list[tuple[str, int]]):
    """expected: {stream_key: last_seq}. received: [(stream_key, seq), ...] 도착 순서.
    반환: 유실·중복·순서 뒤바뀜(키별 seq 감소) 수."""
    seen: dict[str, set] = {}
    last: dict[str, int] = {}
    dup = reorder = 0
    for k, s in received:
        st = seen.setdefault(k, set())
        if s in st:
            dup += 1
            continue
        st.add(s)
        if s < last.get(k, 0):
            reorder += 1
        last[k] = max(last.get(k, 0), s)
    lost = sum(n - len(seen.get(k, ())) for k, n in expected.items())
    return {"expected": sum(expected.values()), "received_unique": sum(len(v) for v in seen.values()),
            "lost": lost, "duplicates": dup, "reordered_within_key": reorder}
