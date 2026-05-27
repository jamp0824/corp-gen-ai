"""
DB 레이어 단위 테스트 (인메모리 SQLite).
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import EnrichmentJob, JobStatus
from app.db.repository import (
    create_job,
    get_job,
    get_result,
    mark_failed,
    mark_processing,
    persist_result,
)
from app.models.content_package import (
    AboutSection,
    ContentMeta,
    ContentPackage,
    ContentSections,
    HeroSection,
    StrengthItem,
)
from app.models.schemas import (
    EnrichmentMeta,
    EnrichmentRequest,
    NormalizedInput,
    Source,
    ValidationResult,
)


# ─────────────────────────────────────────────
# 픽스처
# ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def event_loop_policy():
    # pytest-asyncio 0.23+
    return None


@pytest_asyncio.fixture
async def session() -> AsyncSession:  # type: ignore[return]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _make_normalized() -> NormalizedInput:
    return NormalizedInput(
        company_id="test-co",
        company_name="테스트",
        industry="IT",
        business_type="솔루션",
        main_business_description="AI 솔루션 개발 및 공급",
        official_url="https://test.co.kr",
        homepage_type="general",
        tone="professional",
    )


def _make_request() -> EnrichmentRequest:
    return EnrichmentRequest(
        company_name="테스트",
        industry="IT",
        business_type="솔루션",
        main_business_description="AI 솔루션 개발 및 공급",
        official_url="https://test.co.kr",
    )


def _make_package() -> ContentPackage:
    return ContentPackage(
        sections=ContentSections(
            hero=HeroSection(
                headline="AI 솔루션 전문 기업",
                subheadline="AI로 비즈니스를 혁신합니다.",
                cta_label="문의하기",
                evidence_refs=["src_001"],
                sufficient=True,
            ),
            about=AboutSection(
                title="회사소개",
                body="AI 솔루션을 개발하는 전문 기업입니다. " * 4,
                evidence_refs=["src_001"],
                sufficient=True,
            ),
            strengths=[
                StrengthItem(
                    title="전문성",
                    description="AI 분야에 특화된 전문 기업으로 다양한 솔루션을 제공합니다.",
                    evidence_refs=["src_001"],
                    sufficient=True,
                ),
                StrengthItem(
                    title="신뢰성",
                    description="검증된 기술력과 오랜 경험을 바탕으로 안정적인 서비스를 제공합니다.",
                    evidence_refs=["src_001"],
                    sufficient=True,
                ),
            ],
        ),
        meta=ContentMeta(evidence_level="input_only", warnings=[]),
    )


# ─────────────────────────────────────────────
# 테스트
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_get_job(session: AsyncSession) -> None:
    """job 생성 후 조회"""
    job = await create_job(session, "job-001", _make_normalized(), _make_request())
    assert job.id == "job-001"
    assert job.status == JobStatus.pending
    assert job.company_id == "test-co"

    fetched = await get_job(session, "job-001")
    assert fetched is not None
    assert fetched.company_name == "테스트"


@pytest.mark.asyncio
async def test_mark_processing(session: AsyncSession) -> None:
    await create_job(session, "job-002", _make_normalized(), _make_request())
    await mark_processing(session, "job-002")

    job = await get_job(session, "job-002")
    assert job is not None
    assert job.status == JobStatus.processing


@pytest.mark.asyncio
async def test_persist_and_get_result(session: AsyncSession) -> None:
    """완료 결과 저장 후 역직렬화 조회"""
    await create_job(session, "job-003", _make_normalized(), _make_request())
    await mark_processing(session, "job-003")

    package    = _make_package()
    sources    = [
        Source(source_id="src_001", source_type="input",
               origin="/company_name", text="테스트", confidence=1.0),
    ]
    validation = ValidationResult()
    meta       = EnrichmentMeta(
        evidence_level="input_only",
        crawled_pages=0,
        crawl_duration_ms=0,
        llm_duration_ms=5000,
        total_duration_ms=5000,
        retry_count=0,
    )

    await persist_result(session, "job-003", package, sources, validation, meta)

    result = await get_result(session, "job-003")
    assert result is not None
    assert result.company_id == "test-co"
    assert result.package.sections.hero.headline == "AI 솔루션 전문 기업"
    assert len(result.sources) == 1
    assert result.meta.evidence_level == "input_only"


@pytest.mark.asyncio
async def test_mark_failed(session: AsyncSession) -> None:
    await create_job(session, "job-004", _make_normalized(), _make_request())
    await mark_failed(session, "job-004", "llm_timeout", "LLM 응답 초과")

    job = await get_job(session, "job-004")
    assert job is not None
    assert job.status == JobStatus.failed
    assert job.error_code == "llm_timeout"


@pytest.mark.asyncio
async def test_get_result_not_completed(session: AsyncSession) -> None:
    """미완료 job은 None 반환"""
    await create_job(session, "job-005", _make_normalized(), _make_request())
    result = await get_result(session, "job-005")
    assert result is None


@pytest.mark.asyncio
async def test_get_nonexistent_job(session: AsyncSession) -> None:
    result = await get_result(session, "nonexistent-job")
    assert result is None
