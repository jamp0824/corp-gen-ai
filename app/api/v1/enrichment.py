"""
콘텐츠 보강 API — SSE 아키텍처 버전.

엔드포인트:
  POST   /api/v1/content-enrichment          → {job_id} (즉시 반환)
  GET    /api/v1/content-enrichment/stream/{job_id}   → SSE 스트림
  GET    /api/v1/content-enrichment/result/{job_id}   → 저장된 최종 결과

흐름:
  1. POST → job_id 반환 + 백그라운드 태스크 시작
  2. 클라이언트가 SSE 스트림 구독 → phase/complete/error 이벤트 수신
  3. complete 이벤트에 result(ContentPackageResponse) 포함

백그라운드 태스크 Phase 순서:
  A. preflight  (≤2s)   URL 검증
  B. crawl      (≤25s)  홈페이지 크롤링 (부분 실패 허용)
  C. source_pool(≤0.5s) 소스 풀 구성
  D. llm        (≤25s)  LLM 호출
  E. validate   (≤12s)  검증 + 재시도
  F. persist    (≤2s)   DB 저장
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import unicodedata
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.crawlers import InvalidURL, crawl_site, preflight
from app.db import (
    async_session,
    create_job,
    get_job,
    get_result,
    mark_failed,
    mark_processing,
    persist_result,
)
from app.db.models import JobStatus
from app.models.schemas import (
    ContentPackageResponse,
    EnrichmentMeta,
    EnrichmentRequest,
    NormalizedInput,
)
from app.services import (
    LLMClient,
    build_mega_prompt,
    build_source_pool,
    build_strict_mega_prompt,
    validate_package,
)
from app.services.job_store import (
    emit_complete,
    emit_error,
    emit_phase,
    job_store,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["enrichment"])

# ─────────────────────────────────────────────
# 의존성
# ─────────────────────────────────────────────

_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


# ─────────────────────────────────────────────
# 입력 정규화
# ─────────────────────────────────────────────

def _make_company_id(name: str) -> str:
    slug = unicodedata.normalize("NFC", name)
    slug = re.sub(r"[^\w가-힣\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip()).lower()
    return slug[:50] or "company"


def normalize_input(payload: EnrichmentRequest) -> NormalizedInput:
    return NormalizedInput(
        company_id=_make_company_id(payload.company_name),
        company_name=payload.company_name,
        industry=payload.industry,
        business_type=payload.business_type,
        main_business_description=payload.main_business_description,
        official_url=payload.official_url,
        homepage_type=payload.homepage_type,
        tone=payload.tone,
    )


# ─────────────────────────────────────────────
# POST — 작업 시작 (즉시 반환)
# ─────────────────────────────────────────────

@router.post(
    "/content-enrichment",
    summary="콘텐츠 보강 작업 시작",
    description=(
        "즉시 job_id를 반환하고 백그라운드에서 크롤링 + LLM을 실행합니다. "
        "/stream/{job_id}로 실시간 진행 상황을 수신하세요."
    ),
    status_code=202,
)
async def start_enrichment(
    payload: EnrichmentRequest,
    llm: LLMClient = Depends(get_llm),
) -> dict:
    job_id     = str(uuid.uuid4())
    normalized = normalize_input(payload)

    # 큐 먼저 생성 (태스크가 emit하기 전에 큐가 있어야 함)
    job_store.create(job_id)

    # DB에 pending 레코드 생성
    async with async_session() as session:
        await create_job(session, job_id, normalized, payload)

    # 백그라운드 태스크 시작 (GC 방지용 참조 유지)
    task = asyncio.create_task(
        _run_enrichment(job_id, normalized, payload, llm),
        name=f"enrich-{job_id[:8]}",
    )
    job_store.track_task(task)

    logger.info("job started: job_id=%s company=%s", job_id, normalized.company_name)
    return {"job_id": job_id}


# ─────────────────────────────────────────────
# GET /stream — SSE 스트림
# ─────────────────────────────────────────────

@router.get(
    "/content-enrichment/stream/{job_id}",
    summary="SSE 진행 상황 스트림",
    description="phase / complete / error 이벤트를 Server-Sent Events로 수신합니다.",
)
async def stream_enrichment(job_id: str, request: Request) -> StreamingResponse:
    # DB에서 job 존재 확인
    async with async_session() as session:
        job = await get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    q = job_store.get(job_id)

    async def event_generator():
        try:
            # 이미 완료/실패된 job이면 DB에서 결과를 즉시 반환
            if job.status == JobStatus.completed:
                async with async_session() as session:
                    result = await get_result(session, job_id)
                if result:
                    yield _sse("complete", {
                        "result": json.loads(result.model_dump_json()),
                        "elapsed_ms": 0,
                        "from_cache": True,
                    })
                return

            if job.status == JobStatus.failed:
                yield _sse("error", {
                    "code": job.error_code or "unknown",
                    "message": job.error_message or "작업 실패",
                })
                return

            if q is None:
                yield _sse("error", {"code": "queue_missing", "message": "큐가 없습니다"})
                return

            # 실시간 이벤트 수신
            while True:
                if await request.is_disconnected():
                    logger.info("SSE client disconnected: job_id=%s", job_id)
                    return

                try:
                    event = await asyncio.wait_for(q.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    # keepalive (빈 주석)
                    yield ": keepalive\n\n"
                    continue

                yield _sse(event.event_type, event.to_sse_data())

                if event.event_type in ("complete", "error"):
                    break

        finally:
            job_store.cleanup(job_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":          "no",   # Nginx 버퍼 비활성화
            "Access-Control-Allow-Origin": "*",
        },
    )


def _sse(event: str, data: dict) -> str:
    """SSE 포맷 문자열 생성."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ─────────────────────────────────────────────
# GET /result — 저장된 최종 결과
# ─────────────────────────────────────────────

@router.get(
    "/content-enrichment/result/{job_id}",
    response_model=ContentPackageResponse,
    summary="완료된 결과 조회",
)
async def get_enrichment_result(job_id: str) -> ContentPackageResponse:
    async with async_session() as session:
        result = await get_result(session, job_id)
    if result is None:
        async with async_session() as session:
            job = await get_job(session, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        if job.status == JobStatus.failed:
            raise HTTPException(
                422,
                detail={"code": job.error_code, "message": job.error_message},
            )
        raise HTTPException(202, "Job still processing")
    return result


# ─────────────────────────────────────────────
# GET /history/{company_id} — 회사별 이력
# ─────────────────────────────────────────────

@router.get(
    "/content-enrichment/history/{company_id}",
    summary="회사별 보강 이력",
)
async def get_company_history(company_id: str, limit: int = 5) -> list[dict]:
    from app.db import get_latest_by_company
    async with async_session() as session:
        jobs = await get_latest_by_company(session, company_id, limit=limit)
    return [
        {
            "job_id":      j.id,
            "company_name": j.company_name,
            "official_url": j.official_url,
            "evidence_level": j.evidence_level,
            "created_at":  j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


# ─────────────────────────────────────────────
# 백그라운드 태스크 — Phase A~F
# ─────────────────────────────────────────────

async def _run_enrichment(
    job_id: str,
    normalized: NormalizedInput,
    payload: EnrichmentRequest,
    llm: LLMClient,
) -> None:
    """
    실제 처리 파이프라인.
    각 Phase 시작/종료 시 job_store에 이벤트를 emit한다.
    """
    started = time.monotonic()
    DEADLINE = settings.request_deadline_sec

    def elapsed_ms() -> int:
        return int((time.monotonic() - started) * 1000)

    def remaining() -> float:
        return DEADLINE - (time.monotonic() - started)

    async with async_session() as session:
        await mark_processing(session, job_id)

    try:
        # ── Phase A: Pre-flight ───────────────
        await emit_phase(job_id, "preflight",
                         "공식 홈페이지를 확인하고 있어요...",
                         elapsed_ms=elapsed_ms())
        try:
            preflight_res = await preflight(payload.official_url)
        except InvalidURL as e:
            await emit_error(job_id, e.code, e.detail)
            async with async_session() as session:
                await mark_failed(session, job_id, e.code, e.detail)
            return

        # ── Phase B: Crawl ────────────────────
        crawl_budget = min(settings.crawl_budget_sec, max(0.0, remaining() - 30.0))
        await emit_phase(job_id, "crawl",
                         "페이지 내용을 수집하고 있어요...",
                         elapsed_ms=elapsed_ms(),
                         budget_sec=round(crawl_budget, 1))
        crawl_start = time.monotonic()
        try:
            pages = await crawl_site(
                payload.official_url,
                origin=preflight_res.origin,
                budget_sec=crawl_budget,
            )
        except Exception as exc:
            logger.warning("크롤링 예외 (input-only fallback): %s", exc)
            pages = []

        crawl_ms = int((time.monotonic() - crawl_start) * 1000)
        await emit_phase(job_id, "crawl",
                         f"홈페이지 {len(pages)}페이지 수집 완료",
                         elapsed_ms=elapsed_ms(),
                         crawled_pages=len(pages),
                         crawl_duration_ms=crawl_ms)

        # ── Phase C: Source Pool ──────────────
        await emit_phase(job_id, "source_pool",
                         "수집한 내용을 분석하고 있어요...",
                         elapsed_ms=elapsed_ms())
        sources        = build_source_pool(normalized, pages)
        evidence_level = "input_plus_crawl" if pages else "input_only"

        # ── Phase D: LLM ─────────────────────
        await emit_phase(job_id, "llm",
                         "홈페이지 문구를 작성하고 있어요...",
                         elapsed_ms=elapsed_ms(),
                         evidence_level=evidence_level)

        llm_budget = max(15.0, remaining() - 7.0)
        prompt     = build_mega_prompt(normalized, sources, evidence_level)
        llm_start  = time.monotonic()
        try:
            package = await asyncio.wait_for(
                llm.complete_package(prompt, temperature=0.2),
                timeout=llm_budget,
            )
        except asyncio.TimeoutError:
            await emit_error(job_id, "llm_timeout", "AI 응답 시간이 초과됐습니다.")
            async with async_session() as session:
                await mark_failed(session, job_id, "llm_timeout", "LLM timeout")
            return
        except Exception as exc:
            logger.error("LLM 오류: %s", exc)
            await emit_error(job_id, "llm_error", "AI 처리 중 오류가 발생했습니다.")
            async with async_session() as session:
                await mark_failed(session, job_id, "llm_error", str(exc))
            return

        llm_ms = int((time.monotonic() - llm_start) * 1000)

        # ── Phase E: Validate ─────────────────
        await emit_phase(job_id, "validate",
                         "근거를 다시 확인하고 있어요...",
                         elapsed_ms=elapsed_ms())

        validation  = validate_package(package, sources)
        retry_count = 0

        if validation.has_blocker and remaining() > 12.0:
            await emit_phase(job_id, "validate",
                             f"품질 개선을 위해 재작성하고 있어요... (이슈 {len(validation.blockers)}건)",
                             elapsed_ms=elapsed_ms())
            retry_count = 1
            strict_prompt = build_strict_mega_prompt(normalized, sources, evidence_level)
            try:
                package    = await asyncio.wait_for(
                    llm.complete_package(strict_prompt, temperature=0.1),
                    timeout=max(10.0, remaining() - 4.0),
                )
                validation = validate_package(package, sources)
            except Exception as exc:
                logger.warning("재시도 실패, 원본 사용: %s", exc)

        # ── Phase F: Persist ──────────────────
        await emit_phase(job_id, "persist",
                         "결과를 저장하고 있어요...",
                         elapsed_ms=elapsed_ms())

        meta = EnrichmentMeta(
            evidence_level=evidence_level,          # type: ignore[arg-type]
            crawled_pages=len(pages),
            crawl_duration_ms=crawl_ms,
            llm_duration_ms=llm_ms,
            total_duration_ms=elapsed_ms(),
            retry_count=retry_count,
        )
        async with async_session() as session:
            await persist_result(session, job_id, package, sources, validation, meta)

        # ── Complete ──────────────────────────
        result = ContentPackageResponse(
            company_id=normalized.company_id,
            package=package,
            sources=sources,
            validation=validation,
            meta=meta,
        )
        await emit_complete(job_id, result, elapsed_ms())
        logger.info("job completed: job_id=%s total=%.1fs", job_id, (time.monotonic() - started))

    except Exception as exc:
        logger.exception("예상치 못한 오류: job_id=%s", job_id)
        await emit_error(job_id, "internal_error", f"서버 내부 오류: {exc!s}")
        try:
            async with async_session() as session:
                await mark_failed(session, job_id, "internal_error", str(exc))
        except Exception:
            pass
