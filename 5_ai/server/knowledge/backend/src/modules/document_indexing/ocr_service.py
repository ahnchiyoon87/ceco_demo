"""PDF OCR service backed by OpenAI file inputs and local page cache."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

from ...shared.kernel.model_profiles import ModelProfile, resolve_model_profile
from ...shared.kernel.settings import get_settings
from ...shared.logging import SmartLogger
from ..files.service import get_cache_root

logger = logging.getLogger(__name__)

PdfProgressCallback = Callable[[int, str, dict[str, Any] | None], Awaitable[None]]
OCR_PROMPT_VERSION = "2026-04-17-v1"
PAGE_OCR_PROMPT_TEMPLATE = """You are performing OCR on a single PDF page for downstream ontology construction.

Goal:
- Produce a faithful, machine-parseable transcription of only the visible content on this page.

Hard rules:
- Return only the page content. Do not add explanations outside the requested page output.
- Do not summarize, interpret, infer trends, or rewrite content in your own words.
- Preserve Korean, English, numbers, units, formulas, and symbols as accurately as possible.
- If text is unreadable, cropped, or ambiguous, use only these placeholders: [unclear], [illegible], [cropped].
- If a diagram connection is uncertain, use [connection ambiguous] instead of guessing.
- Never shorten visible labels with `...`. Keep the full visible label text, or append `[cropped]` / `[unclear]` when incomplete.

Output format:
1. Start with exactly `<!-- Page {page_number} -->`
2. If a running header, footer, or printed page number is clearly visible, put each in its own HTML comment.
3. Transcribe normal headings, paragraphs, bullets, and formulas in visible reading order.
4. Reproduce tables as Markdown tables whenever possible.
5. For flowcharts or diagrams, preserve node labels, edge labels, and explicit connections in a structured list instead of rewriting them as prose.
6. For charts, preserve visible labels, legends, axes, and numeric callouts without interpreting causes or trends.

Visible page number: {page_number}
"""


def log_pdf_ocr(level: str, message: str, params: dict[str, Any] | None = None) -> None:
    """Write OCR logs through the structured backend logger."""

    SmartLogger.log(level, message, category="document_indexing.ocr", params=params)


def build_pdf_metadata(path: Path) -> dict[str, Any]:
    """Collect basic file metadata for logs and responses."""

    exists = path.exists()
    metadata: dict[str, Any] = {
        "path": str(path),
        "exists": exists,
        "name": path.name,
    }
    if exists:
        metadata["size_bytes"] = path.stat().st_size
    return metadata


def summarize_text_payload(text: str) -> dict[str, Any]:
    """Return a small summary for OCR text logs."""

    normalized = (text or "").strip()
    return {
        "length": len(normalized),
        "sha256": hashlib.sha256(
            normalized.encode("utf-8", errors="ignore")
        ).hexdigest()[:12],
    }


class PDFOCRService:
    """Extract text from PDFs with page-level OCR cache."""

    def __init__(self) -> None:
        self._ocr_cache_root = get_cache_root() / "ocr"

    async def _emit_progress(
        self,
        on_progress: PdfProgressCallback | None,
        progress: int,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        if on_progress is None:
            return
        await on_progress(max(0, min(100, int(progress))), message, detail)

    def _scale_progress(self, start: int, end: int, current: int, total: int) -> int:
        if total <= 0:
            return end
        fraction = max(0.0, min(1.0, current / total))
        return max(start, min(end, int(round(start + ((end - start) * fraction)))))

    async def extract_text(
        self,
        pdf_bytes: bytes,
        on_progress: PdfProgressCallback | None = None,
    ) -> str:
        """Extract text from PDF bytes."""

        result = await self.extract_text_with_metadata(pdf_bytes, on_progress=on_progress)
        return result["text"]

    async def extract_text_with_metadata(
        self,
        pdf_bytes: bytes,
        on_progress: PdfProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Extract text and page metadata from PDF bytes."""

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            temp_pdf.write(pdf_bytes)
            temp_path = Path(temp_pdf.name)

        try:
            return await self.extract_text_from_path_with_metadata(
                temp_path,
                on_progress=on_progress,
            )
        finally:
            temp_path.unlink(missing_ok=True)

    async def extract_text_from_path_with_metadata(
        self,
        pdf_path: str | Path,
        on_progress: PdfProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Extract text and OCR metadata from a PDF path."""

        path = Path(pdf_path)
        if not path.exists():
            raise ValueError(f"PDF 파일을 찾을 수 없습니다: {path}")

        await self._emit_progress(
            on_progress,
            5,
            "PDF OCR 준비 중",
            {"mode": "prepare", "source": str(path)},
        )
        log_pdf_ocr(
            "INFO",
            "pdf ocr extraction started",
            {"pdf": build_pdf_metadata(path)},
        )

        try:
            result = await self._extract_text_with_openai(path, on_progress=on_progress)
            if result.get("text"):
                return result
        except Exception as exc:
            logger.warning("OpenAI OCR failed, falling back to text extractors: %s", exc)
            log_pdf_ocr(
                "WARNING",
                "openai ocr failed; falling back to baseline extractor",
                {
                    "pdf": build_pdf_metadata(path),
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

        await self._emit_progress(
            on_progress,
            12,
            "기본 PDF 추출 경로로 전환 중",
            {"mode": "baseline_fallback", "source": str(path)},
        )
        return await self._extract_text_from_path_internal(path, on_progress=on_progress)

    async def _extract_text_with_openai(
        self,
        pdf_path: Path,
        on_progress: PdfProgressCallback | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        profile = resolve_model_profile(
            purpose="ocr",
            model_name=settings.ocr_model,
            reasoning_effort=settings.ocr_model_reasoning_effort,
            openai_base_url=settings.openai_base_url,
            openai_api_key=settings.openai_api_key,
        )
        if not profile.is_openai:
            raise ValueError(f"OCR provider is not supported yet: {profile.provider}")
        if not profile.api_key:
            raise ValueError("OPENAI_API_KEY is required for OCR")

        pdf_bytes = pdf_path.read_bytes()
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        with tempfile.TemporaryDirectory(prefix="pdf-ocr-pages-") as temp_dir:
            page_paths = self._split_pdf_to_pages(pdf_bytes, Path(temp_dir))
            if not page_paths:
                raise ValueError("PDF에서 페이지를 분리하지 못했습니다.")

            await self._emit_progress(
                on_progress,
                15,
                f"페이지 분리 완료 ({len(page_paths)}페이지)",
                {"pageCurrent": 0, "pageTotal": len(page_paths), "mode": "ocr_split"},
            )

            attempted_pages = list(range(1, len(page_paths) + 1))
            applied_pages: list[int] = []
            cached_pages: list[int] = []
            structured_pages: list[dict[str, Any]] = []
            ocr_only_text_by_page: dict[int, str] = {}

            for page_number, page_path in enumerate(page_paths, start=1):
                page_bytes = page_path.read_bytes()
                page_sha256 = hashlib.sha256(page_bytes).hexdigest()
                cached_text = self._load_cached_page(
                    pdf_sha256=pdf_sha256,
                    page_number=page_number,
                    page_sha256=page_sha256,
                    profile=profile,
                )
                cache_hit = cached_text is not None

                if cache_hit:
                    page_text = cached_text
                    used_llm = True
                    cached_pages.append(page_number)
                else:
                    try:
                        page_text = await asyncio.to_thread(
                            self._extract_single_page_with_openai_sync,
                            page_bytes,
                            page_path.name,
                            page_number,
                            profile,
                        )
                        used_llm = True
                        if settings.use_ocr_cache:
                            self._save_cached_page(
                                pdf_sha256=pdf_sha256,
                                page_number=page_number,
                                page_sha256=page_sha256,
                                profile=profile,
                                text=page_text,
                            )
                    except Exception as exc:
                        logger.warning(
                            "페이지 %s OpenAI OCR 실패, PyPDF 추출로 폴백합니다: %s",
                            page_number,
                            exc,
                        )
                        fallback_pages = self._extract_text_with_pypdf(page_path)
                        page_text = "\n\n".join(
                            [page["text"] for page in fallback_pages if page.get("text")]
                        ).strip()
                        used_llm = False

                sanitized_text = self._sanitize_page_output(page_text)
                if sanitized_text:
                    structured_pages.append(
                        {
                            "pageNumber": page_number,
                            "text": sanitized_text,
                            "textHash": hashlib.sha256(
                                sanitized_text.encode("utf-8", errors="ignore")
                            ).hexdigest(),
                            "charCount": len(sanitized_text),
                            "pageSha256": page_sha256,
                            "ocrMethod": (
                                "openai_cache"
                                if cache_hit
                                else "openai"
                                if used_llm
                                else "pypdf_fallback"
                            ),
                            "usedLlm": used_llm,
                            "cacheHit": cache_hit,
                        }
                    )
                    if used_llm:
                        applied_pages.append(page_number)
                        ocr_only_text_by_page[page_number] = sanitized_text

                await self._emit_progress(
                    on_progress,
                    self._scale_progress(20, 85, page_number, len(page_paths)),
                    f"페이지 {page_number}/{len(page_paths)} OCR 처리 완료",
                    {
                        "pageCurrent": page_number,
                        "pageTotal": len(page_paths),
                        "mode": "ocr",
                        "lastProcessedPage": page_number,
                        "cacheHit": cache_hit,
                    },
                )

        combined_text = "\n\n".join(page["text"] for page in structured_pages).strip()
        if not combined_text:
            raise ValueError("OCR 결과에서 텍스트를 추출하지 못했습니다.")

        await self._emit_progress(
            on_progress,
            95,
            "OCR 결과 조립 완료",
            {
                "pageCurrent": len(structured_pages),
                "pageTotal": len(structured_pages),
                "mode": "ocr_assemble",
            },
        )
        result = {
            "text": combined_text,
            "pageCount": len(page_paths),
            "ocrAttemptedPages": attempted_pages,
            "ocrAppliedPages": applied_pages,
            "ocrCachedPages": cached_pages,
            "ocrOnlyTextByPage": ocr_only_text_by_page,
            "ocrEngine": f"openai:{profile.model_name}",
            "pages": structured_pages,
        }
        log_pdf_ocr(
            "INFO",
            "openai ocr extraction completed",
            {
                "pdf": build_pdf_metadata(pdf_path),
                "pdf_sha256": pdf_sha256,
                "attempted_pages": attempted_pages,
                "applied_pages": applied_pages,
                "cached_pages": cached_pages,
                "result_summary": summarize_text_payload(combined_text),
            },
        )
        return result

    def _cache_file_path(self, pdf_sha256: str, page_number: int) -> Path:
        return self._ocr_cache_root / pdf_sha256 / f"page_{page_number:04d}.json"

    def _load_cached_page(
        self,
        *,
        pdf_sha256: str,
        page_number: int,
        page_sha256: str,
        profile: ModelProfile,
    ) -> str | None:
        settings = get_settings()
        if not settings.use_ocr_cache:
            return None
        cache_path = self._cache_file_path(pdf_sha256, page_number)
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if payload.get("pageSha256") != page_sha256:
            return None
        if payload.get("ocrModel") != profile.raw_name:
            return None
        if payload.get("promptVersion") != OCR_PROMPT_VERSION:
            return None
        return str(payload.get("text", "")).strip() or None

    def _save_cached_page(
        self,
        *,
        pdf_sha256: str,
        page_number: int,
        page_sha256: str,
        profile: ModelProfile,
        text: str,
    ) -> None:
        cache_path = self._cache_file_path(pdf_sha256, page_number)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pageNumber": page_number,
            "pageSha256": page_sha256,
            "ocrModel": profile.raw_name,
            "promptVersion": OCR_PROMPT_VERSION,
            "text": text,
        }
        cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _extract_single_page_with_openai_sync(
        self,
        page_bytes: bytes,
        filename: str,
        page_number: int,
        profile: ModelProfile,
    ) -> str:
        from openai import OpenAI

        client_kwargs: dict[str, Any] = {
            "api_key": profile.api_key,
            "base_url": profile.base_url or "https://api.openai.com/v1",
        }
        client = OpenAI(**client_kwargs)
        prompt = PAGE_OCR_PROMPT_TEMPLATE.format(page_number=page_number)
        data_uri = "data:application/pdf;base64," + base64.b64encode(page_bytes).decode(
            "utf-8"
        )
        request: dict[str, Any] = {
            "model": profile.model_name,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_file",
                            "filename": filename,
                            "file_data": data_uri,
                        },
                    ],
                }
            ],
        }
        if profile.reasoning_effort:
            request["reasoning"] = {"effort": profile.reasoning_effort}
        response = client.responses.create(**request)
        text = (getattr(response, "output_text", None) or "").strip()
        if not text:
            raise ValueError(f"페이지 {page_number} OCR 응답이 비었습니다.")
        return text

    def _sanitize_page_output(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return ""
        cleaned = re.sub(r"(?m)^[ \t]*<!--.*?-->[ \t]*\n?", "", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _split_pdf_to_pages(self, pdf_bytes: bytes, output_dir: Path) -> list[Path]:
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError as exc:
            raise ValueError(
                "페이지별 OCR을 위해 pypdf가 필요합니다. 서버 환경에 pypdf를 설치하세요."
            ) from exc

        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_paths: list[Path] = []
        for page_number, page in enumerate(reader.pages, start=1):
            writer = PdfWriter()
            writer.add_page(page)
            page_path = output_dir / f"page_{page_number:04d}.pdf"
            with page_path.open("wb") as handle:
                writer.write(handle)
            page_paths.append(page_path)
        return page_paths

    async def _extract_text_from_path_internal(
        self,
        pdf_path: Path,
        on_progress: PdfProgressCallback | None = None,
    ) -> dict[str, Any]:
        page_texts: list[str] = []
        structured_pages: list[dict[str, Any]] = []

        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                await self._emit_progress(
                    on_progress,
                    15,
                    f"기본 PDF 추출 시작 ({total_pages}페이지)",
                    {"pageCurrent": 0, "pageTotal": total_pages, "mode": "pdfplumber"},
                )
                for page_number, page in enumerate(pdf.pages, start=1):
                    page_text = (page.extract_text() or "").strip()
                    if page_text:
                        page_texts.append(page_text)
                        structured_pages.append(
                            {
                                "pageNumber": page_number,
                                "text": page_text,
                                "textHash": hashlib.sha256(
                                    page_text.encode("utf-8", errors="ignore")
                                ).hexdigest(),
                                "charCount": len(page_text),
                                "ocrMethod": "pdfplumber",
                                "usedLlm": False,
                                "cacheHit": False,
                            }
                        )
                    await self._emit_progress(
                        on_progress,
                        self._scale_progress(20, 85, page_number, total_pages),
                        f"페이지 {page_number}/{total_pages} 기본 추출 중",
                        {
                            "pageCurrent": page_number,
                            "pageTotal": total_pages,
                            "mode": "pdfplumber",
                        },
                    )
                result = "\n\n".join(page_texts).strip()
                if result:
                    return {
                        "text": result,
                        "pageCount": total_pages,
                        "ocrAttemptedPages": [],
                        "ocrAppliedPages": [],
                        "ocrCachedPages": [],
                        "ocrOnlyTextByPage": {},
                        "ocrEngine": None,
                        "pages": structured_pages,
                    }
        except ImportError:
            logger.info("pdfplumber is unavailable; falling back to pypdf.")

        await self._emit_progress(
            on_progress,
            20,
            "PyPDF 텍스트 추출 중",
            {"mode": "pypdf"},
        )
        page_results = self._extract_text_with_pypdf(pdf_path)
        result = "\n\n".join(
            [page["text"] for page in page_results if page.get("text")]
        ).strip()
        if not result:
            raise ValueError("PDF에서 추출된 텍스트가 없습니다.")
        return {
            "text": result,
            "pageCount": len(page_results),
            "ocrAttemptedPages": [],
            "ocrAppliedPages": [],
            "ocrCachedPages": [],
            "ocrOnlyTextByPage": {},
            "ocrEngine": None,
            "pages": page_results,
        }

    def _extract_text_with_pypdf(self, pdf_path: Path) -> list[dict[str, Any]]:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError(
                "PDF 텍스트 추출을 위해 pypdf가 필요합니다. 서버 환경에 pypdf를 설치하세요."
            ) from exc

        reader = PdfReader(io.BytesIO(pdf_path.read_bytes()))
        page_results: list[dict[str, Any]] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            page_results.append(
                {
                    "pageNumber": page_number,
                    "text": text,
                    "textHash": hashlib.sha256(
                        text.encode("utf-8", errors="ignore")
                    ).hexdigest(),
                    "charCount": len(text),
                    "ocrMethod": "pypdf",
                    "usedLlm": False,
                    "cacheHit": False,
                }
            )
        return page_results
