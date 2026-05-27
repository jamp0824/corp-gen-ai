"""
DB 액세스 레이어 (Repository 패턴).

EnrichmentJob CRUD + 직렬화/역직렬화 처리.
모든 함수는 AsyncSession을 받아 트랜잭션 제어를 호출자에게 위임한다.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_package import ContentPackage
from app.models.schemas import (
    ContentPackageResponse,
    EnrichmentMeta,
    EnrichmentRequest,
    NormalizedInput,
    Source,
    ValidationResult,
)

from .models import EnrichmentJob, JobStatus


# ─────────────────────────────────────────────
# 생성
# ─────────────────────────────────────────────

async def create_job(
    session: AsyncSession,
    job_id: str,
    normalized: NormalizedInput,
    request: EnrichmentRequest,
) -> EnrichmentJob:
    """
    pending 상태 job 레코드 생성.
    백그라운드 태스크 시작 전에 호출.
    """
    job = EnrichmentJob(
        id=job_id,
        company_id=normalized.company_id,
        company_name=normalized.company_name,
        official_url=normalized.official_url,
        status=JobStatus.pending,
        request_json=request.model_dump_json(),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


# ─────────────────────────────────────────────
# 상태 업데이트
# ─────────────────────────────────────────────

async def mark_processing(session: AsyncSession, job_id: str) -> None:
    job = await _get_or_raise(session, job_id)
    job.status = JobStatus.processing
    await session.commit()


async def persist_result(
    session: AsyncSession,
    job_id: str,
    package: ContentPackage,
    sources: list[Source],
    validation: ValidationResult,
    meta: EnrichmentMeta,
) -> None:
    """
    Phase F: 완료된 결과 저장.
    """
    job = await _get_or_raise(session, job_id)
    job.status          = JobStatus.completed
    job.evidence_level  = meta.evidence_level
    job.package_json    = package.model_dump_json()
    job.sources_json    = json.dumps(
        [s.model_dump() for s in sources], ensure_ascii=False
    )
    job.validation_json = validation.model_dump_json()
    job.meta_json       = meta.model_dump_json()
    job.updated_at      = datetime.utcnow()
    await session.commit()


async def mark_failed(
    session: AsyncSession,
    job_id: str,
    code: str,
    message: str,
) -> None:
    """실패 상태로 전환 + 에러 정보 저장."""
    job = await _get_or_raise(session, job_id)
    job.status        = JobStatus.failed
    job.error_code    = code
    job.error_message = message
    job.updated_at    = datetime.utcnow()
    await session.commit()


# ─────────────────────────────────────────────
# 조회
# ─────────────────────────────────────────────

async def get_job(session: AsyncSession, job_id: str) -> EnrichmentJob | None:
    return await session.get(EnrichmentJob, job_id)


async def get_latest_by_company(
    session: AsyncSession,
    company_id: str,
    limit: int = 10,
) -> list[EnrichmentJob]:
    """company_id 기준 최신 job 목록 조회."""
    result = await session.execute(
        select(EnrichmentJob)
        .where(
            EnrichmentJob.company_id == company_id,
            EnrichmentJob.status == JobStatus.completed,
        )
        .order_by(EnrichmentJob.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_result(
    session: AsyncSession,
    job_id: str,
) -> ContentPackageResponse | None:
    """
    완료된 job을 ContentPackageResponse로 역직렬화해 반환.
    미완료 또는 없으면 None.
    """
    job = await get_job(session, job_id)
    if job is None or job.status != JobStatus.completed:
        return None
    if not job.package_json or not job.sources_json:
        return None

    try:
        package    = ContentPackage.model_validate_json(job.package_json)
        sources    = [Source(**s) for s in json.loads(job.sources_json)]
        validation = ValidationResult.model_validate_json(job.validation_json or "{}")
        meta       = EnrichmentMeta.model_validate_json(job.meta_json or "{}")
    except Exception:
        return None

    return ContentPackageResponse(
        company_id=job.company_id,
        package=package,
        sources=sources,
        validation=validation,
        meta=meta,
    )


# ─────────────────────────────────────────────
# 내부
# ─────────────────────────────────────────────

async def _get_or_raise(session: AsyncSession, job_id: str) -> EnrichmentJob:
    job = await session.get(EnrichmentJob, job_id)
    if job is None:
        raise ValueError(f"Job {job_id!r} not found")
    return job
