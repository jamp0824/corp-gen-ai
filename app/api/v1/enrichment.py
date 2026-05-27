"""
POST /content-enrichment 핸들러.

Phase A~F를 순서대로 실행하는 단일 요청/응답 핸들러.
deadline 기반 동적 시간 배분으로 크롤링 결과에 따라 LLM 예산을 조절한다.

Phase A: Pre-flight  (≤2s)
Phase B: Crawl       (≤25s, 부분 실패 허용)
Phase C: Source Pool 구성 (≤0.5s)
Phase D: LLM 호출    (≤25s, 남은 시간으로 동적 배분)
Phase E: 검증 + 1회 재시도 (≤12s)
Phase F: 저장        (≤2s)
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import unicodedata

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.crawlers import InvalidURL, crawl_site, preflight
from app.models.schemas import (
    ContentPackageResponse,
    EnrichmentMeta,
    EnrichmentRequest,
    NormalizedInput,
    ValidationResult,
)
from app.services import (
    LLMClient,
    build_mega_prompt,
    build_source_pool,
    build_strict_mega_prompt,
    validate_package,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["enrichment"])


# ─────────────────────────────────────────────
# 의존성
# ─────────────────────────────────────────────

_llm_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


# ─────────────────────────────────────────────
# 입력 정규화 (company_id 생성 포함)
# ─────────────────────────────────────────────

def _make_company_id(company_name: str) -> str:
    """회사명 → URL-safe slug."""
    # 한글 → 로마자 변환 없이 ASCII + 한글만 남기고 공백은 하이픈으로
    slug = unicodedata.normalize("NFC", company_name)
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
# 핸들러
# ─────────────────────────────────────────────

@router.post(
    "/content-enrichment",
    response_model=ContentPackageResponse,
    summary="Step 2 → 콘텐츠 보강 (크롤링 + LLM)",
    description=(
        "공식 홈페이지를 크롤링해 소스 풀을 구성하고, "
        "Claude LLM으로 홈페이지 콘텐츠 패키지를 생성합니다. "
        "총 응답 시간: 30~60초."
    ),
)
async def enrich_content(
    payload: EnrichmentRequest,
    llm: LLMClient = Depends(get_llm),
) -> ContentPackageResponse:
    started = time.monotonic()
    DEADLINE = settings.request_deadline_sec  # 기본 58s

    def elapsed() -> float:
        return time.monotonic() - started

    def remaining() -> float:
        return DEADLINE - elapsed()

    retry_count = 0
    crawl_ms = 0
    llm_ms = 0

    # ── Phase A: Pre-flight ──────────────────
    logger.info("Phase A: pre-flight — %s", payload.official_url)
    normalized = normalize_input(payload)

    try:
        preflight_res = await preflight(payload.official_url)
    except InvalidURL as e:
        raise HTTPException(
            status_code=400,
            detail={"code": e.code, "message": e.detail},
        )
    logger.info("Phase A 완료 (%.1fs)", elapsed())

    # ── Phase B: Crawl ───────────────────────
    # 크롤 예산: 25s 또는 남은 시간 - 30s (LLM+검증 최소 30s 확보)
    crawl_budget = min(
        settings.crawl_budget_sec,
        max(0.0, remaining() - 30.0),
    )
    logger.info("Phase B: crawl (budget=%.1fs) — %s", crawl_budget, payload.official_url)

    crawl_start = time.monotonic()
    try:
        pages = await crawl_site(
            payload.official_url,
            origin=preflight_res.origin,
            budget_sec=crawl_budget,
        )
    except Exception as exc:
        logger.warning("크롤링 예외 (fallback to input-only): %s", exc)
        pages = []
    crawl_ms = int((time.monotonic() - crawl_start) * 1000)
    logger.info(
        "Phase B 완료: %d페이지 (%.1fs, elapsed=%.1fs)",
        len(pages), crawl_ms / 1000, elapsed(),
    )

    # ── Phase C: Source Pool ─────────────────
    sources = build_source_pool(normalized, pages)
    evidence_level = "input_plus_crawl" if pages else "input_only"
    logger.info(
        "Phase C: %d sources (%d input + %d crawl)",
        len(sources),
        sum(1 for s in sources if s.source_type == "input"),
        len(pages),
    )

    # ── Phase D: LLM 호출 ────────────────────
    # LLM 예산: 남은 시간 - 검증/저장 여유 7s
    llm_budget = max(15.0, remaining() - 7.0)
    logger.info("Phase D: LLM 호출 (budget=%.1fs)", llm_budget)

    prompt = build_mega_prompt(normalized, sources, evidence_level)
    llm_start = time.monotonic()
    try:
        package = await asyncio.wait_for(
            llm.complete_package(prompt, temperature=0.2),
            timeout=llm_budget,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503,
            detail={"code": "llm_timeout", "message": "LLM 응답 시간 초과"},
        )
    except Exception as exc:
        logger.error("LLM 오류: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"code": "llm_error", "message": "LLM 호출 실패"},
        )
    llm_ms = int((time.monotonic() - llm_start) * 1000)
    logger.info("Phase D 완료 (%.1fs, elapsed=%.1fs)", llm_ms / 1000, elapsed())

    # ── Phase E: 검증 + 조건부 재시도 ────────
    logger.info("Phase E: 검증")
    validation = validate_package(package, sources)

    if validation.has_blocker and remaining() > 12.0:
        logger.warning(
            "blocker %d건, 재시도 (remaining=%.1fs)",
            len(validation.blockers), remaining(),
        )
        retry_count = 1
        strict_prompt = build_strict_mega_prompt(normalized, sources, evidence_level)
        retry_budget = max(10.0, remaining() - 4.0)
        try:
            package = await asyncio.wait_for(
                llm.complete_package(strict_prompt, temperature=0.1),
                timeout=retry_budget,
            )
            validation = validate_package(package, sources)
        except Exception as exc:
            logger.warning("재시도 실패: %s — 원본 결과 사용", exc)
            # 재시도 실패해도 원본 package + validation으로 진행

    logger.info(
        "Phase E 완료: blockers=%d warnings=%d",
        len(validation.blockers), len(validation.warnings),
    )

    # ── Phase F: 응답 조립 ────────────────────
    # TODO: 추후 DB 저장 추가 (persist_package)
    total_ms = int(elapsed() * 1000)
    logger.info("Phase F: 완료 (total=%.1fs)", total_ms / 1000)

    return ContentPackageResponse(
        company_id=normalized.company_id,
        package=package,
        sources=sources,
        validation=validation,
        meta=EnrichmentMeta(
            evidence_level=evidence_level,  # type: ignore[arg-type]
            crawled_pages=len(pages),
            crawl_duration_ms=crawl_ms,
            llm_duration_ms=llm_ms,
            total_duration_ms=total_ms,
            retry_count=retry_count,
        ),
    )
