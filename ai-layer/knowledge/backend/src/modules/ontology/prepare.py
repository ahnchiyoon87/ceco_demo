"""Deterministic source preparation via Ontology Studio's real upload workspace.

This extracts explicit configuration/document structure. It does not pretend to
infer asset membership, diagnose equipment, or replace model-assisted modelling.
"""
import hashlib
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import yaml

from ..files.service import list_local_upload_files, get_local_upload_root
from .inventory import export_inventory
from .review import Batch, preview

router = APIRouter(prefix="/api/knowledge", tags=["knowledge-preparation"])


class Prepare(BaseModel):
    filenames: list[str] = Field(min_length=1, max_length=20)


@router.post("/prepare")
def prepare(request: Prepare):
    known = {path.name: path for path in list_local_upload_files()}
    if len(set(request.filenames)) != len(request.filenames):
        raise HTTPException(422, "같은 파일을 중복 선택했습니다.")
    batch = {"nodes": [], "relationships": [], "unresolved": []}
    root = get_local_upload_root().resolve()
    for name in request.filenames:
        path = known.get(name)
        if not path or path.resolve().parent != root:
            raise HTTPException(404, "등록된 원본 파일을 찾을 수 없습니다.")
        if path.stat().st_size > 2*1024*1024:
            raise HTTPException(413, "이 구조 추출기의 파일 한도는 2MB입니다. 파일을 나누어 등록하세요.")
        try:
            if path.suffix.lower() in {".yaml", ".yml"}:
                extracted = export_inventory(path)
                for node in extracted["nodes"]:
                    node["properties"]["source_path"] = f"uploads/{name}"
                batch["nodes"].extend(extracted["nodes"])
                batch["relationships"].extend(extracted["relationships"])
                batch["unresolved"].extend(extracted["unresolved"])
            elif path.suffix.lower() in {".md", ".txt"}:
                raw = path.read_bytes()
                text = raw.decode("utf-8-sig")
                metadata = {}
                match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
                if match:
                    metadata = yaml.safe_load(match.group(1)) or {}
                doc_id = str(metadata.get("document_id") or path.stem)
                version = metadata.get("version")
                properties = {"name": doc_id, "content": text, "source_path": f"uploads/{name}",
                              "source_sha256": hashlib.sha256(raw).hexdigest(), "version": version,
                              "source_status": str(metadata.get("status", "unreviewed"))}
                batch["nodes"].append({"id": doc_id, "class": "Document", "properties": properties})
                body = text[match.end():] if match else text
                for index, section in enumerate(re.split(r"(?m)^## ", body)):
                    section_id = f"{doc_id}/section/{index}"
                    heading = section.splitlines()[0].lstrip("# ") if section.splitlines() else doc_id
                    batch["nodes"].append({"id": section_id, "class": "DocumentSection", "properties": {
                        "name": heading, "content": section, "document_id": doc_id,
                        "source_path": f"uploads/{name}", "source_locator": f"section:{index}"}})
                    batch["relationships"].append({"from_id": doc_id, "to_id": section_id, "type": "HAS_SECTION"})
                batch["unresolved"].append(f"{name}: 적용 대상과 절차 관계는 검토 후 명시적으로 연결해야 합니다.")
                if version is None:
                    batch["unresolved"].append(f"{name}: 문서 버전이 제공되지 않았습니다.")
            else:
                raise HTTPException(422, "현재 구조 추출기는 AR-100 형식 YAML과 UTF-8 Markdown/TXT를 지원합니다. 다른 자료는 별도 파서 또는 지식 구축 에이전트가 필요합니다.")
        except HTTPException:
            raise
        except (ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as exc:
            raise HTTPException(422, f"{name}: 원본 형식 또는 필수 필드를 확인하세요 ({type(exc).__name__}).") from exc
    try:
        return preview(Batch.model_validate(batch)) | {"preparation": "deterministic-structure-extraction", "source_files": request.filenames}
    except ValueError as exc:
        raise HTTPException(422, "추출 결과에 중복 ID, 잘못된 속성 또는 허용 한도를 초과한 내용이 있습니다.") from exc
