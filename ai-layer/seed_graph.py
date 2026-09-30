"""지식 그래프 시드(기동 때 1회, 멱등) — 빈 Neo4j 에서도 V1 과 같은 교육용 그래프가 생기게 한다.

번들 A(등록부 인벤토리 + 교육 문서 + 검토한 설비 관계), B(고장 지식 문서 ↔ 설비), C(고장 온톨로지 v2)를
검토·게시 모듈(review.publish, LLM 없음)로 넣는다. 같은 묶음은 digest 가 같아 다시 넣어도 중복되지 않는다.
    python ai-layer/seed_graph.py        (knowledge 이미지 안, 저장소가 /repo 에 읽기 전용으로 붙은 상태)
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# 빈 DB 에 처음 게시할 때 드라이버가 "아직 없는 라벨·속성" 알림을 쏟아낸다(정상). 시드 로그에서는 끈다.
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-layer"))

from backend.src.modules.ontology.review import Batch, Publish, publish  # noqa: E402  (이미지의 백엔드 코드)
import build_knowledge_bundle  # noqa: E402
import build_ontology_bundle  # noqa: E402


def main() -> int:
    bundles = [("A 등록부·교육 문서", build_knowledge_bundle.build()),
               ("B 고장 지식 문서", build_ontology_bundle.arm_b()),
               ("C 고장 온톨로지", build_ontology_bundle.arm_c())]
    for attempt in range(30):
        try:
            for name, data in bundles:
                batch = Batch.model_validate(data)
                result = publish(Publish(batch=batch, expected_sha256=batch.digest(), review_note=f"기동 시드: {name}"))
                print(f"[graph-seed] {name}: {'이미 있음' if result.get('duplicate') else '게시'} "
                      f"(노드 {len(batch.nodes)}, 관계 {len(batch.relationships)}, {result['sha256'][:12]})", flush=True)
            return 0
        except Exception as exc:  # Neo4j 가 막 떴을 때의 연결 오류만 다시 시도한다
            if "ServiceUnavailable" not in type(exc).__name__ and "Connection" not in type(exc).__name__:
                raise
            print(f"[graph-seed] Neo4j 대기({attempt + 1}): {type(exc).__name__}", flush=True)
            time.sleep(2)
    return 1


if __name__ == "__main__":
    sys.exit(main())
