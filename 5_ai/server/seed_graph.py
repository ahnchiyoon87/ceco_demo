"""지식 그래프 시드(기동 때 1회, 멱등) — 빈 Neo4j 에서도 교육용 그래프와 검색용 벡터가 생기게 한다.

1) 번들 A(등록부 인벤토리 + 교육 문서 + 검토한 설비 관계), B(고장 지식 문서 ↔ 설비), C(고장 온톨로지 v2)를
   검토·게시 모듈(review.publish)로 넣는다. 같은 묶음은 digest 가 같아 다시 넣어도 중복되지 않는다.
2) LLM 게이트웨이(OPENAI_BASE_URL·OPENAI_API_KEY = GCP LiteLLM)가 설정돼 있으면 매뉴얼 절과 온톨로지 개체를
   EMBEDDING_MODEL 로 임베딩하고 벡터 색인을 만든다(바뀐 것만). 빠진 벡터나 0 벡터가 남으면 실패로 끝낸다.
   설정이 없으면(키 파일 없는 복제본) 임베딩을 건너뛴다고 알린다.
    python 5_ai/server/seed_graph.py        (knowledge 이미지 안, 저장소가 /repo 에 읽기 전용으로 붙은 상태)
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# 빈 DB 에 처음 게시할 때 드라이버가 "아직 없는 라벨·속성" 알림을 쏟아낸다(정상). 시드 로그에서는 끈다.
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "5_ai" / "server"))

from backend.src.modules.ontology.review import Batch, Publish, publish  # noqa: E402  (이미지의 백엔드 코드)
import build_knowledge_bundle  # noqa: E402
import build_ontology_bundle  # noqa: E402


def embed() -> int:
    if not (os.environ.get("OPENAI_BASE_URL") and os.environ.get("OPENAI_API_KEY")):
        print("[graph-seed] 임베딩 건너뜀: LLM 게이트웨이 설정 없음(5_ai/server/.env.local). 매뉴얼 검색은 설정 뒤 다시 기동하면 된다", flush=True)
        return 0
    from backend.src.modules.ontology.embedding import _get_dimensions
    from backend.src.modules.ontology.tools import _embed_entity_nodes, _run_query
    from backend.src.modules.operations.fault_ontology import index_sections
    sections = index_sections()
    entities = 0
    while (n := _embed_entity_nodes()) > 0:
        entities += n
    dims = _get_dimensions()
    left = _run_query("""MATCH (n:_Entity) WHERE n.embedding IS NULL OR size(n.embedding) <> $d RETURN count(n) AS n""", {"d": dims})[0]["n"]
    left += _run_query("""MATCH (d:DocumentSection) WHERE d.content IS NOT NULL AND d.v2_embedding IS NULL RETURN count(d) AS n""")[0]["n"]
    zero = _run_query("""MATCH (n) WHERE (n:_Entity AND n.embedding IS NOT NULL AND all(x IN n.embedding WHERE x = 0.0))
                         OR (n:DocumentSection AND n.v2_embedding IS NOT NULL AND all(x IN n.v2_embedding WHERE x = 0.0))
                         RETURN count(n) AS n""")[0]["n"]
    print(f"[graph-seed] 임베딩({os.environ.get('EMBEDDING_MODEL')}, {dims}차원): 매뉴얼 절 새로 {sections['embedded']}, "
          f"개체 새로 {entities} / 빠진 벡터 {left} · 0 벡터 {zero}", flush=True)
    return 0 if left == 0 and zero == 0 else 1


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
            return embed()
        except Exception as exc:  # Neo4j 가 막 떴을 때의 연결 오류만 다시 시도한다
            if "ServiceUnavailable" not in type(exc).__name__ and "Connection" not in type(exc).__name__:
                raise
            print(f"[graph-seed] Neo4j 대기({attempt + 1}): {type(exc).__name__}", flush=True)
            time.sleep(2)
    return 1


if __name__ == "__main__":
    sys.exit(main())
